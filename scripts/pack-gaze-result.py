#!/usr/bin/env python3
"""Pack Pupil-style gaze samples into a mesh/gaze document.

Does not run Pupil. Takes an existing gaze JSON (list or {gaze/...}) and emits
a distilled mesh document for nulltickets store.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_gaze(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("gaze", "gaze_data", "samples", "data", "points"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    raise ValueError("gaze JSON must be a list or object with a list field")


def distill(samples: list) -> list:
    out = []
    for item in samples:
        if not isinstance(item, dict):
            continue
        norm = (
            item.get("norm_pos")
            or item.get("norm")
            or item.get("gaze_point_norm")
            or item.get("point")
        )
        out.append(
            {
                "norm_pos": norm,
                "confidence": item.get("confidence") or item.get("score"),
                "timestamp": item.get("timestamp") or item.get("ts") or item.get("time"),
                "topic": item.get("topic") or item.get("name"),
            }
        )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gaze", required=True, help="path to gaze JSON")
    p.add_argument("--recording", help="recording path/id (metadata only)")
    p.add_argument("--task", default="gaze", help="gaze|pupil|fixation|surface")
    p.add_argument("--out", help="write mesh doc to file (default stdout)")
    args = p.parse_args()

    gaze_path = Path(args.gaze)
    if not gaze_path.exists():
        print(f"missing gaze file: {gaze_path}", file=sys.stderr)
        return 1

    distilled = distill(load_gaze(gaze_path))
    confidences = [s["confidence"] for s in distilled if isinstance(s.get("confidence"), (int, float))]
    doc = {
        "namespace": "mesh/gaze",
        "source": "integrations/pupil",
        "sensitivity": "private",
        "task": args.task,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "recording": args.recording,
        "count": len(distilled),
        "mean_confidence": (sum(confidences) / len(confidences)) if confidences else None,
        "samples": distilled,
        "note": "raw eye video not included; human gate required for live capture",
    }
    text = json.dumps(doc, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
