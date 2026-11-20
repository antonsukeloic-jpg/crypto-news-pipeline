#!/bin/bash
# CryptoNewsFactory render watcher for the VPS (runs as a systemd service).
# n8n drops job_*.json into /root/shared/jobs and assets into /root/shared/assets.
# This renders each job with Remotion and sends the finished video to Telegram.
ROOT=/root/shared
JOBS=$ROOT/jobs; PROC=$ROOT/processing; ARCH=$ROOT/archive
RENDER="$(cd "$(dirname "$0")/.." && pwd)/remotion/render_vps.sh"
TG_ENV=/root/stack/telegram.env
APPR=$ROOT/approvals; APPROVE_SEC=1800
mkdir -p "$JOBS" "$PROC" "$ARCH" "$ROOT/outputs" "$APPR"; chmod 777 "$APPR"
log() { echo "[$(date '+%H:%M:%S')] $*"; }

TG_LAST_MSG=""
send_telegram() {  # $1 = video path, $2 = caption, $3 = optional reply_markup JSON (buttons)
  [ -f "$TG_ENV" ] || { log "no $TG_ENV, skipping Telegram"; return; }
  . "$TG_ENV"
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
  [ -n "$TG_LAST_MSG" ] && log "sent to Telegram" || log "Telegram send FAILED: ${resp:0:200}"
}

tg_mark() {  # $1 = message id (buttons get removed), $2 = reply text
  [ -f "$TG_ENV" ] || return; . "$TG_ENV"
  [ -n "$1" ] && curl -sS -m 20 --data-urlencode chat_id="$TG_CHAT" --data-urlencode message_id="$1" \
    --data-urlencode reply_markup='{"inline_keyboard":[]}' "https://api.telegram.org/bot$TG_TOKEN/editMessageReplyMarkup" >/dev/null 2>&1
  local r=(); [ -n "$1" ] && r=(--data-urlencode reply_to_message_id="$1")
  curl -sS -m 20 --data-urlencode chat_id="$TG_CHAT" --data-urlencode text="$2" "${r[@]}" \
    "https://api.telegram.org/bot$TG_TOKEN/sendMessage" >/dev/null 2>&1
}

tg_album() {  # $1 = folder with slide_*.jpg (max 10), $2 = caption on the first photo
  [ -f "$TG_ENV" ] || return; . "$TG_ENV"
  local args=() media="[" k=0 f
  for f in $(ls "$1"/slide_*.jpg 2>/dev/null | sort | head -n 10); do
    k=$((k+1)); args+=(-F "p$k=@$f")
    [ $k -gt 1 ] && media+=","
    if [ $k -eq 1 ]; then media+=$(python3 -c "import json,sys;print(json.dumps({'type':'photo','media':'attach://p1','caption':sys.argv[1]}))" "$2")
    else media+="{\"type\":\"photo\",\"media\":\"attach://p$k\"}"; fi
  done
  media+="]"; [ $k -ge 2 ] || return
  curl -sS -m 120 --form-string chat_id="$TG_CHAT" --form-string media="$media" "${args[@]}" \
    "https://api.telegram.org/bot$TG_TOKEN/sendMediaGroup" >/dev/null 2>&1 && log "carousel ($k slides) sent to Telegram"
}

tg_text() {  # $1 = text
  [ -f "$TG_ENV" ] || return; . "$TG_ENV"
  curl -sS -m 30 --data-urlencode chat_id="$TG_CHAT" --data-urlencode text="$1" --data-urlencode disable_web_page_preview=true \
    "https://api.telegram.org/bot$TG_TOKEN/sendMessage" >/dev/null 2>&1
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
j=json.load(open(sys.argv[1]))
credits=[]
for s in j.get("scenes",[]):
    c=str(s.get("credit") or "").strip()
    if s.get("real") and c and c not in credits: credits.append(c)
print(json.dumps({"job":re.sub(r'^[a-f0-9]+__','',os.path.basename(sys.argv[1])),"channel":j.get("channel",""),"videoUrl":sys.argv[2],
  "thumbnailUrl":sys.argv[3],"creators":j.get("creators",[]),"credits":credits[:4],
  "voiceover":j.get("voiceover",""),"title":(j.get("meta") or {}).get("title","") or j.get("hook",""),"hashtags":j.get("hashtags",[])}))
P
)
  log "publishing $ch -> Metricool ($url)"
  local resp; resp=$(curl -sS -m 180 -H 'Content-Type: application/json' -d "$payload" https://n8n.visualforma.cloud/webhook/social-publish 2>&1)
  log "publish response: ${resp:0:400}"
  tg_text "$ch: $(publish_report "$resp" "live in ~3 min")"
  # 5HU photo carousel: same story, deeper; Metricool holds it and posts it CAROUSEL_DELAY_MIN later
  local slides; slides=$(ls "$ROOT/public/$(basename "$(dirname "$url")")/$(basename "$url" .mp4)"_car_*.jpg 2>/dev/null | sort | head -n 10)
  if [ -n "$slides" ] && [ "$(echo "$slides" | wc -l)" -ge 3 ]; then
    local ssu=""; [ -s "$ROOT/public/$(basename "$(dirname "$url")")/$(basename "$url" .mp4)_slideshow.mp4" ] && ssu="$(dirname "$url")/$(basename "$url" .mp4)_slideshow.mp4"
    local cp; cp=$(python3 - "$1" "$(dirname "$url")" "$slides" "$ssu" <<'P'
import json,sys,os,re
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
  "voiceover":j.get("voiceover",""),"title":(j.get("meta") or {}).get("title","") or j.get("hook",""),"hashtags":j.get("hashtags",[])}))
