#!/usr/bin/env python3
"""Cam visual cortex — object identification that actually runs.

Two complementary paths feed one shared "what Cam sees" state:

1. **Browser detector (best)** — when Aaron's machine is online, the
   live UI loads TensorFlow.js coco-ssd (80 real object classes) and
   posts labeled detections to `/api/vision/detections`.
2. **Local visual cortex (always works, zero deps beyond numpy)** — the
   UI downsamples camera frames to raw RGBA and posts them to
   `/api/vision/frame`; this module segments salient regions and
   identifies them by color, shape, size, and position (honest labels
   like "large dark rectangular object, center" or "skin-tone region —
   person candidate").

The brain answers "what do you see?" from whichever path reported last.
"""

from __future__ import annotations

import base64
import binascii
import threading
from collections import deque
from datetime import datetime, timezone

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None  # type: ignore


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- color naming ------------------------------------------------------------

_PALETTE = [
    ("black", (18, 18, 18)), ("white", (240, 240, 240)), ("gray", (128, 128, 128)),
    ("red", (200, 40, 40)), ("orange", (240, 140, 40)), ("yellow", (230, 220, 60)),
    ("green", (60, 170, 80)), ("teal", (50, 170, 170)), ("blue", (50, 90, 200)),
    ("purple", (140, 70, 180)), ("pink", (230, 130, 180)), ("brown", (120, 80, 50)),
    ("beige", (205, 185, 155)),
]


def color_name(rgb) -> str:
    r, g, b = (float(v) for v in rgb)
    best, dist = "gray", 1e18
    for name, (pr, pg, pb) in _PALETTE:
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < dist:
            best, dist = name, d
    return best


def is_skin_tone(rgb) -> bool:
    r, g, b = (float(v) for v in rgb)
    return r > 90 and g > 45 and b > 25 and r > g > b and (r - b) > 12 and (r - g) < 110


# -- segmentation ---------------------------------------------------------------

def _label_regions(mask):
    """Two-pass-ish BFS connected components on a small boolean grid."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    current = 0
    stack: list[tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] and labels[y, x] == 0:
                current += 1
                stack.append((y, x))
                labels[y, x] = current
                while stack:
                    cy, cx = stack.pop()
                    for ny, nx in ((cy-1, cx), (cy+1, cx), (cy, cx-1), (cy, cx+1)):
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and labels[ny, nx] == 0:
                            labels[ny, nx] = current
                            stack.append((ny, nx))
    return labels, current


def _position(cx: float, cy: float) -> str:
    horiz = "left" if cx < 0.34 else ("right" if cx > 0.66 else "center")
    vert = "top" if cy < 0.34 else ("bottom" if cy > 0.66 else "")
    return f"{vert} {horiz}".strip()


def _shape_word(fill: float, aspect: float) -> str:
    if fill > 0.78:
        base = "rectangular"
    elif fill > 0.55:
        base = "rounded"
    else:
        base = "irregular"
    if aspect > 2.2:
        return f"wide {base}"
    if aspect < 0.45:
        return f"tall {base}"
    return base


def analyze_rgba(raw: bytes, width: int, height: int) -> dict:
    """Identify salient objects in a raw RGBA frame. Returns scene + objects."""
    if np is None:
        return {"ok": False, "error": "numpy_unavailable", "objects": []}
    expected = width * height * 4
    if width <= 0 or height <= 0 or len(raw) < expected:
        return {"ok": False, "error": "bad_frame_dims", "objects": []}
    arr = np.frombuffer(raw[:expected], dtype=np.uint8).reshape(height, width, 4)[:, :, :3].astype(np.float32)

    # downsample to a small analysis grid
    ty, tx = 60, 80
    sy = max(1, height // ty)
    sx = max(1, width // tx)
    small = arr[::sy, ::sx]
    h, w = small.shape[:2]

    mean_color = small.reshape(-1, 3).mean(axis=0)
    brightness = float(mean_color.mean())
    # saliency: distance from the global mean color (background suppress)
    dist = np.sqrt(((small - mean_color) ** 2).sum(axis=2))
    thresh = max(34.0, float(dist.mean() + dist.std() * 0.9))
    mask = dist > thresh

    labels, count = _label_regions(mask)
    objects: list[dict] = []
    total_px = h * w
    for i in range(1, count + 1):
        region = labels == i
        area = int(region.sum())
        if area < total_px * 0.01:  # ignore specks
            continue
        ys, xs = np.nonzero(region)
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        bw, bh = (x1 - x0 + 1), (y1 - y0 + 1)
        fill = area / float(bw * bh)
        aspect = bw / float(bh)
        rgb = small[region].mean(axis=0)
        cname = color_name(rgb)
        size_frac = area / float(total_px)
        size_word = "large" if size_frac > 0.18 else ("medium" if size_frac > 0.05 else "small")
        pos = _position((x0 + x1) / 2.0 / w, (y0 + y1) / 2.0 / h)
        if is_skin_tone(rgb) and size_frac > 0.02:
            label = "skin-tone region — person candidate"
        else:
            label = f"{size_word} {cname} {_shape_word(fill, aspect)} object"
        objects.append({
            "label": label,
            "color": cname,
            "position": pos,
            "area_frac": round(size_frac, 3),
            "bbox": [round(x0 / w, 3), round(y0 / h, 3), round(bw / w, 3), round(bh / h, 3)],
            "score": round(min(0.95, 0.4 + size_frac * 2), 2),
        })
    objects.sort(key=lambda o: -o["area_frac"])
    scene_word = "bright" if brightness > 170 else ("dim" if brightness < 70 else "normal light")
    return {
        "ok": True,
        "source": "local_cortex",
        "at": utc_now(),
        "scene": {
            "brightness": round(brightness, 1),
            "light": scene_word,
            "dominant_color": color_name(mean_color),
            "salient_regions": len(objects),
        },
        "objects": objects[:12],
    }


def analyze_rgba_b64(b64: str, width: int, height: int) -> dict:
    try:
        raw = base64.b64decode(b64)
    except (binascii.Error, ValueError):
        return {"ok": False, "error": "bad_base64", "objects": []}
    return analyze_rgba(raw, width, height)


# -- shared "what Cam sees" state ------------------------------------------------

class VisionState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest: dict | None = None
        self._history: deque[dict] = deque(maxlen=50)

    def ingest_detections(self, objects: list[dict], source: str = "cocossd") -> dict:
        clean = []
        for o in objects[:20]:
            label = str(o.get("label") or o.get("class") or "object")[:60]
            clean.append({
                "label": label,
                "score": round(float(o.get("score") or 0), 2),
                "bbox": o.get("bbox"),
            })
        snap = {"at": utc_now(), "source": source, "objects": clean}
        with self._lock:
            self._latest = snap
            self._history.append(snap)
        return snap

    def ingest_frame_analysis(self, analysis: dict) -> dict:
        snap = {"at": analysis.get("at") or utc_now(), "source": "local_cortex",
                "objects": analysis.get("objects") or [], "scene": analysis.get("scene")}
        with self._lock:
            self._latest = snap
            self._history.append(snap)
        return snap

    def latest(self) -> dict | None:
        with self._lock:
            return dict(self._latest) if self._latest else None

    def history(self, limit: int = 20) -> list[dict]:
        with self._lock:
            return list(self._history)[-limit:]
