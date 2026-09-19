#!/usr/bin/env python3
"""Pack a mesh claim conforming to Cam's MMP-inspired schema.

Required fields: claim, role, sources, confidence, parents, sensitivity, accessed.
Remixes only — never dump raw peer chat as mesh/facts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "config" / "memory" / "mesh-claim-schema.json").read_text(encoding="utf-8")
)


def content_hash(payload: dict) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def build_claim(args: argparse.Namespace) -> dict:
    sources = []
    if args.source:
        for s in args.source:
            if "|" in s:
                title, url = s.split("|", 1)
                sources.append(
                    {"title": title.strip(), "url": url.strip(), "accessed": args.accessed}
                )
            else:
                sources.append({"title": s, "url": s, "accessed": args.accessed})
    parents = list(args.parent or [])
    body = {
        "claim": args.claim,
        "role": args.role,
        "sources": sources,
        "confidence": args.confidence,
        "parents": parents,
        "sensitivity": args.sensitivity,
        "accessed": args.accessed,
        "namespace": args.namespace,
        "schema": SCHEMA["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    body["id"] = f"cmb_{content_hash(body)}"
    missing = [f for f in SCHEMA["required_fields"] if not body.get(f) and body.get(f) != 0]
    if missing:
        raise SystemExit(f"missing required fields: {missing}")
    return body


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--claim", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--namespace", default="mesh/facts")
    p.add_argument("--confidence", default="medium")
    p.add_argument("--sensitivity", default="team", choices=["public", "team", "private"])
    p.add_argument("--accessed", default=date.today().isoformat())
    p.add_argument("--source", action="append", help="title|url or mesh key (repeatable)")
    p.add_argument("--parent", action="append", help="parent claim id / mesh key")
    p.add_argument("--out", help="write JSON file")
    args = p.parse_args()
    if not args.source:
        print("at least one --source required for non-trivial claims", file=sys.stderr)
        return 2
    doc = build_claim(args)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
