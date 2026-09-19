#!/usr/bin/env python3
"""Pack Google Scholar search results into a mesh/research document.

Does not call the network. Takes SerpAPI-shaped (or distilled) JSON and emits
a mesh document for nulltickets store / vault distillates.
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
        return {"organic_results": data}
    if isinstance(data, dict):
        return data
    raise ValueError("results JSON must be an object or list")


def distill_results(payload: dict) -> list[dict]:
    raw = (
        payload.get("organic_results")
        or payload.get("results")
        or payload.get("papers")
        or []
    )
    out: list[dict] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        pub = item.get("publication_info") or {}
        authors = []
        if isinstance(pub, dict):
            for a in pub.get("authors") or []:
                if isinstance(a, dict) and a.get("name"):
                    authors.append(a["name"])
                elif isinstance(a, str):
                    authors.append(a)
            summary = pub.get("summary")
        else:
            summary = None
        cited = None
        inline = item.get("inline_links") or {}
        if isinstance(inline, dict):
            cb = inline.get("cited_by") or {}
            if isinstance(cb, dict):
                cited = cb.get("total")
        out.append(
            {
                "title": item.get("title"),
                "url": item.get("link") or item.get("url"),
                "snippet": item.get("snippet") or item.get("abstract"),
                "authors": authors,
                "publication": summary,
                "cited_by": cited,
                "result_id": item.get("result_id") or item.get("id"),
                "position": item.get("position"),
            }
        )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", required=True, help="path to Scholar results JSON")
    p.add_argument("--query", help="override query string recorded in mesh doc")
    p.add_argument("--out", help="write mesh doc to file (default stdout)")
    args = p.parse_args()

    path = Path(args.results)
    if not path.exists():
        print(f"missing results file: {path}", file=sys.stderr)
        return 1

    payload = load_payload(path)
    papers = distill_results(payload)
    query = args.query or payload.get("query") or payload.get("search_parameters", {}).get(
        "q"
    )
    doc = {
        "namespace": "mesh/research",
        "source": "integrations/google-scholar",
        "provider": payload.get("provider") or "serpapi",
        "sensitivity": "team",
        "query": query,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "count": len(papers),
        "papers": papers,
        "citations_required": True,
        "note": "Distilled Scholar hits only; cite title+URL+accessed date in briefs",
    }
    text = json.dumps(doc, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
