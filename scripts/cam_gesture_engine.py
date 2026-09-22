#!/usr/bin/env python3
"""Cam hand-gesture engine — one algorithm meshed from Aaron's three repos.

Input: a stream of 21-point hand landmarks per frame (MediaPipe layout) from
any camera source — the companion PWA, a Mac webcam, the Pupil world camera.
Output: ``cam_gestures.Segment`` values (``pose:motion:duration:conf:hands``)
that ``GestureResolver`` turns into intents.

What each repo contributes
--------------------------
* ``integrations/hand-gesture-mediapipe`` (Kazuhito00) — landmark normalization
  (relative to wrist, scaled by max-abs), the keypoint classifier
  (Open / Close / Pointer) and the 16-point fingertip **point-history**
  classifier (Stop / Clockwise / Counter Clockwise / Move). Both are re-trained
  here as k-NN over the repo's own CSV samples so no TensorFlow is needed.
* ``integrations/hand-gesture-recognition`` (Ha0Tang) — **key-frame
  extraction**: a per-frame signal, its local extrema plus the endpoints, kept
  as the frames that carry the motion. Used to describe a movement by a handful
  of key frames instead of every jittery sample.
* ``integrations/hagrid`` (HaGRIDv2) — the 33-class label set. External
  detector labels (HaGRID YOLO / ResNet, MediaPipe canned gestures) enter the
  same fusion through ``repos.hagrid.pose_map`` in ``gestures.json``.

Cam adds geometric finger rules for every pose in the vocabulary, a per-hand
segmenter (still / moving phases, engagement dwell, two-hand pairing) and the
fusion that votes between rules, k-NN, Aaron's taught prototypes, and external
labels.

Coordinate convention: landmarks are in **screen space as Aaron sees them**
(selfie-mirrored, x right, y down, 0..1) with ``handedness`` = the hand he is
actually using. Sources that run on an un-mirrored frame set ``mirror=True``
and the engine flips x.
"""
from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import cam_gestures as cg

ROOT = Path(__file__).resolve().parents[1]
REPO_MP = ROOT / "integrations" / "hand-gesture-mediapipe"
KEYPOINT_CSV = REPO_MP / "model" / "keypoint_classifier" / "keypoint.csv"
KEYPOINT_LABELS = REPO_MP / "model" / "keypoint_classifier" / "keypoint_classifier_label.csv"
HISTORY_CSV = REPO_MP / "model" / "point_history_classifier" / "point_history.csv"
HISTORY_LABELS = REPO_MP / "model" / "point_history_classifier" / "point_history_classifier_label.csv"
PROTOTYPES_PATH = ROOT / "data" / "gestures" / "prototypes.json"

# MediaPipe hand landmark indices
WRIST = 0
THUMB = (1, 2, 3, 4)
INDEX = (5, 6, 7, 8)
MIDDLE = (9, 10, 11, 12)
RING = (13, 14, 15, 16)
PINKY = (17, 18, 19, 20)
FINGERS = (INDEX, MIDDLE, RING, PINKY)
PALM = (0, 5, 9, 13, 17)

HISTORY_LEN = 16
DEFAULT_FRAME = (960, 540)

# Pose families: a coarse external label votes for the fine pose the rules saw.
FAMILIES = {
    "open": {"open_palm", "back_of_hand", "palm_down", "palm_up", "four"},
    "fist": {"closed_fist"},
    "point": {"pointing_up", "pointing_away", "mute"},
}


def _family_of(pose: str) -> str | None:
    for fam, members in FAMILIES.items():
        if pose in members:
            return fam
    return None


# --------------------------------------------------------------------------
# Observations
# --------------------------------------------------------------------------


@dataclass
class HandFrame:
    """One detected hand in one frame."""

    landmarks: list[tuple[float, float, float]]
    handedness: str = "Right"
    score: float = 1.0
    labels: dict[str, tuple[str, float]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict, mirror: bool = False) -> "HandFrame":
        pts = []
        for p in d.get("landmarks") or []:
            if isinstance(p, dict):
                x, y, z = float(p.get("x", 0)), float(p.get("y", 0)), float(p.get("z", 0))
            else:
                x, y = float(p[0]), float(p[1])
                z = float(p[2]) if len(p) > 2 else 0.0
            if mirror:
                x = 1.0 - x
            pts.append((x, y, z))
        labels = {}
        for src, val in (d.get("labels") or {}).items():
            if isinstance(val, (list, tuple)) and val:
                labels[src] = (str(val[0]), float(val[1]) if len(val) > 1 else 0.8)
            elif isinstance(val, dict) and val.get("label"):
                labels[src] = (str(val["label"]), float(val.get("score", 0.8)))
            elif isinstance(val, str):
                labels[src] = (val, 0.8)
        return cls(pts, str(d.get("handedness") or "Right"), float(d.get("score", 1.0)), labels)

    def to_dict(self) -> dict:
        return {
            "landmarks": [[round(x, 4), round(y, 4), round(z, 4)] for x, y, z in self.landmarks],
            "handedness": self.handedness,
            "score": round(self.score, 3),
            "labels": {k: [v[0], round(v[1], 3)] for k, v in self.labels.items()},
        }


@dataclass
class Observation:
    """All hands seen in one camera frame."""

    t_ms: int
    hands: list[HandFrame] = field(default_factory=list)
    width: int = DEFAULT_FRAME[0]
    height: int = DEFAULT_FRAME[1]
    device: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> "Observation":
        mirror = bool(d.get("mirror", False))
        hands = [HandFrame.from_dict(h, mirror=mirror) for h in (d.get("hands") or [])]
        hands = [h for h in hands if len(h.landmarks) == 21]
        return cls(
            int(d.get("t_ms", 0)),
            hands,
            int(d.get("w") or d.get("width") or DEFAULT_FRAME[0]),
            int(d.get("h") or d.get("height") or DEFAULT_FRAME[1]),
            d.get("device"),
        )

    def to_dict(self) -> dict:
        return {
            "t_ms": self.t_ms,
            "w": self.width,
            "h": self.height,
            "device": self.device,
            "hands": [h.to_dict() for h in self.hands],
        }


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------


def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def palm_center(lm) -> tuple[float, float]:
    xs = [lm[i][0] for i in PALM]
    ys = [lm[i][1] for i in PALM]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def hand_scale(lm) -> float:
    """Palm length (wrist → middle MCP) — size-invariant unit for thresholds."""
    return max(dist(lm[WRIST], lm[MIDDLE[0]]), 1e-6)


def bbox_size(lm) -> float:
    xs = [p[0] for p in lm]
    ys = [p[1] for p in lm]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


def finger_extension(lm, finger) -> float:
    """> 1.15 extended, < 0.95 curled (tip vs PIP distance from the wrist)."""
    mcp, pip, _dip, tip = finger
    return dist(lm[tip], lm[WRIST]) / max(dist(lm[pip], lm[WRIST]), 1e-6)


def finger_states(lm) -> dict:
    ext = {}
    for name, f in zip(("index", "middle", "ring", "pinky"), FINGERS):
        r = finger_extension(lm, f)
        ext[name] = "ext" if r > 1.15 else "curl" if r < 0.95 else "half"
    # Thumb: tip further from the pinky MCP than the IP joint, and away from the palm.
    thumb_out = dist(lm[THUMB[3]], lm[PINKY[0]]) > dist(lm[THUMB[2]], lm[PINKY[0]]) * 1.05
    thumb_far = dist(lm[THUMB[3]], lm[INDEX[0]]) > 0.55 * hand_scale(lm)
    ext["thumb"] = "ext" if (thumb_out and thumb_far) else "curl"
    return ext


