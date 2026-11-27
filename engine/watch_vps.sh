#!/bin/bash
# CryptoNewsFactory render watcher for the VPS (runs as a systemd service).
# n8n drops job_*.json into /root/shared/jobs and assets into /root/shared/assets.
# This renders each job with Remotion and sends the finished video to Telegram.
ROOT=/root/shared
JOBS=$ROOT/jobs; PROC=$ROOT/processing; ARCH=$ROOT/archive
RENDER="$(cd "$(dirname "$0")/.." && pwd)/remotion/render_vps.sh"
TG_ENV=/root/stack/telegram.env
APPR=$ROOT/approvals; APPROVE_SEC=1800
# Telegram outage handling (learned 2026-11-20: the server could not reach Telegram for hours, the approval
# counted down while the owner saw nothing). Now: quick reachability check before every send, nothing blocks
# the render loop; failed messages wait in an outbox and go out once Telegram is back; an approval countdown
# only starts when the video actually arrived; if Telegram stays down TG_GIVEUP_SEC, the post goes out anyway.
TG_OUT=$ROOT/tg_outbox; TG_GIVEUP_SEC=3600
mkdir -p "$JOBS" "$PROC" "$ARCH" "$ROOT/outputs" "$APPR" "$TG_OUT"; chmod 777 "$APPR"
log() { echo "[$(date '+%H:%M:%S')] $*"; }

TG_UP=1; TG_UP_AT=0
tg_up() {  # is the Telegram API reachable? (cached 60 s; a failed send marks it down)
  local now; now=$(date +%s)
  if [ $((now - TG_UP_AT)) -ge 60 ]; then
    [ -f "$TG_ENV" ] || return 1; . "$TG_ENV"
    if curl -sf -o /dev/null -m 8 "https://api.telegram.org/bot$TG_TOKEN/getMe"; then
      [ "$TG_UP" = 0 ] && log "Telegram reachable again"; TG_UP=1
    else
      [ "$TG_UP" = 1 ] && log "Telegram UNREACHABLE"; TG_UP=0
    fi
    TG_UP_AT=$now
  fi
  [ "$TG_UP" = 1 ]
}
tg_down() { TG_UP=0; TG_UP_AT=$(date +%s); }
tg_queue() {  # $1 = text -> outbox (sent later by tg_flush)
  printf '%s' "$1" > "$TG_OUT/$(date +%s%N).txt"; log "Telegram message queued (outbox)"
}
tg_queue_video() {  # $1 = video path, $2 = caption -> outbox
  printf '%s\n%s' "$1" "$2" > "$TG_OUT/$(date +%s%N).video"; log "Telegram video queued (outbox)"
}

