#!/bin/bash
# Render one job on the VPS: render_vps.sh <job.json> <root_dir> <out.mp4>
JOB="$1"; ROOT="$2"; OUT="$3"
PROJ="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$PROJ/public/logos" && cp -f "$PROJ"/logos/*.png "$PROJ/public/logos/"   # coin logos
python3 "$PROJ/make_props.py" "$JOB" "$ROOT" "$PROJ/public" "$PROJ/props.json" || exit 1
cd "$PROJ" || exit 1
npx remotion render src/index.js NewsVideo "$OUT" \
  --props="$PROJ/props.json" --port=3999 --concurrency=3 --log=error 2>&1 | tee "$PROJ/render_error.log"