def palm_facing(lm, handedness: str) -> str:
    """'palm' or 'back' toward the camera, from the index/pinky MCP winding."""
    w, i, p = lm[WRIST], lm[INDEX[0]], lm[PINKY[0]]
    cross = (i[0] - w[0]) * (p[1] - w[1]) - (i[1] - w[1]) * (p[0] - w[0])
    right = handedness.lower().startswith("r")
    # Screen space (selfie-mirrored), right hand palm to camera: index is
    # screen-left of pinky with fingers up → positive cross.
    return "palm" if (cross > 0) == right else "back"


def pointing_angle(lm) -> float:
    """Direction of the index finger in degrees; 0 = right, -90 = up (y down)."""
    a, b = lm[INDEX[0]], lm[INDEX[3]]
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def fingers_up(lm) -> bool:
    """Fingers pointing up on screen (tips above MCPs)."""
    return sum(1 for f in FINGERS if lm[f[3]][1] < lm[f[0]][1]) >= 3


def depth_tilt(lm) -> float:
    """Mean fingertip z minus wrist z (MediaPipe z: smaller = closer). Negative → tips toward camera."""
    tips = [lm[f[3]][2] for f in FINGERS]
    return sum(tips) / len(tips) - lm[WRIST][2]


# --------------------------------------------------------------------------
# Pose head — geometric rules over the vocabulary poses
# --------------------------------------------------------------------------


class RulePoseHead:
    """Deterministic finger-rule classifier for every one-hand pose in gestures.json."""

    def classify(self, hand: HandFrame) -> tuple[str, float]:
        lm = hand.landmarks
        st = finger_states(lm)
        ext = [n for n in ("index", "middle", "ring", "pinky") if st[n] == "ext"]
        curl = [n for n in ("index", "middle", "ring", "pinky") if st[n] == "curl"]
        thumb = st["thumb"] == "ext"
        scale = hand_scale(lm)
        pinch_gap = dist(lm[THUMB[3]], lm[INDEX[3]])
        n_ext = len(ext)

        ring_out = dist(lm[INDEX[3]], palm_center(lm)) > 0.6 * scale
        if pinch_gap < 0.35 * scale and "index" not in ext and ring_out:
            others = [n for n in ("middle", "ring", "pinky") if st[n] == "ext"]
            if len(others) == 3:
                return "ok_sign", 0.9
            if len(others) == 0:
                return "pinch", 0.85
        if n_ext == 4:
            if not thumb:
                return "four", 0.8
            facing = palm_facing(lm, hand.handedness)
            tilt = depth_tilt(lm)
            if not fingers_up(lm) and abs(tilt) > 0.04:
                return ("palm_down", 0.7) if facing == "back" else ("palm_up", 0.7)
            if facing == "back":
                return "back_of_hand", 0.8
            return "open_palm", 0.92
        if n_ext == 0 and len(curl) >= 3:
            if thumb:
                # thumb up / down by thumb direction
                dy = lm[THUMB[3]][1] - lm[THUMB[1]][1]
                dx = abs(lm[THUMB[3]][0] - lm[THUMB[1]][0])
                if dy < -0.5 * scale and abs(dy) > dx:
                    return "thumb_up", 0.9
                if dy > 0.5 * scale and abs(dy) > dx:
                    return "thumb_down", 0.9
            return "closed_fist", 0.9
        if ext == ["index"]:
            ang = pointing_angle(lm)
            tilt = lm[INDEX[3]][2] - lm[INDEX[0]][2]
            if tilt < -0.06 and not (-120 < ang < -60):
                return "pointing_away", 0.8
            if -125 <= ang <= -55:
                return "pointing_up", 0.9
            return "pointing_away", 0.7
        if ext == ["index", "middle"]:
            return "victory", 0.9
        if ext == ["index", "middle", "ring"]:
            return "three", 0.85
        if set(ext) == {"index", "pinky"} and thumb:
            return "i_love_you", 0.9
        return "none", 0.5


class TwoHandRuleHead:
    """Geometric rules for the two-hand HaGRID poses (take_picture / timeout / hand_heart)."""

    def classify(self, a: HandFrame, b: HandFrame) -> tuple[str, float] | None:
        la, lb = a.landmarks, b.landmarks
        sa, sb = finger_states(la), finger_states(lb)
        scale = (hand_scale(la) + hand_scale(lb)) / 2
        wrist_gap = dist(la[WRIST], lb[WRIST])

        def l_shape(st):
            return st["thumb"] == "ext" and st["index"] == "ext" and all(st[n] != "ext" for n in ("middle", "ring", "pinky"))

        if l_shape(sa) and l_shape(sb) and wrist_gap < 3.5 * scale:
            return "take_picture", 0.8

        def open_(st):
            return sum(1 for n in ("index", "middle", "ring", "pinky") if st[n] == "ext") == 4

        if open_(sa) and open_(sb):
            # Timeout: one hand horizontal (fingers sideways) with its palm on the other's fingertips.
            for top, bottom in ((la, lb), (lb, la)):
                ang_top = abs(pointing_angle(top))
                horizontal = ang_top < 35 or ang_top > 145
                vertical = -125 <= pointing_angle(bottom) <= -55
                touch = dist(palm_center(top), bottom[MIDDLE[3]]) < 1.1 * scale
                if horizontal and vertical and touch:
                    return "timeout", 0.8
        # Hand heart: both thumb tips close, both index tips close, hands mirrored.
        if dist(la[THUMB[3]], lb[THUMB[3]]) < 0.6 * scale and dist(la[INDEX[3]], lb[INDEX[3]]) < 0.6 * scale and wrist_gap > 1.2 * scale:
            if la[INDEX[3]][1] < la[THUMB[3]][1] and lb[INDEX[3]][1] < lb[THUMB[3]][1]:
                return "hand_heart", 0.75
        return None


# --------------------------------------------------------------------------
# Kazuhito00 normalization + k-NN heads (trained from the repo CSVs)
# --------------------------------------------------------------------------


def preprocess_landmarks(lm, width: int, height: int) -> list[float]:
    """Kazuhito00 ``pre_process_landmark``: pixel coords relative to the wrist, max-abs scaled."""
    bx, by = lm[WRIST][0] * width, lm[WRIST][1] * height
    flat: list[float] = []
    for x, y, _z in lm:
        flat.append(x * width - bx)
        flat.append(y * height - by)
    m = max(abs(v) for v in flat) or 1.0
    return [v / m for v in flat]


def preprocess_history(points: list[tuple[float, float]], width: int, height: int) -> list[float]:
    """Kazuhito00 ``pre_process_point_history``: fingertip pixels relative to the first, / frame size."""
    if not points:
        return []
    bx, by = points[0]
    flat: list[float] = []
    for x, y in points:
        flat.append((x - bx) / width)
        flat.append((y - by) / height)
    return flat


def resample(points: list[tuple[float, float]], n: int = HISTORY_LEN) -> list[tuple[float, float]]:
    if not points:
        return []
    if len(points) == 1:
        return points * n
    out = []
    for i in range(n):
        pos = i * (len(points) - 1) / (n - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, len(points) - 1)
        f = pos - lo
        out.append((points[lo][0] * (1 - f) + points[hi][0] * f, points[lo][1] * (1 - f) + points[hi][1] * f))
    return out


