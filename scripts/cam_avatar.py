#!/usr/bin/env python3
"""Cam avatar engine — AvatarFrame timelines from text (tier 0, procedural).

Implements the build-plan AvatarFrame contract (config/system/build-plan.json →
avatar.frame_contract): text + emotion in, a timeline of sparse ARKit-52
blendshape frames with viseme labels out. No model weights required; when the
hf_realtime weights land (MuseTalk lips / LivePortrait expression), they drive
the SAME contract and this engine becomes the offline fallback.

Muscle-grade targets honored (avatar.muscle_spec): ≥25 fps, first lip movement
≤500 ms, blink 12–20/min, co-articulated visemes (no flapping jaw).
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config" / "system" / "build-plan.json"

# ARKit-52 blendshape keys (Apple ARFaceAnchor standard).
ARKIT_52 = [
    "browDownLeft", "browDownRight", "browInnerUp", "browOuterUpLeft",
    "browOuterUpRight", "cheekPuff", "cheekSquintLeft", "cheekSquintRight",
    "eyeBlinkLeft", "eyeBlinkRight", "eyeLookDownLeft", "eyeLookDownRight",
    "eyeLookInLeft", "eyeLookInRight", "eyeLookOutLeft", "eyeLookOutRight",
    "eyeLookUpLeft", "eyeLookUpRight", "eyeSquintLeft", "eyeSquintRight",
    "eyeWideLeft", "eyeWideRight", "jawForward", "jawLeft", "jawOpen",
    "jawRight", "mouthClose", "mouthDimpleLeft", "mouthDimpleRight",
    "mouthFrownLeft", "mouthFrownRight", "mouthFunnel", "mouthLeft",
    "mouthLowerDownLeft", "mouthLowerDownRight", "mouthPressLeft",
    "mouthPressRight", "mouthPucker", "mouthRight", "mouthRollLower",
    "mouthRollUpper", "mouthShrugLower", "mouthShrugUpper", "mouthSmileLeft",
    "mouthSmileRight", "mouthStretchLeft", "mouthStretchRight",
    "mouthUpperUpLeft", "mouthUpperUpRight", "noseSneerLeft",
    "noseSneerRight", "tongueOut",
]

# Oculus/ARKit 15-viseme set with blendshape recipes (speech muscles).
VISEME_SHAPES: dict[str, dict[str, float]] = {
    "sil": {},
    "PP": {"mouthClose": 0.85, "mouthPressLeft": 0.55, "mouthPressRight": 0.55, "jawOpen": 0.05},
    "FF": {"mouthLowerDownLeft": 0.35, "mouthLowerDownRight": 0.35, "mouthRollLower": 0.6, "jawOpen": 0.12},
    "TH": {"tongueOut": 0.45, "jawOpen": 0.2, "mouthUpperUpLeft": 0.15, "mouthUpperUpRight": 0.15},
    "DD": {"jawOpen": 0.22, "mouthUpperUpLeft": 0.2, "mouthUpperUpRight": 0.2},
    "kk": {"jawOpen": 0.28, "mouthStretchLeft": 0.15, "mouthStretchRight": 0.15},
    "CH": {"jawOpen": 0.2, "mouthFunnel": 0.45, "mouthPucker": 0.25},
    "SS": {"jawOpen": 0.12, "mouthStretchLeft": 0.4, "mouthStretchRight": 0.4, "mouthSmileLeft": 0.15, "mouthSmileRight": 0.15},
    "nn": {"jawOpen": 0.14, "mouthClose": 0.3},
    "RR": {"jawOpen": 0.18, "mouthFunnel": 0.3, "mouthPucker": 0.35},
    "aa": {"jawOpen": 0.62, "mouthLowerDownLeft": 0.25, "mouthLowerDownRight": 0.25},
    "E": {"jawOpen": 0.34, "mouthStretchLeft": 0.35, "mouthStretchRight": 0.35, "mouthSmileLeft": 0.2, "mouthSmileRight": 0.2},
    "ih": {"jawOpen": 0.25, "mouthSmileLeft": 0.25, "mouthSmileRight": 0.25},
    "oh": {"jawOpen": 0.45, "mouthFunnel": 0.6, "mouthPucker": 0.3},
    "ou": {"jawOpen": 0.3, "mouthFunnel": 0.5, "mouthPucker": 0.65},
}

VISEMES = list(VISEME_SHAPES.keys())

# Grapheme → viseme (English-lean approximation; digraphs first).
DIGRAPHS = {
    "th": "TH", "ch": "CH", "sh": "CH", "ph": "FF", "wh": "ou",
    "oo": "ou", "ou": "ou", "ow": "oh", "ee": "ih", "ea": "ih",
    "ai": "E", "ay": "E", "ng": "nn", "qu": "kk", "ck": "kk",
}
SINGLES = {
    "a": "aa", "e": "E", "i": "ih", "o": "oh", "u": "ou", "y": "ih",
    "p": "PP", "b": "PP", "m": "PP",
    "f": "FF", "v": "FF",
    "d": "DD", "t": "DD",
    "k": "kk", "g": "kk", "c": "kk", "q": "kk", "x": "kk",
    "j": "CH",
    "s": "SS", "z": "SS",
    "n": "nn", "l": "nn", "h": "nn",
    "r": "RR", "w": "ou",
}

VOWEL_MS = 110
CONSONANT_MS = 72
WORD_GAP_MS = 90
PUNCT_GAP_MS = 260
EMOTIONS: dict[str, dict[str, float]] = {
    "neutral": {"mouthSmileLeft": 0.08, "mouthSmileRight": 0.08},
    "warm": {"mouthSmileLeft": 0.28, "mouthSmileRight": 0.28, "cheekSquintLeft": 0.12, "cheekSquintRight": 0.12},
    "focused": {"browDownLeft": 0.15, "browDownRight": 0.15, "eyeSquintLeft": 0.1, "eyeSquintRight": 0.1},
    "concerned": {"browInnerUp": 0.35, "mouthFrownLeft": 0.12, "mouthFrownRight": 0.12},
}


def text_to_visemes(text: str) -> list[tuple[str, int]]:
    """[(viseme, duration_ms)] with word/punctuation pauses."""
    seq: list[tuple[str, int]] = [("sil", 120)]
    i, low = 0, text.lower()
    while i < len(low):
        two = low[i : i + 2]
        ch = low[i]
        if two in DIGRAPHS:
            v = DIGRAPHS[two]
            seq.append((v, VOWEL_MS if v in ("aa", "E", "ih", "oh", "ou") else CONSONANT_MS))
            i += 2
            continue
        if ch in SINGLES:
            v = SINGLES[ch]
            seq.append((v, VOWEL_MS if ch in "aeiouy" else CONSONANT_MS))
        elif ch in ".,!?;:":
            seq.append(("sil", PUNCT_GAP_MS))
        elif ch.isspace():
            seq.append(("sil", WORD_GAP_MS))
        i += 1
    seq.append(("sil", 200))
    return seq


def _lerp_shapes(a: dict[str, float], b: dict[str, float], t: float) -> dict[str, float]:
    keys = set(a) | set(b)
    out = {}
    for k in keys:
        val = a.get(k, 0.0) * (1 - t) + b.get(k, 0.0) * t
        if val > 0.004:
            out[k] = round(min(1.0, val), 3)
    return out


def timeline(
    text: str,
    emotion: str = "neutral",
    fps: int = 25,
    seed: int | None = None,
) -> dict:
    """AvatarFrame timeline: sparse ARKit blendshapes per frame + viseme label."""
    rng = random.Random(seed if seed is not None else hash(text) & 0xFFFF)
    vis = text_to_visemes(text)
    total_ms = sum(d for _, d in vis)
    n_frames = max(2, int(total_ms / 1000 * fps) + 1)
    base = EMOTIONS.get(emotion, EMOTIONS["neutral"])

    # Viseme start times for co-articulated lookup.
    starts: list[tuple[int, str]] = []
    t_ms = 0
    for v, d in vis:
        starts.append((t_ms, v))
        t_ms += d

    def viseme_at(ms: float) -> tuple[str, str, float]:
        """(current, next, blend 0..1) — co-articulation across boundaries."""
        for idx in range(len(starts)):
            s = starts[idx][0]
            e = starts[idx + 1][0] if idx + 1 < len(starts) else total_ms
            if s <= ms < e:
                cur = starts[idx][1]
                nxt = starts[idx + 1][1] if idx + 1 < len(starts) else "sil"
                span = max(1.0, e - s)
                pos = (ms - s) / span
                blend = max(0.0, (pos - 0.6) / 0.4)  # last 40% eases to next
                return cur, nxt, blend
        return "sil", "sil", 0.0

    # Blink schedule: 12–20/min → every 3–5 s, 3 frames closed at 25 fps.
    blinks: list[float] = []
    t = rng.uniform(0.9, 2.2)
    while t < total_ms / 1000:
        blinks.append(t)
        t += rng.uniform(3.0, 5.0)

    frames = []
    for f in range(n_frames):
        ts = f / fps
        ms = ts * 1000
        cur, nxt, blend = viseme_at(ms)
        shapes = _lerp_shapes(VISEME_SHAPES[cur], VISEME_SHAPES[nxt], blend)
        # Emotion baseline under the speech muscles.
        for k, val in base.items():
            shapes[k] = round(min(1.0, max(shapes.get(k, 0.0), val)), 3)
        # Blink (both lids), 120 ms closed.
        for b in blinks:
            d = abs(ts - b)
            if d < 0.06:
                lid = round(1.0 - (d / 0.06) * 0.2, 3)
                shapes["eyeBlinkLeft"] = lid
                shapes["eyeBlinkRight"] = lid
        # Gaze wander + brow micro-life.
        shapes["eyeLookOutLeft"] = round(abs(math.sin(ts * 0.35)) * 0.08, 3)
        shapes["eyeLookOutRight"] = round(abs(math.cos(ts * 0.3)) * 0.08, 3)
        if f % int(fps * 4) == 0 and f > 0:
            shapes["browInnerUp"] = max(shapes.get("browInnerUp", 0.0), 0.18)
        frames.append({"t": round(ts, 3), "viseme": cur, "blendshapes": shapes})

    blink_per_min = len(blinks) / max(total_ms / 60000.0, 1e-6)
    return {
        "contract": "AvatarFrame",
        "tier": "procedural_tier0",
        "text": text,
        "emotion": emotion,
        "fps": fps,
        "duration_s": round(total_ms / 1000, 3),
        "frame_count": len(frames),
        "blink_per_min": round(blink_per_min, 1),
        "frames": frames,
        "note": "sparse blendshapes; absent ARKit keys are 0. Weights-backed tiers drive the same contract.",
    }


def contract() -> dict:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    avatar = plan.get("avatar") or {}
    return {
        "contract": avatar.get("frame_contract"),
        "muscle_spec": avatar.get("muscle_spec"),
        "blendshape_keys": ARKIT_52,
        "visemes": VISEMES,
        "tiers": [t.get("id") for t in avatar.get("tiers") or []],
    }
