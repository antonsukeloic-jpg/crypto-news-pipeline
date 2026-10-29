#!/bin/zsh
ENGINE="${0:A:h}"
ROOT="${ENGINE:h}"
REMOTION="/Users/shu/Library/CloudStorage/GoogleDrive-antonsukeloic@gmail.com/My Drive/5HU/CryptoNewsFactory/remotion"
JOBS="$ROOT/jobs"; PROC="$ROOT/temp/processing"; ARCH="$ROOT/archive"
mkdir -p "$JOBS" "$PROC" "$ARCH"
echo "=== CryptoNewsFactory watcher (REMOTION render, dedup-by-output). Watching: $JOBS. Close window to stop. ==="
while true; do
  jobfile=$(find "$JOBS" -maxdepth 1 -name '*.json' 2>/dev/null | head -n1)
  if [ -n "$jobfile" ]; then
    name=$(basename "$jobfile")
    # read the output video name from inside the job JSON (the true identity of the render)
    outp=$(python3 -c "import json,sys;print(json.load(open('$jobfile'))['output'])" 2>/dev/null)
    if [ -z "$outp" ]; then echo "[$(date '+%H:%M:%S')] $name not readable yet (still syncing?), waiting..."; sleep 3; continue; fi
    outbase=$(basename "$outp")
    # DEDUP: if this output was already rendered, this is a duplicate job file -> discard it
    if [ -f "$ARCH/.done_$outbase" ]; then echo "[$(date '+%H:%M:%S')] $outbase already rendered; discarding duplicate $name"; rm -f "$jobfile"; continue; fi
    # LOCK on the output name so two copies of the same job can never render at once
    lock="$PROC/$outbase.lock"
    if ! mkdir "$lock" 2>/dev/null; then sleep 2; continue; fi
    dest="$PROC/$name"
    mv "$jobfile" "$dest" 2>/dev/null
    if [ ! -f "$dest" ]; then rmdir "$lock" 2>/dev/null; continue; fi
    ts=$(echo "$name" | grep -oE '[0-9]{10,}' | head -1); [ -n "$ts" ] && rm -f "$JOBS"/*"$ts"*.json 2>/dev/null
    echo "[$(date '+%H:%M:%S')] Found job: $name  ->  $outbase"
    # wait for all assets (voice + images) to finish syncing down from Drive
    for try in {1..60}; do
      missing=$(python3 -c "import json,os;j=json.load(open('$dest'));r='$ROOT';fs=[j['voice']]+[s['image'] for s in j['scenes']];print(len([f for f in fs if not os.path.exists(os.path.join(r,f))]))" 2>/dev/null)
      if [ "$missing" = "0" ]; then echo "[$(date '+%H:%M:%S')] all assets present"; break; fi
      echo "[$(date '+%H:%M:%S')] waiting for assets ($missing missing)..."; sleep 3
    done
    rm -f "$ROOT/$outp"
    echo "[$(date '+%H:%M:%S')] Rendering (Remotion) -> $outp ..."
    zsh "$REMOTION/render_remotion.sh" "$dest" "$ROOT" "$ROOT/$outp"
    if [ -f "$ROOT/$outp" ]; then touch "$ARCH/.done_$outbase"; echo "[$(date '+%H:%M:%S')] OK: $outbase"; else echo "[$(date '+%H:%M:%S')] RENDER FAILED: $outbase (will retry on next job)"; fi
    mv "$dest" "$ARCH/$name" 2>/dev/null
    rmdir "$lock" 2>/dev/null
    echo "[$(date '+%H:%M:%S')] Finished: $name"
  fi
  sleep 5
done
