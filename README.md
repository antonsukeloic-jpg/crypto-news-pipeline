# Crypto News Video Pipeline

Automated crypto-news short-video pipeline (n8n + Remotion).
- `remotion/` — Remotion render project (9:16 vertical news videos)
- `engine/` — render watcher scripts
- `remotion/make_props.py` — builds props.json for a render (incl. live multi-source BTC price)

Render stack: Node + Remotion + ffmpeg + Chromium. Orchestration: n8n.
