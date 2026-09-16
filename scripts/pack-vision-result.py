#!/usr/bin/env python3
"""Pack PaddleDetection-style detections into a mesh/vision document.

Does not run models. Takes an existing detections JSON (list or {boxes:...})
and emits a distilled mesh document for nulltickets store.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_detections(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("detections", "boxes", "results", "predictions"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    raise ValueError("detections JSON must be a list or object with a list field")


def distill(dets: list) -> list:
    out = []
    for item in dets:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "label": item.get("label") or item.get("category") or item.get("class"),
                "score": item.get("score") or item.get("confidence"),
                "bbox": item.get("bbox") or item.get("box") or item.get("bbox_xyxy"),
            }
        )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--detections", required=True, help="path to detections JSON")
    p.add_argument("--image", help="source image path (recorded as metadata only)")
    p.add_argument("--task", default="detect", help="detect|pose|track|segment")
    p.add_argument("--out", help="write mesh doc to file (default stdout)")
    args = p.parse_args()

    dets_path = Path(args.detections)
    if not dets_path.exists():
        print(f"missing detections file: {dets_path}", file=sys.stderr)
        return 1

    distilled = distill(load_detections(dets_path))
    doc = {
        "namespace": "mesh/vision",
        "source": "integrations/paddledetection",
        "sensitivity": "private",
        "task": args.task,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "image": args.image,
        "count": len(distilled),
        "detections": distilled,
        "note": "raw frames not included; human gate required for camera capture",
    }
    text = json.dumps(doc, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
