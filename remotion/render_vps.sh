#!/bin/bash
# Render one job on the VPS: render_vps.sh <job.json> <root_dir> <out.mp4>
JOB="$1"; ROOT="$2"; OUT="$3"
PROJ="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$PROJ/public/logos" && cp -f "$PROJ"/logos/*.png "$PROJ/public/logos/"   # coin logos
mkdir -p "$PROJ/public/music" && cp -f "$PROJ"/music/*.mp3 "$PROJ/public/music/" 2>/dev/null   # music beds (5HU)
mkdir -p "$PROJ/public/fx" && cp -f "$PROJ"/fx/*.png "$PROJ/public/fx/" 2>/dev/null   # grain tiles (5HU)
python3 "$PROJ/make_props.py" "$JOB" "$ROOT" "$PROJ/public" "$PROJ/props.json" || exit 1
cd "$PROJ" || exit 1
EXTRA="--concurrency=3"
CH=$(python3 -c "import json;print(json.load(open('$JOB')).get('channel',''))" 2>/dev/null)
[ "$CH" = "5hu" ] && EXTRA="--concurrency=4 --x264-preset=veryfast --scale=0.75"   # 5HU: 810x1440 (integer dims), speed over file size
npx remotion render src/index.js NewsVideo "$OUT" \
  --props="$PROJ/props.json" --port=3999 $EXTRA --log=error 2>&1 | tee "$PROJ/render_error.log"
# 5HU + crypto: even loudness for phones (-14 LUFS, like TikTok/Reels); video stream is copied untouched
if [ "$CH" != "lt" ] && [ "$CH" != "vikops" ] && [ -s "$OUT" ]; then
  ffmpeg -loglevel error -y -i "$OUT" -c:v copy -af "loudnorm=I=-14:TP=-1.5:LRA=11" -c:a aac -b:a 192k -movflags +faststart "${OUT%.mp4}_ln.mp4" && mv -f "${OUT%.mp4}_ln.mp4" "$OUT"
fi
