#!/usr/bin/env python3
"""Pack google-trends search results into a mesh/research document.

Does not call the network. Takes search-script JSON and emits a mesh document.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def load_payload(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"results": data}
    if isinstance(data, dict):
        return data
    raise ValueError("results JSON must be an object or list")


def distill_results(payload: dict) -> list[dict]:
    raw = payload.get("results") or payload.get("datasets") or []
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "path": item.get("path"),
                "name": item.get("name"),
                "topic": item.get("topic"),
                "year": item.get("year"),
                "ext": item.get("ext"),
                "size": item.get("size"),
                "raw_url": item.get("raw_url"),
                "html_url": item.get("html_url") or item.get("url"),
                "score": item.get("score"),
            }
        )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True, help="path to google-trends search JSON")
    p.add_argument("--query", help="override query string recorded in mesh doc")
    p.add_argument("--out", help="write mesh doc to file (default stdout)")
    args = p.parse_args()

    path = Path(args.results)
    if not path.exists():
        print(f"missing results file: {path}", file=sys.stderr)
        return 1

    payload = load_payload(path)
    doc = {
        "namespace": "mesh/research",
        "kind": "google_trends_catalog_hit",
        "integration": "google-trends",
        "query": args.query or payload.get("query") or payload.get("year"),
        "provider": payload.get("provider"),
        "fetched_at": payload.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        "packed_at": datetime.now(timezone.utc).isoformat(),
        "total_catalog": payload.get("total_catalog"),
        "returned": payload.get("returned"),
        "datasets": distill_results(payload),
        "source_repo": payload.get("source_repo") or "github.com/GoogleTrends/data",
        "cite": {
            "title": "Google Trends open-source datasets",
            "url": "https://github.com/GoogleTrends/data",
            "date_accessed": datetime.now(timezone.utc).date().isoformat(),
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
