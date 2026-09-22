#!/usr/bin/env python3
"""Search the public-apis catalog for Cam agents.

Parses the curated markdown tables from afidurko/public-apis (submodule README)
or a fixture / optional GitHub raw refresh.

Connectome:
  sense.catalog.public_apis → switch.autonomy → motor.public_apis

Usage:
  python3 scripts/public-apis-search.py --query weather --num 8
  python3 scripts/public-apis-search.py --category Animals --auth No --https
  python3 scripts/public-apis-search.py --list-categories
  python3 scripts/public-apis-search.py --doctor
  python3 scripts/public-apis-search.py --query cats --offline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "integrations" / "public-apis.json"
SAMPLE = ROOT / "scripts" / "testdata" / "sample-public-apis-readme.md"
ROW_RE = re.compile(
    r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|?\s*$"
)
CATEGORY_RE = re.compile(r"^###\s+(.+?)\s*$")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def catalog_paths(cfg: dict) -> list[Path]:
    rel = cfg.get("catalog_file") or "integrations/public-apis/README.md"
    return [ROOT / rel, SAMPLE]


def read_catalog_text(cfg: dict, *, offline: bool, refresh: bool) -> tuple[str, str]:
    """Return (markdown, source_label)."""
    if offline:
        return SAMPLE.read_text(encoding="utf-8"), "fixture"

    local = ROOT / (cfg.get("catalog_file") or "integrations/public-apis/README.md")
    if local.exists() and local.stat().st_size > 0 and not refresh:
        return local.read_text(encoding="utf-8"), "submodule"

    if refresh or not local.exists():
        url = (cfg.get("provider") or {}).get("raw_url") or (
            "https://raw.githubusercontent.com/afidurko/public-apis/master/README.md"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Cam-PublicAPIs/1.0"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                text = resp.read().decode("utf-8")
            if local.parent.exists():
                local.write_text(text, encoding="utf-8")
            return text, "github_raw"
        except Exception as exc:  # noqa: BLE001
            if local.exists():
                return local.read_text(encoding="utf-8"), f"submodule_after_fetch_error:{exc}"
            if SAMPLE.exists():
                return SAMPLE.read_text(encoding="utf-8"), f"fixture_after_fetch_error:{exc}"
            raise SystemExit(f"catalog unavailable: {exc}") from exc

    if SAMPLE.exists():
        return SAMPLE.read_text(encoding="utf-8"), "fixture"
    raise SystemExit(
        "public-apis catalog missing. Run: git submodule update --init integrations/public-apis"
    )


def parse_catalog(md: str) -> list[dict]:
    entries: list[dict] = []
    category = "Uncategorized"
    for line in md.splitlines():
        cat = CATEGORY_RE.match(line)
        if cat:
            category = cat.group(1).strip()
            continue
        if not line.startswith("|"):
            continue
        if "API |" in line or line.startswith("|:"):
            continue
        m = ROW_RE.match(line)
        if not m:
            continue
        name, url, desc, auth, https, cors = (g.strip() for g in m.groups())
        if name.lower() == "api":
            continue
        entries.append(
            {
                "name": name,
                "url": url,
                "description": desc,
                "auth": auth.strip("`"),
                "https": https,
                "cors": cors,
                "category": category,
            }
        )
    return entries


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def score_entry(entry: dict, query: str) -> int:
    q = norm(query)
    if not q:
        return 1
    blob = norm(
        " ".join(
            [
                entry.get("name") or "",
                entry.get("description") or "",
                entry.get("category") or "",
            ]
        )
    )
    score = 0
    if q in blob:
        score += 10
    for token in q.split():
        if token and token in blob:
            score += 3
        if token and token in norm(entry.get("name") or ""):
            score += 5
        if token and token in norm(entry.get("category") or ""):
            score += 4
    return score


def filter_entries(
    entries: list[dict],
    *,
    query: str | None,
    category: str | None,
    auth: str | None,
    https_only: bool,
    cors: str | None,
) -> list[dict]:
    out: list[dict] = []
    for e in entries:
        if category and norm(category) not in norm(e.get("category") or ""):
            continue
        if auth and norm(auth) != norm(e.get("auth") or ""):
            continue
        if https_only and norm(e.get("https") or "") != "yes":
            continue
        if cors and norm(cors) != norm(e.get("cors") or ""):
            continue
        if query:
            s = score_entry(e, query)
            if s <= 0:
                continue
            e = dict(e)
            e["score"] = s
        out.append(e)
    if query:
        out.sort(key=lambda x: (-(x.get("score") or 0), x.get("name") or ""))
    else:
        out.sort(key=lambda x: ((x.get("category") or ""), x.get("name") or ""))
    return out


def categories(entries: list[dict]) -> list[str]:
    seen: list[str] = []
    for e in entries:
        c = e.get("category") or "Uncategorized"
        if c not in seen:
            seen.append(c)
    return seen


def save_vault(payload: dict, query: str | None) -> Path:
    cfg = load_config()
    vault_rel = cfg.get("vault_dir") or "vault/04-Research/public-apis"
    day = date.today().isoformat()
    out_dir = ROOT / vault_rel / day
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = (query or payload.get("category") or "public-apis").strip().lower()
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug)[:48].strip("-")
    path = out_dir / f"{slug or 'public-apis'}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_markdown(payload: dict, json_path: Path) -> Path:
    lines = [
        f"# Public APIs: {payload.get('query') or payload.get('category') or 'results'}",
        "",
        f"Accessed: {date.today().isoformat()}  ",
        f"Source: public-apis via {payload.get('provider', 'catalog')}  ",
        f"Raw: `{json_path.relative_to(ROOT)}`",
        "",
        "## Results",
        "",
    ]
    for i, item in enumerate(payload.get("results") or [], 1):
        lines.append(
            f"{i}. **[{item.get('name')}]({item.get('url')})** — {item.get('description')}  \n"
            f"   Category: {item.get('category')} · Auth: {item.get('auth')} · "
            f"HTTPS: {item.get('https')} · CORS: {item.get('cors')}"
        )
    md_path = json_path.with_suffix(".md")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def search(
    *,
    query: str | None = None,
    category: str | None = None,
    auth: str | None = None,
    https_only: bool = False,
    cors: str | None = None,
    num: int = 0,
    offline: bool = True,
    refresh: bool = False,
) -> dict:
    """In-process catalog search (fixture by default — no subprocess)."""
    cfg = load_config()
    md, source = read_catalog_text(cfg, offline=offline, refresh=refresh)
    entries = parse_catalog(md)
    defaults = cfg.get("defaults") or {}
    limit = num or int(defaults.get("num_results") or 12)
    results = filter_entries(
        entries,
        query=query,
        category=category,
        auth=auth,
        https_only=https_only,
        cors=cors,
    )[:limit]
    return {
        "provider": source,
        "offline": bool(offline or source == "fixture"),
        "query": query,
        "category": category,
        "filters": {"auth": auth, "https": https_only, "cors": cors},
        "total_catalog": len(entries),
        "returned": len(results),
        "results": results,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "integration": "public-apis",
        "source_repo": "github.com/afidurko/public-apis",
        "sense": cfg.get("sense") or "sense.catalog.public_apis",
    }


def doctor(cfg: dict) -> dict:
    local = ROOT / (cfg.get("catalog_file") or "integrations/public-apis/README.md")
    report = {
        "ok": True,
        "config": str(CONFIG_PATH.relative_to(ROOT)),
        "submodule_readme": local.exists(),
        "fixture": SAMPLE.exists(),
        "scripts": {
            "search": (ROOT / "scripts/public-apis-search.py").exists(),
            "pack": (ROOT / "scripts/pack-public-apis-result.py").exists(),
            "check": (ROOT / "scripts/public-apis-check.py").exists(),
        },
        "sense": cfg.get("sense"),
        "motor": cfg.get("motor"),
        "hotspot": cfg.get("hotspot"),
        "available_to": cfg.get("available_to"),
    }
    if not CONFIG_PATH.exists():
        report["ok"] = False
    if not (local.exists() or SAMPLE.exists()):
        report["ok"] = False
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", "-q", help="keyword search across name/description/category")
    p.add_argument("--category", "-c", help="filter by category substring")
    p.add_argument("--auth", help="filter exact auth (No, apiKey, OAuth, …)")
    p.add_argument("--https", action="store_true", help="HTTPS Yes only")
    p.add_argument("--cors", help="filter exact CORS (Yes, No, Unknown)")
    p.add_argument("--num", type=int, default=0, help="max results (0 = config default)")
    p.add_argument("--list-categories", action="store_true")
    p.add_argument("--offline", action="store_true", help="use bundled fixture only")
    p.add_argument("--refresh", action="store_true", help="fetch GitHub raw README")
    p.add_argument("--save-vault", action="store_true", default=False)
    p.add_argument("--no-save-vault", action="store_true")
    p.add_argument("--doctor", action="store_true")
    p.add_argument("--json", action="store_true", help="print JSON (default)")
    args = p.parse_args()

    cfg = load_config()
    if args.doctor:
        report = doctor(cfg)
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") else 1

    if args.list_categories:
        md, source = read_catalog_text(cfg, offline=args.offline, refresh=args.refresh)
        cats = categories(parse_catalog(md))
        print(json.dumps({"provider": source, "count": len(cats), "categories": cats}, indent=2))
        return 0

    https_only = bool(args.https)
    payload = search(
        query=args.query,
        category=args.category,
        auth=args.auth,
        https_only=https_only,
        cors=args.cors,
        num=args.num,
        offline=args.offline,
        refresh=args.refresh,
    )

    if args.save_vault:
        jp = save_vault(payload, args.query or args.category)
        write_markdown(payload, jp)
        payload["vault_json"] = str(jp.relative_to(ROOT))

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
