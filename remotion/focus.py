#!/usr/bin/env python3
"""Where is the subject of a photo? -> {"<path>": {"x": 0..1, "y": 0..1, "face": bool}} on stdout.

Used by make_props.py so covers / carousel slides crop real photos around the person (or the main object)
instead of the geometric centre. Runs in its own venv (/opt/focus, opencv-python-headless) - see
engine/setup_focus.sh. Faces first (YuNet, else Haar frontal + profile; all faces in the shot); no face -> centre of the
strongest detail (edges), which finds a chair on a plain wall or hands at the bottom of a sky shot.

    /opt/focus/bin/python focus.py img1.jpg img2.png ...
"""
import json, sys
import cv2
import numpy as np

import os
YUNET = '/opt/focus/yunet.onnx'   # OpenCV Zoo YuNet face detector (MIT), downloaded by engine/setup_focus.sh
_hc = getattr(getattr(cv2, 'data', None), 'haarcascades', '')
CASC = [c for c in (cv2.CascadeClassifier(_hc + n) for n in ('haarcascade_frontalface_default.xml', 'haarcascade_profileface.xml')
                    if _hc and os.path.exists(_hc + n)) if not c.empty()]


def box_center(found, w, h):
    big = max(f[2] * f[3] for f in found)
    found = [f for f in found if f[2] * f[3] >= big * 0.25]   # drop tiny false hits in the background
    x0 = min(f[0] for f in found); y0 = min(f[1] for f in found)
    x1 = max(f[0] + f[2] for f in found); y1 = max(f[1] + f[3] for f in found)
    return (x0 + x1) / 2 / w, (y0 + y1) / 2 / h


def faces_yunet(bgr):
    if not (os.path.exists(YUNET) and hasattr(cv2, 'FaceDetectorYN')):
        return None
    h, w = bgr.shape[:2]
    det = cv2.FaceDetectorYN.create(YUNET, '', (w, h), 0.75, 0.3, 50)
    _, res = det.detect(bgr)
    if res is None or not len(res):
        return None
    return box_center([(float(r[0]), float(r[1]), float(r[2]), float(r[3])) for r in res], w, h)


def faces(gray):
    if not CASC:
        return None
    h, w = gray.shape
    mn = max(24, int(min(h, w) * 0.05))
    found = []
    for k, c in enumerate(CASC):
        for flip in ((False, True) if k == 1 else (False,)):
            g = cv2.flip(gray, 1) if flip else gray
            for (x, y, fw, fh) in c.detectMultiScale(g, scaleFactor=1.1, minNeighbors=6, minSize=(mn, mn)):
                if flip:
                    x = w - x - fw
                found.append((int(x), int(y), int(fw), int(fh)))
    if not found:
        return None
    return box_center(found, w, h)


def detail(gray):
    g = cv2.GaussianBlur(cv2.resize(gray, (256, max(1, int(256 * gray.shape[0] / gray.shape[1])))), (5, 5), 0)
    m = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    m[:3, :] = 0; m[-3:, :] = 0; m[:, :3] = 0; m[:, -3:] = 0      # ignore frame edges
    m = m ** 2
    s = float(m.sum())
    if s <= 0:
        return 0.5, 0.5
    ys, xs = np.indices(m.shape)
    return float((m * xs).sum() / s / m.shape[1]), float((m * ys).sum() / s / m.shape[0])


out = {}
for p in sys.argv[1:]:
    try:
        bgr = cv2.imread(p, cv2.IMREAD_COLOR)
        if bgr is None:
            continue
        sc = 640 / max(bgr.shape[:2])
        if sc < 1:
            bgr = cv2.resize(bgr, (int(bgr.shape[1] * sc), int(bgr.shape[0] * sc)))
        img = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        f = faces_yunet(bgr) or faces(cv2.equalizeHist(img))
        x, y = f if f else detail(img)
        out[p] = {'x': round(min(max(x, 0), 1), 3), 'y': round(min(max(y, 0), 1), 3), 'face': bool(f)}
    except Exception:
        pass
print(json.dumps(out))
