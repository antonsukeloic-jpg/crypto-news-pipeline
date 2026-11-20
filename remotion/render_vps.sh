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
# 5HU: Reel/Short cover from the real photo + hook (used as the Instagram / Facebook thumbnail)
if [ "$CH" = "5hu" ] && [ -s "$OUT" ]; then
  npx remotion still src/index.js FiveHuCover "${OUT%.mp4}_cover.jpg" --props="$PROJ/props.json" --port=3999 \
    --image-format=jpeg --jpeg-quality=88 --log=error >> "$PROJ/render_error.log" 2>&1 || rm -f "${OUT%.mp4}_cover.jpg"
fi
# 5HU: photo carousel (4:5 slides) when the job has carousel copy -> <video>_car/slide_01.jpg ... (posted ~3 h after the Reel)
if [ "$CH" = "5hu" ] && [ -s "$OUT" ] && python3 -c "import json,sys;sys.exit(0 if json.load(open('$PROJ/props.json')).get('carousel',{}).get('slides') else 1)" 2>/dev/null; then
  CAR="${OUT%.mp4}_car"; rm -rf "$CAR"; mkdir -p "$CAR"
  npx remotion render src/index.js FiveHuCarousel "$CAR" --sequence --image-format=jpeg --jpeg-quality=90 --props="$PROJ/props.json" \
    --port=3999 --log=error >> "$PROJ/render_error.log" 2>&1
  i=0; for f in $(ls -v "$CAR" | grep -Ei '\.jpe?g$'); do i=$((i+1)); mv "$CAR/$f" "$CAR/s$(printf %02d $i).tmp"; done
  for f in "$CAR"/s*.tmp; do [ -e "$f" ] && mv "$f" "$CAR/slide_$(basename "$f" .tmp | tr -d s).jpg"; done
  [ "$i" -ge 3 ] || rm -rf "$CAR"
fi
# 5HU: TikTok slideshow = the carousel slides as a 9:16 video over the same music (TikTok photo posts can't carry our track)
if [ "$CH" = "5hu" ] && [ -d "${OUT%.mp4}_car" ]; then
  SS="${OUT%.mp4}_slideshow.mp4"
  npx remotion render src/index.js FiveHuSlideshow "$SS" --props="$PROJ/props.json" --port=3999 --concurrency=4 --x264-preset=veryfast \
    --scale=0.75 --log=error >> "$PROJ/render_error.log" 2>&1 \
  && ffmpeg -loglevel error -y -i "$SS" -c:v copy -af "loudnorm=I=-14:TP=-1.5:LRA=11" -c:a aac -b:a 192k -movflags +faststart "${SS%.mp4}_ln.mp4" \
  && mv -f "${SS%.mp4}_ln.mp4" "$SS" || rm -f "$SS" "${SS%.mp4}_ln.mp4"
fi
