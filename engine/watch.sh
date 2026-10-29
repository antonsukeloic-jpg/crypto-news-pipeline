#!/bin/zsh
ENGINE="${0:A:h}"
ROOT="${ENGINE:h}"
JOBS="$ROOT/jobs"; PROC="$ROOT/temp/processing"; ARCH="$ROOT/archive"
TPL="$ENGINE/template/short_template.aep"
JSX="$ENGINE/build_main.jsx"
AE="/Applications/Adobe After Effects 2026/aerender"
mkdir -p "$JOBS" "$PROC" "$ARCH"
echo "=== CryptoNewsFactory watcher (Mac, dynamic, single-render guard). Watching: $JOBS. Close window to stop. ==="
while true; do
  jobfile=$(find "$JOBS" -maxdepth 1 -name '*.json' 2>/dev/null | head -n1)
  if [ -n "$jobfile" ]; then
    name=$(basename "$jobfile")
    if [ -f "$ARCH/$name" ]; then echo "[$(date '+%H:%M:%S')] dup $name done, removing"; rm -f "$jobfile"; continue; fi
    lock="$PROC/$name.lock"
    if ! mkdir "$lock" 2>/dev/null; then sleep 2; continue; fi
    dest="$PROC/$name"
    mv "$jobfile" "$dest" 2>/dev/null
    if [ ! -f "$dest" ]; then rmdir "$lock" 2>/dev/null; continue; fi
    echo "[$(date '+%H:%M:%S')] Found job: $name"
    cp "$dest" "$ENGINE/current_job.json"
    comp=$(python3 -c "import json;print(json.load(open('$dest'))['comp'])")
    outp=$(python3 -c "import json;print(json.load(open('$dest'))['output'])")
    for try in {1..60}; do
      missing=$(python3 -c "import json,os;j=json.load(open('$dest'));r='$ROOT';fs=[j['voice']]+[s['image'] for s in j['scenes']];print(len([f for f in fs if not os.path.exists(os.path.join(r,f))]))")
      if [ "$missing" = "0" ]; then echo "[$(date '+%H:%M:%S')] all assets present"; break; fi
      echo "[$(date '+%H:%M:%S')] waiting for assets ($missing missing)..."; sleep 3
    done
    rm -f "$ROOT/$outp"
    echo "[$(date '+%H:%M:%S')] Rendering $comp -> $outp ..."
    CNF_ROOT="$ROOT" "$AE" -project "$TPL" -r "$JSX" -comp "$comp" -OMtemplate "H.264 - Match Render Settings - 15 Mbps" -output "$ROOT/$outp"
    mv "$dest" "$ARCH/$name"
    rmdir "$lock" 2>/dev/null
    echo "[$(date '+%H:%M:%S')] Finished: $name"
  fi
  sleep 5
done
