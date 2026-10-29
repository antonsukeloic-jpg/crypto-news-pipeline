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
  curl -sS -m 120 -F chat_id="$TG_CHAT" -F supports_streaming=true \
    -F caption="$2" -F video=@"$1" \
    "https://api.telegram.org/bot$TG_TOKEN/sendVideo" | grep -q '"ok":true' \
    && log "sent to Telegram" || log "Telegram send FAILED"
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
      cap=$(python3 -c "import json;j=json.load(open('$dest'));print(('🇱🇹 ' if j.get('channel')=='lt' else '')+j.get('voiceover','')[:900])" 2>/dev/null)
      send_telegram "$ROOT/$outp" "$cap"
    else
      log "RENDER FAILED $outbase (see remotion/render_error.log)"
    fi
    mv "$dest" "$ARCH/$name" 2>/dev/null
  fi
  sleep 5
done
