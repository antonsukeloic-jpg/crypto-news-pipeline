#!/bin/zsh
JOB="$1"; ROOT="$2"; OUT="$3"
PROJ="${0:A:h}"
python3 "$PROJ/make_props.py" "$JOB" "$ROOT" "$PROJ/public" "$PROJ/props.json" || exit 1
cd "$PROJ"
npx remotion render src/index.js NewsVideo "$OUT" --props="$PROJ/props.json" --port=3999 --log=error 2>&1 | tee "$PROJ/render_error.log"