TG_LAST_MSG=""; TG_VID_FAIL_AT=0
send_telegram() {  # $1 = video path, $2 = caption, $3 = optional reply_markup JSON (buttons)
  [ -f "$TG_ENV" ] || { log "no $TG_ENV, skipping Telegram"; return; }
  . "$TG_ENV"
  TG_LAST_MSG=""
  tg_up || { log "Telegram unreachable, video not sent"; return; }
  # video uploads can stall while small calls still work: after a failed upload wait 10 min before the next try
  [ $(( $(date +%s) - TG_VID_FAIL_AT )) -ge 600 ] || { log "Telegram video uploads failing, next try later"; return; }
  # Telegram bots accept max 50 MB: re-encode anything over 45 MB (busy grain/glitch footage gets big)
  if [ "$(stat -c %s "$1")" -gt 47185920 ]; then
    local small="${1%.mp4}_tg.mp4"
    ffmpeg -loglevel error -y -i "$1" -c:v libx264 -preset veryfast -crf 27 -maxrate 9M -bufsize 18M -c:a aac -b:a 160k -movflags +faststart "$small" \
      && { log "compressed for Telegram: $(du -m "$1" | cut -f1) MB -> $(du -m "$small" | cut -f1) MB"; set -- "$small" "$2" "$3"; }
  fi
  # tell Telegram the real size, otherwise it may show the 9:16 video squashed / square
  local wh; wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$1" 2>/dev/null)
  local extra=(); [ -n "$3" ] && extra=(--form-string reply_markup="$3")
  local resp; resp=$(curl -sS -m 120 --form-string chat_id="$TG_CHAT" -F supports_streaming=true \
    -F width="${wh%%,*}" -F height="${wh##*,}" \
    --form-string caption="$2" "${extra[@]}" -F video=@"$1" \
    "https://api.telegram.org/bot$TG_TOKEN/sendVideo")
  TG_LAST_MSG=$(printf '%s' "$resp" | python3 -c "import json,sys
try: print(json.load(sys.stdin)['result']['message_id'])
except Exception: print('')" 2>/dev/null)
  [ -n "$TG_LAST_MSG" ] && log "sent to Telegram" || { log "Telegram send FAILED: ${resp:0:200}"; tg_down; TG_VID_FAIL_AT=$(date +%s); }
}

tg_mark() {  # $1 = message id (buttons get removed), $2 = reply text
  [ -f "$TG_ENV" ] || return; . "$TG_ENV"
  { [ -n "$1" ] && tg_up; } || { tg_text "$2"; return; }
  curl -sS -m 20 --data-urlencode chat_id="$TG_CHAT" --data-urlencode message_id="$1" \
    --data-urlencode reply_markup='{"inline_keyboard":[]}' "https://api.telegram.org/bot$TG_TOKEN/editMessageReplyMarkup" >/dev/null 2>&1
  curl -sSf -m 20 --data-urlencode chat_id="$TG_CHAT" --data-urlencode text="$2" --data-urlencode reply_to_message_id="$1" \
    "https://api.telegram.org/bot$TG_TOKEN/sendMessage" >/dev/null 2>&1 || { tg_down; tg_queue "$2"; }
}

tg_album() {  # $1 = folder with slide_*.jpg (max 10), $2 = caption on the first photo
  [ -f "$TG_ENV" ] || return; . "$TG_ENV"
  tg_up || return
  local args=() media="[" k=0 f
  for f in $(ls "$1"/slide_*.jpg 2>/dev/null | sort | head -n 10); do
    k=$((k+1)); args+=(-F "p$k=@$f")
    [ $k -gt 1 ] && media+=","
    if [ $k -eq 1 ]; then media+=$(python3 -c "import json,sys;print(json.dumps({'type':'photo','media':'attach://p1','caption':sys.argv[1]}))" "$2")
    else media+="{\"type\":\"photo\",\"media\":\"attach://p$k\"}"; fi
  done
  media+="]"; [ $k -ge 2 ] || return
  curl -sSf -m 120 --form-string chat_id="$TG_CHAT" --form-string media="$media" "${args[@]}" \
    "https://api.telegram.org/bot$TG_TOKEN/sendMediaGroup" >/dev/null 2>&1 && log "carousel ($k slides) sent to Telegram" || tg_down
}

tg_text() {  # $1 = text (queued in the outbox if Telegram is unreachable)
  [ -f "$TG_ENV" ] || return; . "$TG_ENV"
  tg_up || { tg_queue "$1"; return; }
  curl -sSf -m 30 --data-urlencode chat_id="$TG_CHAT" --data-urlencode text="$1" --data-urlencode disable_web_page_preview=true \
    "https://api.telegram.org/bot$TG_TOKEN/sendMessage" >/dev/null 2>&1 || { tg_down; tg_queue "$1"; }
}

tg_flush() {  # send what waited in the outbox (oldest first) once Telegram is back; drop entries older than 24 h
  find "$TG_OUT" -maxdepth 1 -type f -mmin +1440 -delete 2>/dev/null
  local f; f=$(ls "$TG_OUT" 2>/dev/null | sort | head -n1); [ -n "$f" ] || return
  tg_up || return
  . "$TG_ENV"
  for f in $(ls "$TG_OUT" | sort); do
    case "$f" in
      *.txt)
        curl -sSf -m 30 --data-urlencode chat_id="$TG_CHAT" --data-urlencode text="⏳ (delayed, Telegram was unreachable) $(cat "$TG_OUT/$f")" \
          --data-urlencode disable_web_page_preview=true "https://api.telegram.org/bot$TG_TOKEN/sendMessage" >/dev/null 2>&1 \
          && rm -f "$TG_OUT/$f" || { tg_down; return; } ;;
      *.video)
        local v c; v=$(head -n1 "$TG_OUT/$f"); c=$(tail -n +2 "$TG_OUT/$f")
        [ -s "$v" ] || { rm -f "$TG_OUT/$f"; continue; }
        send_telegram "$v" "⏳ (delayed, Telegram was unreachable) $c"
        [ -n "$TG_LAST_MSG" ] && rm -f "$TG_OUT/$f" || return ;;
      *) rm -f "$TG_OUT/$f" ;;
    esac
  done
  log "Telegram outbox flushed"
}

