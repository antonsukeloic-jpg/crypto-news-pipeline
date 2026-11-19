#!/bin/bash
# CryptoNewsFactory render watcher for the VPS (runs as a systemd service).
# n8n drops job_*.json into /root/shared/jobs and assets into /root/shared/assets.
# This renders each job with Remotion and sends the finished video to Telegram.
ROOT=/root/shared
JOBS=$ROOT/jobs; PROC=$ROOT/processing; ARCH=$ROOT/archive
RENDER="$(cd "$(dirname "$0")/.." && pwd)/remotion/render_vps.sh"
TG_ENV=/root/stack/telegram.env
mkdir -p "$JOBS" "$PROC" "$ARCH" "$ROOT/outputs"
log() { echo "[$(date '+%H:%M:%S')] $*"; }

send_telegram() {  # $1 = video path, $2 = caption
  [ -f "$TG_ENV" ] || { log "no $TG_ENV, skipping Telegram"; return; }
  . "$TG_ENV"
  # Telegram bots accept max 50 MB: re-encode anything over 45 MB (busy grain/glitch footage gets big)
  if [ "$(stat -c %s "$1")" -gt 47185920 ]; then
    local small="${1%.mp4}_tg.mp4"
    ffmpeg -loglevel error -y -i "$1" -c:v libx264 -preset veryfast -crf 27 -maxrate 9M -bufsize 18M -c:a aac -b:a 160k -movflags +faststart "$small" \
      && { log "compressed for Telegram: $(du -m "$1" | cut -f1) MB -> $(du -m "$small" | cut -f1) MB"; set -- "$small" "$2"; }
  fi
  # tell Telegram the real size, otherwise it may show the 9:16 video squashed / square
  local wh; wh=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$1" 2>/dev/null)
  curl -sS -m 120 -F chat_id="$TG_CHAT" -F supports_streaming=true \
    -F width="${wh%%,*}" -F height="${wh##*,}" \
    -F caption="$2" -F video=@"$1" \
    "https://api.telegram.org/bot$TG_TOKEN/sendVideo" | grep -q '"ok":true' \
    && log "sent to Telegram" || log "Telegram send FAILED"
}

tg_text() {  # $1 = text
  [ -f "$TG_ENV" ] || return; . "$TG_ENV"
  curl -sS -m 30 --data-urlencode chat_id="$TG_CHAT" --data-urlencode text="$1" --data-urlencode disable_web_page_preview=true \
    "https://api.telegram.org/bot$TG_TOKEN/sendMessage" >/dev/null 2>&1
}

publish() {  # $1 = job json, $2 = video path. Only when /root/stack/autopost_<channel> exists (kill switch: delete the file).
  local ch; ch=$(python3 -c "import json;print(json.load(open('$1')).get('channel',''))" 2>/dev/null)
  [ -n "$ch" ] && [ -f "/root/stack/autopost_$ch" ] || return 0
  local key; key=$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')
  local dir="$ROOT/public/$key"; mkdir -p "$dir"
  local f; f="$dir/$(basename "$2")"
  # platform copy: same look, smaller file (grain/glitch footage gets huge)
  ffmpeg -loglevel error -y -i "$2" -c:v libx264 -preset veryfast -crf 21 -maxrate 12M -bufsize 24M -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart "$f" || cp "$2" "$f"
  chmod -R a+rX "$dir"
  local url="https://n8n.visualforma.cloud/m/$key/$(basename "$2")"
  local payload; payload=$(python3 - "$1" "$url" <<'P'
import json,sys
j=json.load(open(sys.argv[1]))
print(json.dumps({"job":__import__('os').path.basename(sys.argv[1]),"channel":j.get("channel",""),"videoUrl":sys.argv[2],
  "voiceover":j.get("voiceover",""),"title":(j.get("meta") or {}).get("title","") or j.get("hook",""),"hashtags":j.get("hashtags",[])}))
P
)
  log "publishing $ch -> Metricool ($url)"
  local resp; resp=$(curl -sS -m 180 -H 'Content-Type: application/json' -d "$payload" https://n8n.visualforma.cloud/webhook/social-publish 2>&1)
  log "publish response: ${resp:0:400}"
  local msg; msg=$(python3 -c "
import json,sys
try: r=json.loads(sys.argv[1])
except Exception: print('⚠️ Publish: no answer from n8n'); sys.exit()
if r.get('skipped'): print('⏭ Publish skipped: '+str(r.get('reason')))
else: print('\n'.join(('✅ ' if p.get('ok') else '❌ ')+p.get('network','?')+(' scheduled (live in ~3 min) '+p.get('plannerUrl','') if p.get('ok') else ': '+p.get('error','')) for p in r.get('posts',[])) or '⚠️ Publish: empty answer')
" "$resp")
  tg_text "$ch: $msg"
  find "$ROOT/public" -mindepth 1 -maxdepth 1 -type d -mtime +5 -exec rm -rf {} + 2>/dev/null
}

log "watcher started, watching $JOBS"
while true; do
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
      send_telegram "$ROOT/$outp" "$cap"
      publish "$dest" "$ROOT/$outp"
    else
      log "RENDER FAILED $outbase (see remotion/render_error.log)"
    fi
    mv "$dest" "$ARCH/$name" 2>/dev/null
  fi
  sleep 5
done