class KNN:
    """Small pure-Python k-NN with class centroids; enough for 42/32-dim landmark vectors."""

    def __init__(self, k: int = 7) -> None:
        self.k = k
        self.samples: list[tuple[int, list[float]]] = []
        self.centroids: dict[int, list[float]] = {}
        self.labels: list[str] = []

    @property
    def ready(self) -> bool:
        return bool(self.samples)

    def fit(self, rows: Iterable[tuple[int, list[float]]], labels: list[str], stride: int = 1) -> "KNN":
        self.labels = labels
        acc: dict[int, list[float]] = {}
        cnt: Counter = Counter()
        for i, (lab, vec) in enumerate(rows):
            if i % stride == 0:
                self.samples.append((lab, vec))
            if lab not in acc:
                acc[lab] = [0.0] * len(vec)
            a = acc[lab]
            for j, v in enumerate(vec):
                a[j] += v
            cnt[lab] += 1
        self.centroids = {lab: [v / cnt[lab] for v in vec] for lab, vec in acc.items()}
        return self

    @staticmethod
    def _d2(a: list[float], b: list[float]) -> float:
        return sum((x - y) * (x - y) for x, y in zip(a, b))

    def predict(self, vec: list[float]) -> tuple[str, float, float]:
        """(label, vote_share, nearest_distance)."""
        if not self.samples or not vec:
            return "", 0.0, math.inf
        nearest = sorted(((self._d2(vec, s), lab) for lab, s in self.samples), key=lambda t: t[0])[: self.k]
        votes = Counter(lab for _, lab in nearest)
        lab, n = votes.most_common(1)[0]
        return self.labels[lab] if lab < len(self.labels) else str(lab), n / len(nearest), math.sqrt(nearest[0][0])