job_channel() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('channel',''))" "$1" 2>/dev/null; }

prepare_public() {  # $1 = video path -> prints the public URL of a platform copy
  local key; key=$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')
  local dir="$ROOT/public/$key"; mkdir -p "$dir"
  local f; f="$dir/$(basename "$1")"
  # platform copy: same look, smaller file (grain/glitch footage gets huge)
  ffmpeg -loglevel error -y -i "$1" -c:v libx264 -preset veryfast -crf 21 -maxrate 12M -bufsize 24M -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$f" </dev/null || cp "$1" "$f"
  [ -s "${1%.mp4}_cover.jpg" ] && cp "${1%.mp4}_cover.jpg" "$dir/"
  [ -s "${1%.mp4}_slideshow.mp4" ] && cp "${1%.mp4}_slideshow.mp4" "$dir/"
  local sl; for sl in "${1%.mp4}"_car/slide_*.jpg; do [ -s "$sl" ] && cp "$sl" "$dir/$(basename "$1" .mp4)_car_$(basename "$sl" .jpg | sed 's/slide_//').jpg"; done
  chmod -R a+rX "$dir"
  echo "https://n8n.visualforma.cloud/m/$key/$(basename "$1")"
}

publish_report() {  # $1 = social-publish JSON answer, $2 = when it goes live -> Telegram text
  python3 -c "
import json,sys
try: r=json.loads(sys.argv[1])
except Exception: print('⚠️ Publish: no answer from n8n'); sys.exit()
if r.get('skipped'): print('⏭ Publish skipped: '+str(r.get('reason')))
else: print('\n'.join(('✅ ' if p.get('ok') else '❌ ')+p.get('network','?')+(' scheduled ('+sys.argv[2]+') '+p.get('plannerUrl','') if p.get('ok') else ': '+p.get('error','')) for p in r.get('posts',[])) or '⚠️ Publish: empty answer')
" "$1" "$2"
}

