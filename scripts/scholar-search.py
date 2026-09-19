#!/usr/bin/env python3
"""Google Scholar search via SerpAPI (or offline fixtures).

Google Scholar has no official API. This script is the Cam connector:
  sense.web.scholar → switch.research_scan → motor.web_fetch

Usage:
  python3 scripts/scholar-search.py --query "connectome" --offline
  python3 scripts/scholar-search.py --query "connectome" --num 8
  python3 scripts/scholar-search.py --author-id USERID --offline
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "integrations" / "google-scholar.json"
SAMPLE = ROOT / "scripts" / "testdata" / "sample-scholar-results.json"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def serpapi_url(params: dict) -> str:
    cfg = load_config()
    base = (
        (cfg.get("provider") or {}).get("api_base")
        or "https://serpapi.com/search.json"
    )
    return f"{base}?{urllib.parse.urlencode(params)}"


def fetch_serpapi(params: dict) -> dict:
    key = os.environ.get("SERPAPI_API_KEY") or os.environ.get("SERP_API_KEY")
    if not key:
        raise SystemExit(
            "SERPAPI_API_KEY not set. Add it to local .env (gitignored), "
            "or pass --offline / --fixture for dry runs."
        )
    params = dict(params)
    params["api_key"] = key
    url = serpapi_url(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Cam-Scholar/1.0"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def offline_payload(query: str | None, author_id: str | None) -> dict:
    raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
    raw["provider"] = "fixture"
    raw["offline"] = True
    if query:
        raw["query"] = query
    if author_id:
        raw["author_id"] = author_id
        raw["engine"] = "google_scholar_author"
    raw["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return raw


def save_vault(payload: dict, query: str | None) -> Path:
    cfg = load_config()
    vault_rel = cfg.get("vault_dir") or "vault/04-Research/scholar"
    day = date.today().isoformat()
    out_dir = ROOT / vault_rel / day
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = (query or payload.get("author_id") or "scholar").strip().lower()
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug)[:48].strip("-")
    path = out_dir / f"{slug or 'scholar'}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_markdown(payload: dict, json_path: Path) -> Path:
    papers = payload.get("organic_results") or payload.get("results") or []
    lines = [
        f"# Scholar: {payload.get('query') or payload.get('author_id') or 'results'}",
        "",
        f"Accessed: {date.today().isoformat()}  ",
        f"Source: Google Scholar via {payload.get('provider', 'serpapi')}  ",
        f"Raw: `{json_path.relative_to(ROOT)}`",
        "",
        "## Results",
        "",
    ]
    for i, item in enumerate(papers, 1):
        if not isinstance(item, dict):
            continue
        title = item.get("title") or "(untitled)"
        url = item.get("link") or item.get("url") or ""
        snippet = item.get("snippet") or ""
        pub = (item.get("publication_info") or {}).get("summary") or ""
        cited = ((item.get("inline_links") or {}).get("cited_by") or {}).get("total")
        lines.append(f"{i}. **{title}**")
        if pub:
            lines.append(f"   - {pub}")
        if url:
            lines.append(f"   - {url}")
        if cited is not None:
            lines.append(f"   - cited by: {cited}")
        if snippet:
            lines.append(f"   - {snippet}")
        lines.append("")
    md_path = json_path.with_suffix(".md")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", "-q", help="Scholar search query")
    p.add_argument("--author-id", help="Google Scholar author user id")
    p.add_argument("--num", type=int, default=None, help="max results (default from config)")
    p.add_argument("--offline", action="store_true", help="use fixture; no network")
    p.add_argument("--fixture", help="path to results JSON fixture")
    p.add_argument("--dry-run", action="store_true", help="print plan only")
    p.add_argument("--save-vault", action="store_true", default=True)
    p.add_argument("--no-save-vault", action="store_false", dest="save_vault")
    p.add_argument("--out", help="write raw JSON to this path")
    p.add_argument("--pack-out", help="also write packed mesh/research JSON here")
    args = p.parse_args()

    cfg = load_config()
    defaults = cfg.get("defaults") or {}
    profile = cfg.get("profile") or {}
    author_id = args.author_id or profile.get("author_id")
    num = args.num or int(defaults.get("num_results") or 10)

    if not args.query and not author_id and not args.fixture and not args.offline:
        print("Need --query, --author-id, --fixture, or --offline", file=sys.stderr)
        return 1

    if args.dry_run:
        plan = {
            "sense": "sense.web.scholar",
            "switch": "switch.research_scan",
            "motor": "motor.web_fetch",
            "query": args.query,
            "author_id": author_id,
            "num": num,
            "offline": bool(args.offline or args.fixture),
            "credential_env": (cfg.get("provider") or {}).get("credential_env"),
        }
        print(json.dumps(plan, indent=2))
        return 0

    if args.fixture:
        payload = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
        payload.setdefault("provider", "fixture")
    elif args.offline:
        payload = offline_payload(args.query, author_id)
    elif author_id and not args.query:
        payload = fetch_serpapi(
            {
                "engine": "google_scholar_author",
                "author_id": author_id,
                "hl": defaults.get("language") or "en",
            }
        )
        payload["provider"] = "serpapi"
        payload["author_id"] = author_id
    else:
        params = {
            "engine": "google_scholar",
            "q": args.query,
            "num": num,
            "hl": defaults.get("language") or "en",
        }
        payload = fetch_serpapi(params)
        payload["provider"] = "serpapi"
        payload["query"] = args.query

    payload.setdefault("fetched_at", datetime.now(timezone.utc).isoformat())
    text = json.dumps(payload, indent=2, sort_keys=True)

    out_path = Path(args.out) if args.out else None
    if args.save_vault and not out_path:
        out_path = save_vault(payload, args.query)
        write_markdown(payload, out_path)
        print(f"wrote {out_path.relative_to(ROOT)}", file=sys.stderr)
    elif out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {out_path}", file=sys.stderr)
    else:
        print(text)

    if args.pack_out:
        pack = ROOT / "scripts" / "pack-scholar-result.py"
        # Inline distill to avoid subprocess import issues
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib.util

        spec = importlib.util.spec_from_file_location("pack_scholar", pack)
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        papers = mod.distill_results(payload)
        doc = {
            "namespace": "mesh/research",
            "source": "integrations/google-scholar",
            "provider": payload.get("provider"),
            "sensitivity": "team",
            "query": args.query or payload.get("query"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "count": len(papers),
            "papers": papers,
            "citations_required": True,
        }
        Path(args.pack_out).write_text(
            json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"packed mesh → {args.pack_out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
