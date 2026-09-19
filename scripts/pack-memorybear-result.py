#!/usr/bin/env python3
"""Pack MemoryBear read/write results into a mesh/memorybear document.

Does not call the network. Takes memorybear.py output JSON and emits a mesh
document for nulltickets store / vault distillates.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_payload(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    raise ValueError("results JSON must be an object")


def distill_memories(payload: dict) -> list[dict]:
    raw = (
        payload.get("intermediate_outputs")
        or payload.get("memories")
        or payload.get("items")
        or []
    )
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if isinstance(item, str):
            out.append({"content": item})
            continue
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "id": item.get("id") or item.get("memory_id"),
                "content": item.get("content") or item.get("text") or item.get("message"),
                "type": item.get("type") or item.get("node_type"),
                "strength": item.get("strength") or item.get("score"),
            }
        )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True, help="path to MemoryBear result JSON")
    p.add_argument("--query", help="override query string recorded in mesh doc")
    p.add_argument("--out", help="write mesh doc to file (default stdout)")
    args = p.parse_args()

    path = Path(args.results)
    if not path.exists():
        print(f"missing results file: {path}", file=sys.stderr)
        return 1

    payload = load_payload(path)
    op = payload.get("operation") or ("write" if payload.get("message") else "read")
    doc = {
        "namespace": "mesh/memorybear",
        "kind": "memorybear_result",
        "at": datetime.now(timezone.utc).isoformat(),
        "operation": op,
        "query": args.query or payload.get("query"),
        "message": payload.get("message"),
        "answer": payload.get("answer") or payload.get("content"),
        "count": payload.get("count") or len(distill_memories(payload)),
        "memories": distill_memories(payload),
        "msg_id": payload.get("msg_id"),
        "provider": payload.get("provider"),
        "offline": bool(payload.get("offline")),
        "sense": payload.get("sense") or "sense.memorybear.hit",
        "motor": payload.get("motor") or "motor.memorybear",
        "source_file": str(path),
        "claim_hint": {
            "role": "memory-curator",
            "sensitivity": "internal",
            "confidence": 0.7 if payload.get("offline") else 0.85,
            "sources": ["memorybear", str(path)],
        },
    }

    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(str(out))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