do_publish() {  # $1 = job json, $2 = public video URL
  local ch; ch=$(job_channel "$1"); local url="$2"
  local thumb=""; local tf="$ROOT/public/$(basename "$(dirname "$url")")/$(basename "$url" .mp4)_cover.jpg"
  [ -s "$tf" ] && thumb="$(dirname "$url")/$(basename "$url" .mp4)_cover.jpg"
  local payload; payload=$(python3 - "$1" "$url" "$thumb" <<'P'
import json,sys,os,re
def strategy():
    try: st=json.load(open("/root/shared/5hu_strategy.json"))
    except Exception: st={}
    try:   # Instagram careful mode: 14 days after the last "restricted activity" warning (written by 5HU Post Check)
        import time,datetime; h=json.load(open("/root/shared/5hu_ig_health.json"))
        t=datetime.datetime.fromisoformat(h["lastRestrictedAt"].replace("Z","+00:00")).timestamp()
        careful=time.time()-t < int(h.get("carefulDays",14))*86400
    except Exception: careful=False
    return {"captionNotes":str(st.get("caption_notes",""))[:600],"tiktokCarousel":st.get("tiktok_carousel","ab"),"igCautious":careful}
j=json.load(open(sys.argv[1]))
credits=[]
for s in j.get("scenes",[]):
    c=str(s.get("credit") or "").strip()
    if s.get("real") and c and c not in credits: credits.append(c)
print(json.dumps({"job":re.sub(r'^[a-f0-9]+__','',os.path.basename(sys.argv[1])),"channel":j.get("channel",""),"videoUrl":sys.argv[2],
  "thumbnailUrl":sys.argv[3],"creators":j.get("creators",[]),"credits":credits[:4],
  "voiceover":j.get("voiceover",""),"title":(j.get("meta") or {}).get("title","") or j.get("hook",""),"hashtags":j.get("hashtags",[]),
  "episode":j.get("episode"),"endQuestion":j.get("end_question",""),"sendCta":bool(j.get("send_cta")),
  **({"only":["tiktok","youtube","facebook"]} if j.get("slot")=="extra" else {}),**strategy()}))
P
)
  log "publishing $ch -> Metricool ($url)"
  local resp; resp=$(curl -sS -m 180 -H 'Content-Type: application/json' -d "$payload" https://n8n.visualforma.cloud/webhook/social-publish 2>&1)
  log "publish response: ${resp:0:400}"
  local rep; rep=$(publish_report "$resp" "live in ~3 min")
  if [ "${QUIET:-0}" != 1 ] || echo "$rep" | grep -qE "❌|⚠️|⏭"; then tg_text "$ch: $rep"; else log "published (quiet): ${rep//$'\n'/ | }"; fi
  # the series number counts only once the Reel is really out
  if [ "$ch" = 5hu ]; then
    local epv; epv=$(python3 -c "
import json,sys
try: r=json.loads(sys.argv[1]); ok=any(p.get('ok') for p in r.get('posts',[]))
except Exception: ok=False
e=json.load(open(sys.argv[2])).get('episode') if ok else None
print(e or '')" "$resp" "$1" 2>/dev/null)
    [ -n "$epv" ] && echo "$epv" > "$ROOT/5hu_episode" && log "5HU episode Nº$epv published"
    # log for the engagement assistant (who we featured, with the accounts we verified)
    [ -n "$epv" ] && python3 -c "
import json,sys,time,re
j=json.load(open(sys.argv[1]))
vo=(j.get('voiceover','') or '').strip(); hook=re.split(r'(?<=[.!?])\\s',vo,1)[0][:160] if vo else ''
sc=j.get('scenes') or [{}]; title=((j.get('carousel') or {}).get('cover') or sc[0].get('on_screen_text') or hook)[:80]
print(json.dumps({'ts':int(time.time()*1000),'title':title,'hook':hook,
  'creators':j.get('creators',[]),'episode':j.get('episode'),'words':len(vo.split()),'end_question':j.get('end_question',''),
  'collab':bool([c for c in (j.get('creators') or []) if c.get('instagram')]),'slot':j.get('slot','main'),'send_cta':bool(j.get('send_cta'))},ensure_ascii=False))" "$1" >> "$ROOT/5hu_featured.jsonl" 2>/dev/null
  fi
  # 5HU photo carousel: same story, deeper; Metricool holds it and posts it CAROUSEL_DELAY_MIN later
  local slides; slides=$(ls "$ROOT/public/$(basename "$(dirname "$url")")/$(basename "$url" .mp4)"_car_*.jpg 2>/dev/null | sort | head -n 10)
  local slot; slot=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('slot','main'))" "$1" 2>/dev/null)
  if [ "$slot" != extra ] && [ -n "$slides" ] && [ "$(echo "$slides" | wc -l)" -ge 3 ]; then
    local ssu=""; [ -s "$ROOT/public/$(basename "$(dirname "$url")")/$(basename "$url" .mp4)_slideshow.mp4" ] && ssu="$(dirname "$url")/$(basename "$url" .mp4)_slideshow.mp4"
    local cp; cp=$(python3 - "$1" "$(dirname "$url")" "$slides" "$ssu" <<'P'
import json,sys,os,re
def strategy():
    try: st=json.load(open("/root/shared/5hu_strategy.json"))
    except Exception: st={}
    try:   # Instagram careful mode: 14 days after the last "restricted activity" warning (written by 5HU Post Check)
        import time,datetime; h=json.load(open("/root/shared/5hu_ig_health.json"))
        t=datetime.datetime.fromisoformat(h["lastRestrictedAt"].replace("Z","+00:00")).timestamp()
        careful=time.time()-t < int(h.get("carefulDays",14))*86400
    except Exception: careful=False
    return {"captionNotes":str(st.get("caption_notes",""))[:600],"tiktokCarousel":st.get("tiktok_carousel","ab"),"igCautious":careful}
j=json.load(open(sys.argv[1])); base=sys.argv[2]; files=sys.argv[3].split(); ssu=sys.argv[4] if len(sys.argv)>4 else ""
c=j.get("carousel") or {}
txt="\n".join(f"{i+1}. {s.get('title','')} — {s.get('body','')}" for i,s in enumerate(c.get("slides",[])))
credits=[]
for s in j.get("scenes",[]):
    x=str(s.get("credit") or "").strip()
    if s.get("real") and x and x not in credits: credits.append(x)
print(json.dumps({"kind":"carousel","job":re.sub(r'^[a-f0-9]+__','',os.path.basename(sys.argv[1])),"channel":j.get("channel",""),
  "images":[base+"/"+os.path.basename(f) for f in files],"slideshowUrl":ssu,"delayMin":int(os.environ.get("CAROUSEL_DELAY_MIN","180")),
  "slidesText":("COVER: "+str(c.get("cover",""))+"\n"+txt)[:2000],"creators":j.get("creators",[]),"credits":credits[:4],
  "voiceover":j.get("voiceover",""),"title":(j.get("meta") or {}).get("title","") or j.get("hook",""),"hashtags":j.get("hashtags",[]),
  "episode":j.get("episode"),"endQuestion":j.get("end_question",""),**strategy()}))
P
)
    resp=$(curl -sS -m 180 -H 'Content-Type: application/json' -d "$cp" https://n8n.visualforma.cloud/webhook/social-publish 2>&1)
    log "carousel publish response: ${resp:0:400}"
    rep=$(publish_report "$resp" "goes live $(TZ=Europe/Vilnius date -d "+${CAROUSEL_DELAY_MIN:-180} min" +%H:%M)")
    if [ "${QUIET:-0}" != 1 ] || echo "$rep" | grep -qE "❌|⚠️|⏭"; then tg_text "$ch carousel: $rep"; else log "carousel scheduled (quiet): ${rep//$'\n'/ | }"; fi
  fi
  find "$ROOT/public" -mindepth 1 -maxdepth 1 -type d -mtime +5 -exec rm -rf {} + 2>/dev/null
}

publish() {  # $1 = job json, $2 = video path. Only when /root/stack/autopost_<channel> exists (kill switch: delete the file).
  local ch; ch=$(job_channel "$1")
  [ -n "$ch" ] && [ -f "/root/stack/autopost_$ch" ] || return 0
  do_publish "$1" "$(prepare_public "$2")"
}

# ---- approval: with /root/stack/approve_<channel>, the video comes to Telegram with buttons.
#      ✅ Post -> publish now · 🔄 Another story -> new run (max 2 per 90 min) · ❌ Skip -> nothing.
#      No answer in APPROVE_SEC -> publish anyway. /root/stack/approval_dryrun = test mode (never publishes).
alt_count() { [ -f "$APPR/.alt" ] || { echo 0; return; }; awk -v t=$(( $(date +%s) - 5400 )) '$1>t' "$APPR/.alt" | wc -l; }
start_run() {  # $1 = channel (only 5hu has a re-run path)
  [ "$1" = "5hu" ] || return 1
  ( cd /root/stack && docker compose exec -T -e N8N_RUNNERS_BROKER_PORT=5684 n8n \
      n8n execute --id="$(cat /root/stack/5hu_wf_id)" >> /root/exec_5hu.log 2>&1 </dev/null & )
}

approval_send() {  # $1 = approval id, $2 = video path, $3 = extra first line (optional) -> 0 if the video with buttons arrived
  tg_up || return 1
  local due=$(( $(date +%s) + APPROVE_SEC ))
  local pre=""; [ -n "$3" ] && pre="$3"$'\n'
  local cap="$pre$(cat "$APPR/$1.cap")"$'\n\n'"🕒 Auto-posts at $(TZ=Europe/Vilnius date -d @$due +%H:%M) if you don't choose."
  local kb='{"inline_keyboard":[[{"text":"✅ Post","callback_data":"ap:'$1':post"},{"text":"🔄 Another story","callback_data":"ap:'$1':alt"},{"text":"❌ Skip","callback_data":"ap:'$1':skip"}]]}'
  [ -d "${2%.mp4}_car" ] && tg_album "${2%.mp4}_car" "🖼 Carousel for this story — posts ~3 h after the video on Instagram, Facebook and TikTok (TikTok alternates: photo carousel with TikTok music / slideshow with our music). Same buttons below."
  send_telegram "$2" "$cap" "$kb"
  [ -n "$TG_LAST_MSG" ]
}

request_approval() {  # $1 = job json, $2 = video path, $3 = caption
  local id; id=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
  local url; url=$(prepare_public "$2")
  cp "$1" "$APPR/${id}__$(basename "$1")"
  local test=""; [ -f /root/stack/approval_dryrun ] && test="🧪 TEST — nothing will be posted"$'\n'
  local body; body=$(python3 -c "import sys;print(sys.argv[1].encode('utf-8','surrogateescape').decode('utf-8','ignore')[:800])" "$3")
  printf '%s' "${test}${body}" > "$APPR/$id.cap"
  local due state msg=""
  if approval_send "$id" "$2"; then state=sent; msg=$TG_LAST_MSG; due=$(( $(date +%s) + APPROVE_SEC ))
  else state=undelivered; due=$(( $(date +%s) + TG_GIVEUP_SEC )); fi   # countdown waits for Telegram (max TG_GIVEUP_SEC)
  printf '%s\n' "url=$url" "due=$due" "msg=$msg" "job=$APPR/${id}__$(basename "$1")" "video=$2" "state=$state" > "$APPR/$id.pending"
  log "approval $id requested ($state, auto at $(date -d @$due +%H:%M))"
}

check_approvals() {
  local p
  for p in "$APPR"/*.pending; do
    [ -e "$p" ] || continue
    local id url due msg job act now
    id=$(basename "$p" .pending)
    url=$(sed -n 's/^url=//p' "$p"); due=$(sed -n 's/^due=//p' "$p"); msg=$(sed -n 's/^msg=//p' "$p"); job=$(sed -n 's/^job=//p' "$p")
    act=""; [ -f "$APPR/$id.decision" ] && act=$(head -n1 "$APPR/$id.decision" | tr -dc 'a-z')
    now=$(date +%s)
    # not delivered yet (Telegram was down): retry; the 30-min countdown starts when it arrives
    if [ -z "$act" ] && [ "$(sed -n 's/^state=//p' "$p")" = undelivered ] && [ "$now" -lt "${due:-0}" ]; then
      local vid; vid=$(sed -n 's/^video=//p' "$p")
      if [ -s "$vid" ] && approval_send "$id" "$vid" "⏳ Delayed — Telegram was unreachable when this video was ready."; then
        sed -i "s/^due=.*/due=$(( $(date +%s) + APPROVE_SEC ))/; s/^msg=.*/msg=$TG_LAST_MSG/; s/^state=.*/state=sent/" "$p"
        log "approval $id delivered late, countdown started"
      fi
      continue
    fi
    [ -z "$act" ] && [ "$now" -lt "${due:-0}" ] && continue
    [ -z "$act" ] && act=auto
    mv "$p" "$APPR/$id.done" 2>/dev/null || continue   # claim it once
    log "approval $id -> $act"
    case "$act" in
      post|auto)
        if [ "$act" = auto ] && [ "$(sed -n 's/^state=//p' "$APPR/$id.done")" = undelivered ]; then
          tg_text "⚠️ Telegram was unreachable for an hour, so this video went out automatically without approval: $(head -c 300 "$APPR/$id.cap" 2>/dev/null)"
        else
          tg_mark "$msg" "$([ "$act" = auto ] && echo '⏱ No answer in 30 min — posting now.' || echo '✅ Approved — posting now.')"
        fi
        if [ -f /root/stack/approval_dryrun ]; then tg_text "🧪 TEST mode: this is where it would publish to TikTok, Instagram, YouTube and Facebook (+ the carousel 3 h later)."
        else do_publish "$job" "$url"; fi ;;
      skip) tg_mark "$msg" "❌ Skipped — nothing posted." ;;
      alt)
        if [ "$(alt_count)" -ge 2 ]; then tg_mark "$msg" "🔄 Already tried 2 other stories — nothing posted this time."
        else date +%s >> "$APPR/.alt"; tg_mark "$msg" "🔄 OK — picking another story. New video in about 8 min."
             start_run "$(job_channel "$job")" || tg_text "⚠️ Can't start a new run for this channel."; fi ;;
      *) tg_mark "$msg" "⚠️ Unknown choice — nothing posted." ;;
    esac
  done
  find "$APPR" -maxdepth 1 -type f -mtime +7 -delete 2>/dev/null
}