def _read_labels(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [l.strip() for l in path.read_text(encoding="utf-8-sig").splitlines() if l.strip()]


def _read_csv(path: Path) -> list[tuple[int, list[float]]]:
    rows: list[tuple[int, list[float]]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for r in csv.reader(f):
            if not r:
                continue
            try:
                rows.append((int(r[0]), [float(v) for v in r[1:]]))
            except ValueError:
                continue
    return rows


def load_keypoint_knn(stride: int = 6) -> KNN:
    return KNN().fit(_read_csv(KEYPOINT_CSV), _read_labels(KEYPOINT_LABELS), stride=stride)


def load_history_knn(stride: int = 6) -> KNN:
    return KNN().fit(_read_csv(HISTORY_CSV), _read_labels(HISTORY_LABELS), stride=stride)


class PrototypeStore:
    """Aaron-taught pose prototypes (normalized 42-vectors) — data/gestures/prototypes.json."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PROTOTYPES_PATH
        self.protos: dict[str, list[list[float]]] = {}
        if self.path.exists():
            try:
                doc = json.loads(self.path.read_text(encoding="utf-8"))
                self.protos = {k: v for k, v in (doc.get("poses") or {}).items() if isinstance(v, list)}
            except json.JSONDecodeError:
                self.protos = {}

    def add(self, pose: str, vec: list[float], *, by: str = "Aaron", write: bool = True) -> int:
        if by != "Aaron":
            raise PermissionError("only Aaron teaches gesture prototypes")
        self.protos.setdefault(pose, []).append([round(v, 5) for v in vec])
        if write:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps({"taught_by": "Aaron", "poses": self.protos}, indent=1) + "\n", encoding="utf-8"
            )
        return len(self.protos[pose])

    def nearest(self, vec: list[float]) -> tuple[str, float] | None:
        best: tuple[str, float] | None = None
        for pose, vecs in self.protos.items():
            for p in vecs:
                if len(p) != len(vec):
                    continue
                d = math.sqrt(KNN._d2(vec, p))
                if best is None or d < best[1]:
                    best = (pose, d)
        return best


# --------------------------------------------------------------------------
# Ha0Tang key frames
# --------------------------------------------------------------------------


def key_frames(signal: list[float], max_frames: int = 5) -> list[int]:
    """Key-frame indices: endpoints + local extrema of the signal, thinned to the most prominent.

    Mirrors ``key_frames_extraction.m``: peaks and valleys of a per-frame signal
    (image entropy there; landmark motion energy here) plus the first and last
    frame, then reduced to ``max_frames``.
    """
    n = len(signal)
    if n == 0:
        return []
    if n <= max_frames:
        return list(range(n))
    idx = {0, n - 1}
    prominence: dict[int, float] = {}
    for i in range(1, n - 1):
        if (signal[i] > signal[i - 1] and signal[i] >= signal[i + 1]) or (signal[i] < signal[i - 1] and signal[i] <= signal[i + 1]):
            prominence[i] = abs(signal[i] - (signal[i - 1] + signal[i + 1]) / 2)
    for i, _p in sorted(prominence.items(), key=lambda kv: -kv[1]):
        if len(idx) >= max_frames:
            break
        idx.add(i)
    return sorted(idx)


# --------------------------------------------------------------------------
# Motion head
# --------------------------------------------------------------------------


@dataclass
class Track:
    """One hand across the frames of a segmenter run."""

    times: list[int] = field(default_factory=list)
    centers: list[tuple[float, float]] = field(default_factory=list)
    tips: list[tuple[float, float]] = field(default_factory=list)
    sizes: list[float] = field(default_factory=list)
    frames: list[HandFrame] = field(default_factory=list)

    def add(self, t_ms: int, hand: HandFrame) -> None:
        lm = hand.landmarks
        self.times.append(t_ms)
        self.centers.append(palm_center(lm))
        self.tips.append((lm[INDEX[3]][0], lm[INDEX[3]][1]))
        self.sizes.append(hand_scale(lm))  # palm length: invariant to finger curl, so a fist is not a 'pull_out'
        self.frames.append(hand)

    def __len__(self) -> int:
        return len(self.times)

    def split_tail(self, k: int) -> "Track":
        """Remove and return the last ``k`` frames (they belong to the next run)."""
        k = max(0, min(k, len(self.times) - 1))
        tail = Track(self.times[-k:], self.centers[-k:], self.tips[-k:], self.sizes[-k:], self.frames[-k:]) if k else Track()
        if k:
            del self.times[-k:], self.centers[-k:], self.tips[-k:], self.sizes[-k:], self.frames[-k:]
        return tail

    @property
    def duration_ms(self) -> int:
        return (self.times[-1] - self.times[0]) if self.times else 0


def _angle_sweep(points: list[tuple[float, float]]) -> float:
    """Total signed angle (degrees) traced around the centroid; positive = clockwise on screen (y down)."""
    if len(points) < 4:
        return 0.0
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    total = 0.0
    prev = math.atan2(points[0][1] - cy, points[0][0] - cx)
    for x, y in points[1:]:
        a = math.atan2(y - cy, x - cx)
        d = a - prev
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        total += d
        prev = a
    return math.degrees(total)


def _reversals(values: list[float], min_amp: float) -> int:
    """Direction reversals along one axis with excursions above ``min_amp``."""
    if len(values) < 3:
        return 0
    rev = 0
    direction = 0
    anchor = values[0]
    for v in values[1:]:
        d = v - anchor
        if abs(d) < min_amp:
            continue
        s = 1 if d > 0 else -1
        if direction and s != direction:
            rev += 1
        direction = s
        anchor = v
    return rev


class MotionHead:
    """Geometry on Ha0Tang key frames, fused with Kazuhito00's point-history k-NN."""

    def __init__(self, history_knn: KNN | None = None, motion_map: dict | None = None) -> None:
        self.knn = history_knn
        self.motion_map = motion_map or {}

    def classify(self, tr: Track, width: int, height: int, *, exited: bool = False, hands: int = 1) -> tuple[str, float, dict]:
        n = len(tr)
        if n == 0:
            return "hold", 0.5, {}
        dur = tr.duration_ms
        xs = [c[0] for c in tr.centers]
        ys = [c[1] for c in tr.centers]
        # Ha0Tang: describe the run by its key frames of motion energy.
        energy = [0.0] + [dist(tr.centers[i], tr.centers[i - 1]) for i in range(1, n)]
        kf = key_frames(energy)
        kx = [xs[i] for i in kf]
        ky = [ys[i] for i in kf]
        dx = kx[-1] - kx[0]
        dy = ky[-1] - ky[0]
        exc_x = max(xs) - min(xs)
        exc_y = max(ys) - min(ys)
        path = sum(energy)
        k = max(1, min(2, n // 4))
        size0 = sum(tr.sizes[:k]) / k
        size1 = sum(tr.sizes[-k:]) / k
        ratio = size1 / max(size0, 1e-6)
        sweep = _angle_sweep(tr.tips)
        rev_x = _reversals(xs, 0.04)
        detail = {
            "dx": round(dx, 3), "dy": round(dy, 3), "exc_x": round(exc_x, 3), "exc_y": round(exc_y, 3),
            "path": round(path, 3), "size_ratio": round(ratio, 2), "sweep_deg": round(sweep, 1),
            "reversals_x": rev_x, "key_frames": kf, "duration_ms": dur, "exited": exited,
        }

        knn_label = ""
        knn_share = 0.0
        if self.knn and self.knn.ready and n >= 4:
            pts = resample([(x * width, y * height) for x, y in tr.tips])
            knn_label, knn_share, _ = self.knn.predict(preprocess_history(pts, width, height))
            detail["point_history"] = [knn_label, round(knn_share, 2)]
        knn_motion = self.motion_map.get(knn_label, "")

        motion, conf = self._geometric(dx, dy, exc_x, exc_y, path, ratio, sweep, rev_x, dur, exited, hands, tr)
        # Fusion: Kazuhito00's classifier agrees → lift; disagrees on a circle → trust the sweep only if strong.
        if knn_motion:
            agree = (
                (motion == "hold" and knn_motion == "hold")
                or (motion in ("circle_cw", "circle_ccw") and knn_motion == motion)
                or (motion not in ("hold", "circle_cw", "circle_ccw") and knn_motion == "translate")
            )
            if agree:
                conf = min(0.99, conf + 0.15 * knn_share)
            elif knn_motion in ("circle_cw", "circle_ccw") and motion == "translate" and abs(sweep) >= 200:
                motion, conf = knn_motion, 0.7
            else:
                conf = max(0.4, conf - 0.1)
        return motion, round(conf, 3), detail

    @staticmethod
    def _geometric(dx, dy, exc_x, exc_y, path, ratio, sweep, rev_x, dur, exited, hands, tr: Track) -> tuple[str, float]:
        if hands == 2:
            return "hold", 0.8
        if exited and path > 0.05:
            return "translate_out", 0.85
        if abs(sweep) >= 300 and path > 0.25 and dur <= 2000 and exc_x >= 0.06 and exc_y >= 0.06:
            return ("circle_cw" if sweep > 0 else "circle_ccw"), 0.85
        if rev_x >= 3 and exc_x > 0.06 and dur <= 1600:
            return "wave", 0.85
        if ratio >= 1.6 and dur <= 900:
            return "push_in", 0.85
        if ratio <= 0.6 and dur <= 900:
            return "pull_out", 0.85
        if abs(dx) >= 0.25 and abs(dx) > abs(dy):
            return ("swipe_right" if dx > 0 else "swipe_left"), 0.85
        if abs(dy) >= 0.20 and abs(dy) > abs(dx):
            return ("raise" if dy < 0 else "lower"), 0.85
        still = exc_x < 0.04 and exc_y < 0.04
        if still and 0.75 <= ratio <= 1.33:
            return "hold", 0.9
        if still and ratio >= 1.35 and dur <= 900:
            return "push_in", 0.7
        if still and ratio <= 0.74 and dur <= 900:
            return "pull_out", 0.7
        # Flick: quick excursion that comes back.
        if dur <= 500 and max(exc_x, exc_y) >= 0.05 and math.hypot(dx, dy) < 0.6 * max(exc_x, exc_y):
            xs = [c[0] for c in tr.centers]
            ys = [c[1] for c in tr.centers]
            if exc_x >= exc_y:
                first = xs[len(xs) // 2] - xs[0]
                return ("flick_right" if first > 0 else "flick_left"), 0.8
            first = ys[len(ys) // 2] - ys[0]
            return ("flick_down" if first > 0 else "flick_up"), 0.8
        if path > 0.08:
            return "translate", 0.6
        return "hold", 0.7


def two_hand_motion(a: Track, b: Track) -> tuple[str, float]:
    """spread_apart / bring_together from the wrist distance ratio, else hold."""
    n = min(len(a), len(b))
    if n < 3:
        return "hold", 0.7
    d0 = sum(dist(a.frames[i].landmarks[WRIST], b.frames[i].landmarks[WRIST]) for i in range(max(1, n // 4))) / max(1, n // 4)
    d1 = sum(dist(a.frames[-i - 1].landmarks[WRIST], b.frames[-i - 1].landmarks[WRIST]) for i in range(max(1, n // 4))) / max(1, n // 4)
    r = d1 / max(d0, 1e-6)
    if r >= 1.5:
        return "spread_apart", 0.85
    if r <= 0.66:
        return "bring_together", 0.85
    return "hold", 0.85


# --------------------------------------------------------------------------
# Pose fusion
# --------------------------------------------------------------------------


class PoseFusion:
    """Vote between rules, Kazuhito00 k-NN, Aaron's prototypes, and external labels."""

    W_RULE, W_KNN, W_PROTO, W_EXT = 1.0, 0.6, 1.2, 0.9

    def __init__(self, vocab: dict, keypoint_knn: KNN | None, prototypes: PrototypeStore | None) -> None:
        self.rules = RulePoseHead()
        self.knn = keypoint_knn
        self.protos = prototypes
        repos = vocab.get("repos") or {}
        self.keypoint_map = (repos.get("hand-gesture-mediapipe") or {}).get("keypoint_map") or {}
        self.hagrid_map = (repos.get("hagrid") or {}).get("pose_map") or {}
        self.canned_map = {p["label"]: p["id"] for p in vocab["primitives"]["poses"] if p.get("support") == "canned"}
        self.canned_map.setdefault("None", "none")

    @staticmethod
    def _vote(votes: dict, pose: str, w: float, rule_pose: str) -> None:
        # A coarse label supports the fine rule pose when they share a family.
        if pose != rule_pose and _family_of(pose) and _family_of(pose) == _family_of(rule_pose):
            pose = rule_pose
        votes[pose] = votes.get(pose, 0.0) + w

    def classify(self, hand: HandFrame, width: int, height: int) -> tuple[str, float, dict]:
        rule_pose, rule_conf = self.rules.classify(hand)
        votes: dict[str, float] = {}
        total = self.W_RULE
        if rule_pose != "none":
            votes[rule_pose] = self.W_RULE * rule_conf
        detail = {"rule": [rule_pose, rule_conf]}

        vec = preprocess_landmarks(hand.landmarks, width, height)
        if self.knn and self.knn.ready:
            lab, share, _ = self.knn.predict(vec)
            mapped = self.keypoint_map.get(lab)
            detail["knn"] = [lab, round(share, 2)]
            # Three classes only: abstain when the rules saw a pose outside Open / Close / Pointer.
            if mapped and (rule_pose == "none" or _family_of(rule_pose) is not None):
                total += self.W_KNN
                self._vote(votes, mapped, self.W_KNN * share, rule_pose)
        if self.protos and self.protos.protos:
            near = self.protos.nearest(vec)
            if near and near[1] < 0.9:
                total += self.W_PROTO
                strength = max(0.0, 1.0 - near[1] / 0.9)
                votes[near[0]] = votes.get(near[0], 0.0) + self.W_PROTO * strength
                detail["prototype"] = [near[0], round(near[1], 3)]
        for src, (label, score) in hand.labels.items():
            mapped = None
            if src == "hagrid":
                mapped = self.hagrid_map.get(label)
            elif src == "mediapipe":
                mapped = self.canned_map.get(label)
            elif src == "keypoint":
                mapped = self.keypoint_map.get(label)
            if mapped and mapped != "none":
                total += self.W_EXT
                self._vote(votes, mapped, self.W_EXT * score, rule_pose)
        if not votes:
            return "none", 0.5, detail
        pose, score = max(votes.items(), key=lambda kv: kv[1])
        conf = min(0.99, score / total)
        # Several heads agreeing on one pose beats one strong head.
        if len(votes) == 1 and total > self.W_RULE:
            conf = min(0.99, conf + 0.05)
        return pose, round(conf, 3), detail


# --------------------------------------------------------------------------
# Segmenter — per-hand runs → Segments
# --------------------------------------------------------------------------


@dataclass
class Run:
    pose: str
    start_ms: int
    track: Track = field(default_factory=Track)
    moving: bool = False
    confs: list[float] = field(default_factory=list)
    early_emitted: bool = False
    early_end_ms: int = 0
    pending_change: int = 0
    pending_since: int | None = None
    raw_mismatch: int = 0


class HandSegmenter:
    """Turns one hand's per-frame (pose, position) stream into Segments.

    A run is one pose in one motion phase (still or moving). Runs end when the
    smoothed pose changes, the motion phase flips, or the hand disappears. An
    engagement pose that has been held for the dwell time is emitted early so
    ``system.engage`` fires while the palm is still up.
    """

    def __init__(self, motion: MotionHead, *, smoothing: int = 5, engagement_poses: set[str] | None = None,
                 dwell_ms: int = 300, lost_ms: int = 250, speed_thresh: float = 0.25, hand_id: str = "Right") -> None:
        self.motion = motion
        self.hand_id = hand_id
        self.smoothing = max(1, smoothing)
        self.engagement_poses = engagement_poses or {"open_palm", "back_of_hand"}
        self.dwell = dwell_ms
        self.lost_ms = lost_ms
        self.speed_thresh = speed_thresh
        self.recent: deque = deque(maxlen=self.smoothing)
        self.run: Run | None = None
        self.last_seen_ms: int | None = None
        self.last_center: tuple[float, float] | None = None
        self.last_size: float | None = None
        self.prev_t: int | None = None
        self.pose_runs: deque = deque(maxlen=6)  # (pose, start, end, still) for flutter → beckon
        self.history: deque = deque()  # (t_ms, center, scale) for windowed speed
        self.window_ms = 100
        self.width, self.height = DEFAULT_FRAME

    def _smoothed(self) -> str:
        return Counter(self.recent).most_common(1)[0][0]

    def _speed(self, t_ms: int, hand: HandFrame) -> float:
        """Palm-center speed (frame widths / s) plus palm growth rate, over a ~100 ms window.

        A window (not frame-to-frame) keeps landmark jitter from looking like
        motion at 30 fps; growth (approach / retreat) counts as moving too.
        """
        c = palm_center(hand.landmarks)
        s = hand_scale(hand.landmarks)
        self.history.append((t_ms, c, s))
        while len(self.history) > 1 and t_ms - self.history[0][0] > self.window_ms:
            self.history.popleft()
        speed = 0.0
        t0, c0, s0 = self.history[0]
        if t_ms - t0 >= self.window_ms * 0.6:
            dt = (t_ms - t0) / 1000.0
            speed = dist(c, c0) / dt
            growth = abs(s - s0) / max(s0, 1e-6) / dt
            if growth > 0.6:
                speed = max(speed, self.speed_thresh * 1.5)
        self.last_center, self.last_size, self.prev_t = c, s, t_ms
        return speed

    def _reset_tracking(self) -> None:
        self.recent.clear()
        self.history.clear()
        self.last_center = None
        self.last_size = None
        self.prev_t = None

    def feed(self, t_ms: int, hand: HandFrame | None, pose: str, conf: float, width: int, height: int) -> list[cg.Segment]:
        self.width, self.height = width, height
        out: list[cg.Segment] = []
        if hand is None:
            if self.run and self.last_seen_ms is not None and t_ms - self.last_seen_ms > self.lost_ms:
                out += self._close(t_ms, exited=self._near_edge())
                self._reset_tracking()
            return out
        if self.last_seen_ms is not None and t_ms - self.last_seen_ms > self.lost_ms:
            self._reset_tracking()
        self.last_seen_ms = t_ms
        self.recent.append(pose)
        sm = self._smoothed()
        speed = self._speed(t_ms, hand)

        if self.run is None:
            if sm != "none":
                self.run = Run(sm, t_ms, moving=speed > self.speed_thresh)
        else:
            # Hysteresis: leaving 'moving' needs a clearly slow hand, and for longer.
            if self.run.moving:
                moving = speed > 0.5 * self.speed_thresh
                need_ms = 150
            else:
                moving = speed > self.speed_thresh
                need_ms = 60
            phase_flip = moving != self.run.moving
            pose_change = sm != self.run.pose
            if pose_change:
                need_ms = 60
            # Raw (unsmoothed) frames of another pose: they belong to the next run once the change is confirmed.
            self.run.raw_mismatch = self.run.raw_mismatch + 1 if pose != self.run.pose else 0
            if pose_change or phase_flip:
                self.run.pending_change += 1
                if self.run.pending_since is None:
                    self.run.pending_since = t_ms
            else:
                self.run.pending_change = 0
                self.run.pending_since = None
            confirmed = self.run.pending_change >= 2 and t_ms - (self.run.pending_since or t_ms) >= need_ms
            if confirmed:
                # Speed is windowed, so motion started one frame before it was seen; a stop is
                # seen on the first still frame, so only the pending frames move over.
                if pose_change:
                    k = max(self.run.raw_mismatch, self.run.pending_change)
                elif moving:
                    k = self.run.pending_change + 1
                else:
                    k = self.run.pending_change
                carry = self.run.track.split_tail(k)
                carry_confs = self.run.confs[-len(carry):] if len(carry) else []
                out += self._close(t_ms)
                if sm != "none":
                    start = carry.times[0] if len(carry) else t_ms
                    self.run = Run(sm, start, track=carry, moving=moving, confs=list(carry_confs))
        if self.run is not None:
            self.run.track.add(t_ms, hand)
            self.run.confs.append(conf)
            # Early emission for engagement dwell (still hand only).
            if (
                not self.run.early_emitted
                and not self.run.moving
                and self.run.pose in self.engagement_poses
                and t_ms - self.run.start_ms >= self.dwell
            ):
                seg = self._segment(self.run, self.run.start_ms, t_ms, "hold", 0.9)
                self.run.early_emitted = True
                self.run.early_end_ms = t_ms
                out.append(seg)
        return out

    def _near_edge(self) -> bool:
        if not self.last_center:
            return False
        x, y = self.last_center
        return x < 0.08 or x > 0.92 or y < 0.08 or y > 0.92

    def _segment(self, run: Run, start: int, end: int, motion: str, mconf: float) -> cg.Segment:
        pconf = sum(run.confs) / max(1, len(run.confs))
        conf = round(min(0.99, 0.6 * pconf + 0.4 * mconf), 3)
        return cg.Segment(run.pose, motion, max(1, end - start), conf, 1, start)

    def _close(self, t_ms: int, exited: bool = False) -> list[cg.Segment]:
        run, self.run = self.run, None
        if run is None or len(run.track) == 0:
            return []
        end = run.track.times[-1]
        motion, mconf, _detail = self.motion.classify(run.track, self.width, self.height, exited=exited)
        out: list[cg.Segment] = []
        still = motion == "hold"
        self.pose_runs.append((run.pose, run.start_ms, end, still))
        beckon = self._flutter()
        if beckon:
            out.append(beckon)
            return out
        if run.early_emitted:
            # Remainder only matters if something happened after the dwell.
            if motion not in ("hold", "translate") and end - run.early_end_ms >= 80:
                out.append(self._segment(run, run.early_end_ms, end, motion, mconf))
            return out
        if end - run.start_ms < 100 and motion == "hold":
            return out  # jitter — no gesture step is shorter than 100 ms
        if motion == "translate" and end - run.start_ms < 250:
            return out  # unclassified twitch — would only break sequences
        out.append(self._segment(run, run.start_ms, end, motion, mconf))
        return out

    def _flutter(self) -> cg.Segment | None:
        """≥ 2 palm_up↔curl cycles with a still hand → one ``palm_up beckon`` segment (open_palm flutter stays a sequence)."""
        runs = list(self.pose_runs)
        if len(runs) < 4:
            return None
        last4 = runs[-4:]
        poses = [r[0] for r in last4]
        open_set = {"palm_up", "back_of_hand"}
        alternating = all(p in open_set for p in poses[0::2]) and all(p == "closed_fist" for p in poses[1::2]) or (
            all(p in open_set for p in poses[1::2]) and all(p == "closed_fist" for p in poses[0::2])
        )
        short = all((r[2] - r[1]) < 450 for r in last4)
        still = all(r[3] for r in last4)
        span = last4[-1][2] - last4[0][1]
        if alternating and short and still and 300 <= span <= 1500:
            self.pose_runs.clear()
            pose = "palm_up" if "palm_up" in poses else "back_of_hand"
            return cg.Segment(pose, "beckon", span, 0.8, 1, last4[0][1])
        return None

    def flush(self, t_ms: int) -> list[cg.Segment]:
        return self._close(t_ms, exited=self._near_edge()) if self.run else []


class PairSegmenter:
    """Two-hand runs: same pose on both hands, or a two-hand rule pose.

    A still pair held for ``dwell_ms`` is emitted early (so ``presence.hold_all``
    fires while both palms are still up); the remainder is only emitted if the
    hands then move (spread / bring together).
    """

    def __init__(self, dwell_ms: int = 1000, tolerance: int = 3) -> None:
        self.dwell = dwell_ms
        self.tolerance = tolerance
        self.pose: str | None = None
        self.start_ms = 0
        self.tracks: tuple[Track, Track] | None = None
        self.confs: list[float] = []
        self.early_end_ms: int | None = None
        self.pending = 0

    @property
    def active(self) -> bool:
        return self.pose is not None

    def feed(self, t_ms: int, pose: str | None, conf: float, a: HandFrame | None, b: HandFrame | None) -> list[cg.Segment]:
        out: list[cg.Segment] = []
        if pose is None or a is None or b is None:
            if not self.active:
                return out
            # Brief disagreement between the hands (jitter) does not end the pair.
            self.pending += 1
            if self.pending >= self.tolerance or a is None or b is None:
                out += self._close()
            return out
        if self.pose != pose:
            if self.active and self.pending + 1 < self.tolerance:
                self.pending += 1
                return out
            out += self._close()
            self.pose, self.start_ms, self.tracks, self.confs, self.early_end_ms = pose, t_ms, (Track(), Track()), [], None
        self.pending = 0
        assert self.tracks is not None
        self.tracks[0].add(t_ms, a)
        self.tracks[1].add(t_ms, b)
        self.confs.append(conf)
        if self.early_end_ms is None and t_ms - self.start_ms >= self.dwell:
            motion, mconf = two_hand_motion(*self.tracks)
            if motion == "hold":
                out.append(self._segment(self.start_ms, t_ms, motion, mconf))
                self.early_end_ms = t_ms
        return out

    def _segment(self, start: int, end: int, motion: str, mconf: float) -> cg.Segment:
        pconf = sum(self.confs) / max(1, len(self.confs))
        return cg.Segment(self.pose or "none", motion, max(1, end - start), round(min(0.99, 0.6 * pconf + 0.4 * mconf), 3), 2, start)

    def _close(self) -> list[cg.Segment]:
        if self.pose is None or self.tracks is None or len(self.tracks[0]) == 0:
            self.pose = None
            return []
        motion, mconf = two_hand_motion(*self.tracks)
        end = self.tracks[0].times[-1]
        out: list[cg.Segment] = []
        if self.early_end_ms is not None:
            if motion != "hold" and end - self.early_end_ms >= 80:
                out.append(self._segment(self.early_end_ms, end, motion, mconf))
        elif end - self.start_ms >= 80:
            out.append(self._segment(self.start_ms, end, motion, mconf))
        self.pose, self.tracks, self.early_end_ms, self.pending = None, None, None, 0
        return out

    def flush(self) -> list[cg.Segment]:
        return self._close()


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------


class GestureEngine:
    """Observations in, Segments out. One instance per camera stream."""

    def __init__(
        self,
        vocab: dict | None = None,
        *,
        keypoint_knn: KNN | None = None,
        history_knn: KNN | None = None,
        prototypes: PrototypeStore | None = None,
        load_repo_models: bool = True,
    ) -> None:
        self.vocab = vocab or cg.load_vocabulary()
        rec = self.vocab.get("recognizer") or {}
        gram = self.vocab.get("grammar") or {}
        if load_repo_models:
            keypoint_knn = keypoint_knn or load_keypoint_knn()
            history_knn = history_knn or load_history_knn()
        self.keypoint_knn = keypoint_knn
        self.history_knn = history_knn
        self.prototypes = prototypes if prototypes is not None else PrototypeStore()
        motion_map = ((self.vocab.get("repos") or {}).get("hand-gesture-mediapipe") or {}).get("motion_map") or {}
        self.pose_fusion = PoseFusion(self.vocab, keypoint_knn, self.prototypes)
        self.two_hand_rules = TwoHandRuleHead()
        self.motion = MotionHead(history_knn, motion_map)
        eng = set((gram.get("engagement") or {}).get("poses") or ["open_palm", "back_of_hand"])
        dwell = int((gram.get("engagement") or {}).get("dwell_ms") or 300)
        smoothing = int(rec.get("smoothing_window_frames") or 5)
        self.hands = {
            h: HandSegmenter(self.motion, smoothing=smoothing, engagement_poses=eng, dwell_ms=dwell, hand_id=h)
            for h in ("Left", "Right")
        }
        self.pair = PairSegmenter()
        self.pair_window_ms = 300
        self.frames = 0
        self.last_poses: dict[str, tuple[str, float, dict]] = {}
        self.last_t_ms = 0

    @property
    def models(self) -> dict:
        return {
            "keypoint_knn": bool(self.keypoint_knn and self.keypoint_knn.ready),
            "keypoint_samples": len(self.keypoint_knn.samples) if self.keypoint_knn else 0,
            "history_knn": bool(self.history_knn and self.history_knn.ready),
            "history_samples": len(self.history_knn.samples) if self.history_knn else 0,
            "prototype_poses": sorted(self.prototypes.protos) if self.prototypes else [],
        }

    def feed(self, obs: Observation) -> list[cg.Segment]:
        self.frames += 1
        self.last_t_ms = obs.t_ms
        by_hand: dict[str, HandFrame] = {}
        for h in obs.hands:
            key = "Left" if h.handedness.lower().startswith("l") else "Right"
            if key in by_hand:
                key = "Left" if key == "Right" else "Right"
            by_hand[key] = h
        poses: dict[str, tuple[str, float, dict]] = {}
        for key, h in by_hand.items():
            poses[key] = self.pose_fusion.classify(h, obs.width, obs.height)
        self.last_poses = poses

        out: list[cg.Segment] = []
        a, b = by_hand.get("Left"), by_hand.get("Right")
        pair_pose: str | None = None
        pair_conf = 0.0
        if a is not None and b is not None:
            two = self.two_hand_rules.classify(a, b)
            if two:
                pair_pose, pair_conf = two
            elif poses["Left"][0] == poses["Right"][0] and poses["Left"][0] != "none":
                pair_pose = poses["Left"][0]
                pair_conf = (poses["Left"][1] + poses["Right"][1]) / 2
        both = a is not None and b is not None
        if pair_pose or (self.pair.active and both):
            # Pair mode suspends single-hand runs so a two-palm hold is one segment.
            for key in ("Left", "Right"):
                if self.hands[key].run:
                    out += self.hands[key].flush(obs.t_ms)
        out += self.pair.feed(obs.t_ms, pair_pose, pair_conf, a, b)
        if not self.pair.active:
            for key in ("Left", "Right"):
                h = by_hand.get(key)
                if h is None:
                    out += self.hands[key].feed(obs.t_ms, None, "none", 0.0, obs.width, obs.height)
                else:
                    p, c, _ = poses[key]
                    out += self.hands[key].feed(obs.t_ms, h, p, c, obs.width, obs.height)
        for seg in out:
            seg.device = obs.device or seg.device
        return out

    def flush(self, t_ms: int | None = None) -> list[cg.Segment]:
        t = t_ms if t_ms is not None else self.last_t_ms + 1000
        out: list[cg.Segment] = []
        for h in self.hands.values():
            out += h.flush(t)
        out += self.pair.flush()
        return out

    def run(self, observations: Iterable[Observation]) -> list[cg.Segment]:
        out: list[cg.Segment] = []
        for obs in observations:
            out += self.feed(obs)
        out += self.flush()
        return out

    def teach_prototype(self, hand: HandFrame, pose: str, width: int = DEFAULT_FRAME[0], height: int = DEFAULT_FRAME[1], *, by: str = "Aaron", write: bool = True) -> int:
        return self.prototypes.add(pose, preprocess_landmarks(hand.landmarks, width, height), by=by, write=write)


class GestureSession:
    """Engine + resolver for one live stream (what the converse server holds)."""

    def __init__(self, *, context: str = "home", identity_ok: bool = False, switch_act: bool = False,
                 engine: GestureEngine | None = None, resolver: cg.GestureResolver | None = None) -> None:
        self.engine = engine or GestureEngine()
        self.resolver = resolver or cg.GestureResolver(
            self.engine.vocab, context=context, identity_ok=identity_ok, switch_act=switch_act
        )
        self.segments: list[cg.Segment] = []
        self.intents: list[cg.Intent] = []

    def feed(self, obs: Observation) -> tuple[list[cg.Segment], list[cg.Intent]]:
        segs = self.engine.feed(obs)
        intents: list[cg.Intent] = []
        for s in segs:
            intents += self.resolver.feed(s)
        self.segments += segs
        self.intents += intents
        return segs, intents

    def feed_dicts(self, frames: list[dict]) -> tuple[list[cg.Segment], list[cg.Intent]]:
        segs: list[cg.Segment] = []
        intents: list[cg.Intent] = []
        for d in frames:
            s, i = self.feed(Observation.from_dict(d))
            segs += s
            intents += i
        return segs, intents

    def flush(self) -> tuple[list[cg.Segment], list[cg.Intent]]:
        segs = self.engine.flush()
        intents: list[cg.Intent] = []
        for s in segs:
            intents += self.resolver.feed(s)
        self.segments += segs
        self.intents += intents
        return segs, intents

    def status(self) -> dict:
        return {
            "frames": self.engine.frames,
            "segments": len(self.segments),
            "intents": len(self.intents),
            "context": self.resolver.context,
            "switch_act": self.resolver.switch_act,
            "identity_ok": self.resolver.identity_ok,
            "engaged": self.resolver.engaged_until >= self.engine.last_t_ms,
            "last_poses": {k: [v[0], v[1]] for k, v in self.engine.last_poses.items()},
            "last_intents": [i.to_dict() for i in self.intents[-5:]],
            "models": self.engine.models,
        }


def switch_is_act(switches: dict | None = None) -> bool:
    """``switch.gesture_control`` from config/connectome/switches.json → True only when Aaron flipped it on."""
    doc = switches or cg.load_json(ROOT / "config" / "connectome" / "switches.json")
    for s in doc.get("switches") or []:
        if s.get("id") == "switch.gesture_control":
            d = str(s.get("default") or "").lower()
            return d in {"act", "standing_on", "on"} or d.startswith("standing_on") or d.startswith("act")
    return False


# --------------------------------------------------------------------------
# Synthetic hands — for tests, the demo, and gesture-check
# --------------------------------------------------------------------------


def synth_hand(pose: str, center: tuple[float, float] = (0.5, 0.55), scale: float = 0.09, handedness: str = "Right",
               *, facing: str = "palm", z_tilt: float = 0.0, jitter: float = 0.0, rng: random.Random | None = None) -> HandFrame:
    """Geometrically valid 21-point hand for a vocabulary pose (screen space, fingers up)."""
    rng = rng or random.Random(0)
    cx, cy = center
    right = handedness.lower().startswith("r")
    # x order of fingers across the palm: right hand palm-to-camera in mirrored screen space
    # puts the thumb on screen-left.
    sign = -1.0 if (right == (facing == "palm")) else 1.0
    cols = {"thumb": 1.9, "index": 0.9, "middle": 0.3, "ring": -0.3, "pinky": -0.9}
    wrist = (cx, cy + 1.0 * scale)
    lm: list[tuple[float, float, float]] = [None] * 21  # type: ignore[list-item]
    lm[WRIST] = (wrist[0], wrist[1], 0.0)

    ext = {"index": True, "middle": True, "ring": True, "pinky": True, "thumb": True}
    thumb_dir = "side"
    if pose in ("closed_fist", "thumb_up", "thumb_down"):
        ext = {k: False for k in ext}
        ext["thumb"] = pose != "closed_fist"
        thumb_dir = "up" if pose == "thumb_up" else "down" if pose == "thumb_down" else "in"
    elif pose in ("pointing_up", "pointing_away", "mute"):
        ext = {"index": True, "middle": False, "ring": False, "pinky": False, "thumb": False}
    elif pose == "victory":
        ext = {"index": True, "middle": True, "ring": False, "pinky": False, "thumb": False}
    elif pose == "three":
        ext = {"index": True, "middle": True, "ring": True, "pinky": False, "thumb": False}
    elif pose == "four":
        ext = {"index": True, "middle": True, "ring": True, "pinky": True, "thumb": False}
    elif pose == "i_love_you":
        ext = {"index": True, "middle": False, "ring": False, "pinky": True, "thumb": True}
    elif pose in ("ok_sign", "pinch"):
        ext = {"index": False, "middle": pose == "ok_sign", "ring": pose == "ok_sign", "pinky": pose == "ok_sign", "thumb": False}
    elif pose == "take_picture":  # L-shape per hand
        ext = {"index": True, "middle": False, "ring": False, "pinky": False, "thumb": True}

    def put(idx, x, y, z=0.0):
        lm[idx] = (x + rng.uniform(-jitter, jitter) * scale, y + rng.uniform(-jitter, jitter) * scale, z)

    for name, finger in zip(("index", "middle", "ring", "pinky"), FINGERS):
        col = sign * cols[name] * scale * 0.42
        mcp = (cx + col, cy - 0.15 * scale)
        put(finger[0], *mcp)
        if ext[name]:
            for k, frac in zip(finger[1:], (0.45, 0.8, 1.15)):
                put(k, mcp[0], mcp[1] - frac * scale * 1.35, z_tilt * frac)
        else:
            # curled: tip folds back toward the palm
            put(finger[1], mcp[0], mcp[1] - 0.35 * scale)
            put(finger[2], mcp[0], mcp[1] - 0.15 * scale)
            put(finger[3], mcp[0], mcp[1] + 0.15 * scale)
    tcol = sign * cols["thumb"] * scale * 0.42
    put(THUMB[0], cx + tcol * 0.45, cy + 0.55 * scale)
    if ext["thumb"] and thumb_dir == "side":
        put(THUMB[1], cx + tcol * 0.75, cy + 0.2 * scale)
        put(THUMB[2], cx + tcol * 1.0, cy - 0.15 * scale)
        put(THUMB[3], cx + tcol * 1.2, cy - 0.45 * scale)
    elif thumb_dir == "up":
        put(THUMB[1], cx + tcol * 0.6, cy + 0.1 * scale)
        put(THUMB[2], cx + tcol * 0.6, cy - 0.45 * scale)
        put(THUMB[3], cx + tcol * 0.6, cy - 1.0 * scale)
    elif thumb_dir == "down":
        put(THUMB[1], cx + tcol * 0.6, cy + 0.7 * scale)
        put(THUMB[2], cx + tcol * 0.6, cy + 1.2 * scale)
        put(THUMB[3], cx + tcol * 0.6, cy + 1.7 * scale)
    else:  # tucked
        put(THUMB[1], cx + tcol * 0.5, cy + 0.2 * scale)
        put(THUMB[2], cx + tcol * 0.25, cy + 0.0 * scale)
        put(THUMB[3], cx + tcol * 0.05, cy - 0.05 * scale)
    if pose in ("ok_sign", "pinch"):
        # index half-curled into a ring in front of the palm, thumb tip on the index tip
        mcp = lm[INDEX[0]]
        put(INDEX[1], mcp[0] + 0.1 * scale * sign, mcp[1] - 0.5 * scale)
        put(INDEX[2], mcp[0] + 0.35 * scale * sign, mcp[1] - 0.65 * scale)
        put(INDEX[3], mcp[0] + 0.55 * scale * sign, mcp[1] - 0.45 * scale)
        tip = lm[INDEX[3]]
        put(THUMB[3], tip[0] + 0.05 * scale * sign, tip[1] + 0.05 * scale)
        put(THUMB[2], tip[0] + 0.1 * scale * sign, tip[1] + 0.45 * scale)
    if pose == "pointing_away":
        # index toward the camera: foreshortened and tip nearer (z negative)
        mcp = lm[INDEX[0]]
        put(INDEX[1], mcp[0] + 0.15 * scale * sign, mcp[1] - 0.3 * scale, -0.04)
        put(INDEX[2], mcp[0] + 0.3 * scale * sign, mcp[1] - 0.5 * scale, -0.08)
        put(INDEX[3], mcp[0] + 0.5 * scale * sign, mcp[1] - 0.65 * scale, -0.12)
    return HandFrame(lm, handedness, 0.95)


def synth_sequence(steps: list[dict], *, fps: int = 15, t0: int = 0, device: str = "synthetic",
                   handedness: str = "Right", width: int = DEFAULT_FRAME[0], height: int = DEFAULT_FRAME[1],
                   jitter: float = 0.02) -> list[Observation]:
    """Script → observations. Each step: pose, ms, optional motion (hold/swipe_left/…), start/end center, size, hands, gap.

    ``{"gap": 400}`` inserts empty frames (no hand).
    """
    rng = random.Random(7)
    obs: list[Observation] = []
    t = t0
    dt = int(1000 / fps)
    center = (0.5, 0.55)
    for step in steps:
        if "gap" in step:
            n = max(1, step["gap"] // dt)
            for _ in range(n):
                obs.append(Observation(t, [], width, height, device))
                t += dt
            continue
        pose = step["pose"]
        ms = int(step.get("ms", 500))
        n = max(2, ms // dt)
        motion = step.get("motion", "hold")
        start = tuple(step.get("start", center))
        end = tuple(step.get("end", start))
        size0 = float(step.get("size", 0.09))
        size1 = float(step.get("size_end", size0))
        hands = int(step.get("hands", 1))
        facing = step.get("facing", "palm")
        for i in range(n):
            f = i / max(1, n - 1)
            if motion in ("hold", "swipe_left", "swipe_right", "raise", "lower", "translate_out", "push_in", "pull_out", "translate"):
                cx = start[0] + (end[0] - start[0]) * f
                cy = start[1] + (end[1] - start[1]) * f
            elif motion in ("circle_cw", "circle_ccw"):
                r = float(step.get("radius", 0.12))
                ang = (2 * math.pi * 1.05 * f) * (1 if motion == "circle_cw" else -1)
                cx = start[0] + r * math.cos(ang)
                cy = start[1] + r * math.sin(ang)
            elif motion == "wave":
                cx = start[0] + 0.08 * math.sin(2 * math.pi * 2.2 * f)
                cy = start[1]
            elif motion.startswith("flick_"):
                amp = 0.08 * math.sin(math.pi * f)
                cx, cy = start
                if motion == "flick_left":
                    cx -= amp
                elif motion == "flick_right":
                    cx += amp
                elif motion == "flick_up":
                    cy -= amp
                else:
                    cy += amp
            else:
                cx, cy = start
            sz = size0 + (size1 - size0) * f
            frame_hands = []
            if hands == 2:
                gap = float(step.get("hand_gap", 0.3))
                gap_end = float(step.get("hand_gap_end", gap))
                g = gap + (gap_end - gap) * f
                frame_hands.append(synth_hand(pose, (cx - g / 2, cy), sz, "Left", facing=facing, jitter=jitter, rng=rng))
                frame_hands.append(synth_hand(pose, (cx + g / 2, cy), sz, "Right", facing=facing, jitter=jitter, rng=rng))
            else:
                frame_hands.append(synth_hand(pose, (cx, cy), sz, handedness, facing=facing, jitter=jitter, rng=rng))
            obs.append(Observation(t, frame_hands, width, height, device))
            t += dt
        center = end
    return obs


DEMO_SCRIPTS: dict[str, list[dict]] = {
    "engage_grab_collapse": [
        {"pose": "open_palm", "ms": 600},
        {"pose": "closed_fist", "ms": 400},
        {"pose": "open_palm", "ms": 500},
    ],
    "swipe_left": [
        {"pose": "open_palm", "ms": 500, "start": [0.7, 0.55]},
        {"pose": "open_palm", "ms": 400, "motion": "swipe_left", "start": [0.7, 0.55], "end": [0.3, 0.55]},
        {"pose": "open_palm", "ms": 300, "start": [0.3, 0.55]},
    ],
    "spread_expand": [
        {"pose": "closed_fist", "ms": 500, "size": 0.07},
        {"pose": "open_palm", "ms": 400, "motion": "push_in", "size": 0.07, "size_end": 0.13},
    ],
    "air_scroll_up": [
        {"pose": "open_palm", "ms": 500},
        {"pose": "open_palm", "ms": 300, "motion": "flick_down"},
    ],
    "thumb_up": [{"pose": "thumb_up", "ms": 700}],
    "two_palms_hold": [{"pose": "open_palm", "ms": 1300, "hands": 2}],
    "handoff_grab": [
        {"pose": "open_palm", "ms": 600},
        {"pose": "closed_fist", "ms": 400},
        {"pose": "closed_fist", "ms": 500, "motion": "translate_out", "start": [0.5, 0.55], "end": [0.97, 0.55]},
        {"gap": 600},
    ],
    "circle_repeat": [
        {"pose": "open_palm", "ms": 500},
        {"pose": "pointing_up", "ms": 300},
        {"pose": "pointing_up", "ms": 900, "motion": "circle_cw", "start": [0.5, 0.5]},
    ],
}
