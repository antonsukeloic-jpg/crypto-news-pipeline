#!/bin/bash
# One-time: small Python venv with OpenCV for remotion/focus.py (subject-aware crops on 5HU covers + carousels).
set -e
command -v python3 >/dev/null
dpkg -s python3-venv >/dev/null 2>&1 || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv >/dev/null; }
[ -x /opt/focus/bin/python ] || python3 -m venv /opt/focus
/opt/focus/bin/pip install -q --upgrade pip >/dev/null
/opt/focus/bin/pip install -q 'opencv-python-headless>=4.8,<5' numpy
[ -s /opt/focus/yunet.onnx ] || curl -sSL -m 60 -o /opt/focus/yunet.onnx \
  https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx || true
python3 -c "import sys;d=open('/opt/focus/yunet.onnx','rb').read(200);sys.exit(0 if b'{' not in d[:2] and len(d)>100 else 1)" || { rm -f /opt/focus/yunet.onnx; echo 'yunet download failed (Haar fallback)'; }
/opt/focus/bin/python -c "import cv2,os; print('FOCUS_OK', cv2.__version__, 'yunet' if os.path.exists('/opt/focus/yunet.onnx') else 'haar')"