log "watcher started, watching $JOBS"
while true; do
  check_approvals
  tg_flush
  jobfile=$(find "$JOBS" -maxdepth 1 -name '*.json' 2>/dev/null | head -n1)
  if [ -n "$jobfile" ]; then
    name=$(basename "$jobfile")
    outp=$(python3 -c "import json;print(json.load(open('$jobfile'))['output'])" 2>/dev/null)
    if [ -z "$outp" ]; then log "$name not readable yet"; sleep 3; continue; fi
    outbase=$(basename "$outp")
    if [ -f "$ARCH/.done_$outbase" ]; then log "$outbase already done, dropping duplicate"; rm -f "$jobfile"; continue; fi
    dest="$PROC/$name"; mv "$jobfile" "$dest" 2>/dev/null || continue
    log "job $name -> $outbase"
    for try in $(seq 1 60); do   # wait up to 3 min for all images + voice
      missing=$(python3 -c "import json,os;j=json.load(open('$dest'));fs=[j['voice']]+[s['image'] for s in j['scenes']];print(sum(not os.path.exists(os.path.join('$ROOT',f)) for f in fs))" 2>/dev/null)
      [ "$missing" = "0" ] && break
      log "waiting for assets ($missing missing)"; sleep 3
    done
    rm -f "$ROOT/$outp"
    log "rendering..."
    if [ "$(job_channel "$dest")" = 5hu ]; then
      ep=$(( $(cat "$ROOT/5hu_episode" 2>/dev/null || echo 0) + 1 ))
      # slot (owner 2026-11-27, turbo growth): 08:20 + 18:20 runs = main (all networks + carousel); other runs = extra
      # (TikTok / YouTube / Facebook only). send_cta A/B: every 2nd episode the outro asks to send it to a friend.
      slot=extra; case "$(TZ=Europe/Vilnius date +%H)" in 08|09|18|19) slot=main ;; esac
      python3 -c "import json,sys;p=sys.argv[1];j=json.load(open(p));j['episode']=int(sys.argv[2]);j['slot']=sys.argv[3];j['send_cta']=int(sys.argv[2])%2==1;json.dump(j,open(p,'w'),ensure_ascii=False)" "$dest" "$ep" "$slot" \
        && log "5HU episode Nº$ep ($slot slot)"
    fi
    bash "$RENDER" "$dest" "$ROOT" "$ROOT/$outp"
    if [ -f "$ROOT/$outp" ]; then
      touch "$ARCH/.done_$outbase"; log "OK $outbase"
      cap=$(python3 -c "import json;j=json.load(open('$dest'));print({'lt':'🇱🇹 ','vikops':'🪨 VIKOPS · ','5hu':'👗 5HU · '}.get(j.get('channel'),'')+j.get('voiceover','')[:900])" 2>/dev/null)
      ch=$(job_channel "$dest")
      if [ -n "$ch" ] && [ -f "/root/stack/hold_$ch" ]; then
        # render-only test: keep the video, post nothing, message nobody
        log "HELD (hold_$ch): $outbase rendered, not posted"
        cp "$dest" "$ROOT/outputs/$(basename "$outp" .mp4).job.json" 2>/dev/null
      elif [ -n "$ch" ] && [ -f "/root/stack/autopost_$ch" ] && [ -f "/root/stack/approve_$ch" ]; then
        request_approval "$dest" "$ROOT/$outp" "$cap"
      elif [ -n "$ch" ] && [ -f "/root/stack/quiet_$ch" ]; then
        # fully automatic: no video / reports in Telegram, only errors (owner 2026-11-25)
        QUIET=1 publish "$dest" "$ROOT/$outp"
      else
        send_telegram "$ROOT/$outp" "$cap"
        [ -n "$TG_LAST_MSG" ] || tg_queue_video "$ROOT/$outp" "$cap"
        publish "$dest" "$ROOT/$outp"
      fi
    else
      log "RENDER FAILED $outbase (see remotion/render_error.log)"
      tg_text "⚠️ $(job_channel "$dest"): a video failed to render ($outbase). Nothing was posted for this slot."
    fi
    mv "$dest" "$ARCH/$name" 2>/dev/null
  fi
  sleep 5
done