P
)
    resp=$(curl -sS -m 180 -H 'Content-Type: application/json' -d "$cp" https://n8n.visualforma.cloud/webhook/social-publish 2>&1)
    log "carousel publish response: ${resp:0:400}"
    tg_text "$ch carousel: $(publish_report "$resp" "goes live $(TZ=Europe/Vilnius date -d "+${CAROUSEL_DELAY_MIN:-180} min" +%H:%M)")"
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

request_approval() {  # $1 = job json, $2 = video path, $3 = caption
  local id; id=$(head -c 6 /dev/urandom | od -An -tx1 | tr -d ' \n')
  local url; url=$(prepare_public "$2")
  cp "$1" "$APPR/${id}__$(basename "$1")"
  local due=$(( $(date +%s) + APPROVE_SEC ))
  local test=""; [ -f /root/stack/approval_dryrun ] && test="🧪 TEST — nothing will be posted"$'\n'
  local body; body=$(python3 -c "import sys;print(sys.argv[1].encode('utf-8','surrogateescape').decode('utf-8','ignore')[:800])" "$3")
  local cap="${test}${body}"$'\n\n'"🕒 Auto-posts at $(TZ=Europe/Vilnius date -d @$due +%H:%M) if you don't choose."
  local kb='{"inline_keyboard":[[{"text":"✅ Post","callback_data":"ap:'$id':post"},{"text":"🔄 Another story","callback_data":"ap:'$id':alt"},{"text":"❌ Skip","callback_data":"ap:'$id':skip"}]]}'
  [ -d "${2%.mp4}_car" ] && tg_album "${2%.mp4}_car" "🖼 Carousel for this story — posts ~3 h after the video on Instagram + Facebook; TikTok gets it as a slideshow video with our music (same buttons below)."
  send_telegram "$2" "$cap" "$kb"
  printf '%s\n' "url=$url" "due=$due" "msg=$TG_LAST_MSG" "job=$APPR/${id}__$(basename "$1")" > "$APPR/$id.pending"
  log "approval $id requested (auto at $(date -d @$due +%H:%M))"
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
    [ -z "$act" ] && [ "$now" -lt "${due:-0}" ] && continue
    [ -z "$act" ] && act=auto
    mv "$p" "$APPR/$id.done" 2>/dev/null || continue   # claim it once
    log "approval $id -> $act"
    case "$act" in
      post|auto)
        tg_mark "$msg" "$([ "$act" = auto ] && echo '⏱ No answer in 30 min — posting now.' || echo '✅ Approved — posting now.')"
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
    bash "$RENDER" "$dest" "$ROOT" "$ROOT/$outp"
    if [ -f "$ROOT/$outp" ]; then
      touch "$ARCH/.done_$outbase"; log "OK $outbase"
      cap=$(python3 -c "import json;j=json.load(open('$dest'));print({'lt':'🇱🇹 ','vikops':'🪨 VIKOPS · ','5hu':'👗 5HU · '}.get(j.get('channel'),'')+j.get('voiceover','')[:900])" 2>/dev/null)
      ch=$(job_channel "$dest")
      if [ -n "$ch" ] && [ -f "/root/stack/autopost_$ch" ] && [ -f "/root/stack/approve_$ch" ]; then
        request_approval "$dest" "$ROOT/$outp" "$cap"
      else
        send_telegram "$ROOT/$outp" "$cap"
        publish "$dest" "$ROOT/$outp"
      fi
    else
      log "RENDER FAILED $outbase (see remotion/render_error.log)"
    fi
    mv "$dest" "$ARCH/$name" 2>/dev/null
  fi
  sleep 5
done
