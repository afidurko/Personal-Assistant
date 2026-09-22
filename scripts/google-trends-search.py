#!/usr/bin/env python3
"""Search Google Trends open datasets (GoogleTrends/data on GitHub).

Indexes CSV/XLSX (etc.) paths via GitHub git trees API or offline fixture.
Optionally fetches a single file into the vault.

Connectome:
  sense.catalog.google_trends → switch.autonomy → motor.google_trends

Usage:
  python3 scripts/google-trends-search.py --query election --offline
  python3 scripts/google-trends-search.py --query "nba" --num 8
  python3 scripts/google-trends-search.py --list-years --offline
  python3 scripts/google-trends-search.py --fetch 20150626_SameSexMarriage.csv --offline
  python3 scripts/google-trends-search.py --doctor
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "integrations" / "google-trends.json"
SAMPLE = ROOT / "scripts" / "testdata" / "sample-google-trends-catalog.json"

DATE_PREFIX_RE = re.compile(r"^(\d{8}|\d{6}|\d{4}-\d+|\d{4})_")
YEAR_RE = re.compile(r"(20\d{2})")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def topic_from_stem(stem: str) -> str:
    topic = DATE_PREFIX_RE.sub("", stem)
    return topic.replace("_", " ").strip() or stem


def year_from_path(path: str, stem: str, folder: str | None) -> str | None:
    m = YEAR_RE.search(stem) or (YEAR_RE.search(folder) if folder else None)
    if m:
        return m.group(1)
    m2 = re.match(r"(\d{8})_", stem)
    if m2:
        d8 = m2.group(1)
        return d8[:4] if d8.startswith("20") else d8[4:8]
    return None


def entry_from_path(path: str, *, size: int | None = None, sha: str | None = None) -> dict:
    cfg = load_config()
    provider = cfg.get("provider") or {}
    raw_base = provider.get("raw_base") or "https://raw.githubusercontent.com/GoogleTrends/data/master/"
    html_base = provider.get("html_base") or "https://github.com/GoogleTrends/data/blob/master/"
    name = path.rsplit("/", 1)[-1]
    stem = name.rsplit(".", 1)[0] if "." in name else name
    folder = path.rsplit("/", 1)[0] if "/" in path else None
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return {
        "path": path,
        "name": name,
        "stem": stem,
        "topic": topic_from_stem(stem),
        "ext": ext,
        "size": size,
        "folder": folder,
        "year": year_from_path(path, stem, folder),
        "sha": sha,
        "raw_url": f"{raw_base}{path}",
        "html_url": f"{html_base}{path}",
    }


def allowed_ext(cfg: dict) -> set[str]:
    defaults = cfg.get("defaults") or {}
    exts = defaults.get("extensions") or [".csv", ".xlsx", ".xls", ".tsv", ".json"]
    return {e.lower() if e.startswith(".") else f".{e.lower()}" for e in exts}


def parse_tree_payload(payload: dict, cfg: dict) -> list[dict]:
    tree = payload.get("tree") or payload.get("entries") or []
    allow = allowed_ext(cfg)
    entries: list[dict] = []
    for t in tree:
        if isinstance(t, dict) and t.get("path") and "ext" in t and "topic" in t:
            # already-normalized fixture/cache entry
            path = t["path"]
            name = path.rsplit("/", 1)[-1]
            ext = f".{(t.get('ext') or name.rsplit('.', 1)[-1]).lower()}"
            if allow and ext not in allow:
                continue
            e = dict(t)
            if not e.get("raw_url"):
                e.update(entry_from_path(path, size=e.get("size"), sha=e.get("sha")))
            entries.append(e)
            continue
        if not isinstance(t, dict) or t.get("type") not in (None, "blob"):
            if isinstance(t, dict) and t.get("type") and t.get("type") != "blob":
                continue
        path = (t.get("path") if isinstance(t, dict) else None) or ""
        if not path:
            continue
        lower = path.lower()
        if not any(lower.endswith(ext) for ext in allow):
            continue
        if isinstance(t, dict) and t.get("type") and t.get("type") != "blob":
            continue
        entries.append(
            entry_from_path(
                path,
                size=t.get("size") if isinstance(t, dict) else None,
                sha=t.get("sha") if isinstance(t, dict) else None,
            )
        )
    return entries


def cache_path(cfg: dict) -> Path:
    rel = (cfg.get("cache") or {}).get("tree_path") or "data/runtime/google-trends-tree.json"
    return ROOT / rel


def cache_fresh(cfg: dict, path: Path) -> bool:
    if not path.exists():
        return False
    ttl = float((cfg.get("cache") or {}).get("ttl_hours") or 24)
    age_h = (time.time() - path.stat().st_mtime) / 3600.0
    return age_h <= ttl


def fetch_github_tree(cfg: dict) -> dict:
    url = (cfg.get("provider") or {}).get("tree_api") or (
        "https://api.github.com/repos/GoogleTrends/data/git/trees/master?recursive=1"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Cam-GoogleTrends/1.0",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_catalog(cfg: dict, *, offline: bool, refresh: bool) -> tuple[list[dict], str]:
    if offline:
        raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
        return parse_tree_payload(raw, cfg), "fixture"

    cache = cache_path(cfg)
    if not refresh and cache_fresh(cfg, cache):
        raw = json.loads(cache.read_text(encoding="utf-8"))
        return parse_tree_payload(raw, cfg), "cache"

    try:
        api = fetch_github_tree(cfg)
        entries = parse_tree_payload(api, cfg)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(
            json.dumps(
                {
                    "provider": "github_git_trees",
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "sha": api.get("sha"),
                    "truncated": api.get("truncated"),
                    "entries": entries,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return entries, "github_git_trees"
    except Exception as exc:  # noqa: BLE001
        if cache.exists():
            raw = json.loads(cache.read_text(encoding="utf-8"))
            return parse_tree_payload(raw, cfg), f"cache_after_fetch_error:{exc}"
        if SAMPLE.exists():
            raw = json.loads(SAMPLE.read_text(encoding="utf-8"))
            return parse_tree_payload(raw, cfg), f"fixture_after_fetch_error:{exc}"
        raise SystemExit(f"google-trends catalog unavailable: {exc}") from exc


def score_entry(entry: dict, query: str) -> int:
    q = norm(query)
    if not q:
        return 1
    blob = norm(
        " ".join(
            [
                entry.get("name") or "",
                entry.get("topic") or "",
                entry.get("path") or "",
                entry.get("folder") or "",
                entry.get("year") or "",
            ]
        )
    )
    score = 0
    if q in blob:
        score += 10
    for token in q.split():
        if token and token in blob:
            score += 3
        if token and token in norm(entry.get("topic") or ""):
            score += 5
        if token and token in norm(entry.get("name") or ""):
            score += 4
    return score


def filter_entries(
    entries: list[dict],
    *,
    query: str | None,
    year: str | None,
    ext: str | None,
    folder: str | None,
) -> list[dict]:
    out: list[dict] = []
    ext_n = None
    if ext:
        ext_n = ext.lower().lstrip(".")
    for e in entries:
        if year and str(e.get("year") or "") != str(year):
            continue
        if ext_n and norm(e.get("ext") or "") != norm(ext_n):
            continue
        if folder and norm(folder) not in norm(e.get("folder") or e.get("path") or ""):
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
        out.sort(key=lambda x: (x.get("year") or "", x.get("name") or ""))
    return out


def save_vault(payload: dict, query: str | None) -> Path:
    cfg = load_config()
    vault_rel = cfg.get("vault_dir") or "vault/04-Research/google-trends"
    day = date.today().isoformat()
    out_dir = ROOT / vault_rel / day
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = (query or payload.get("year") or "google-trends").strip().lower()
    slug = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug)[:48].strip("-")
    path = out_dir / f"{slug or 'google-trends'}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_markdown(payload: dict, json_path: Path) -> Path:
    lines = [
        f"# Google Trends data: {payload.get('query') or payload.get('year') or 'results'}",
        "",
        f"Accessed: {date.today().isoformat()}  ",
        f"Source: GoogleTrends/data via {payload.get('provider', 'catalog')}  ",
        f"Raw: `{json_path.relative_to(ROOT)}`",
        "",
        "## Results",
        "",
    ]
    for i, item in enumerate(payload.get("results") or [], 1):
        title = item.get("topic") or item.get("name")
        url = item.get("html_url") or item.get("raw_url")
        lines.append(
            f"{i}. **[{title}]({url})** — `{item.get('path')}`  \n"
            f"   Year: {item.get('year') or '—'} · Ext: {item.get('ext')} · "
            f"Size: {item.get('size') or '—'}"
        )
    md_path = json_path.with_suffix(".md")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def resolve_fetch_path(entries: list[dict], fetch: str) -> dict | None:
    fetch_n = fetch.strip().lstrip("./")
    for e in entries:
        if e.get("path") == fetch_n or e.get("name") == fetch_n:
            return e
    # suffix match
    for e in entries:
        if (e.get("path") or "").endswith(fetch_n):
            return e
    return None


def fetch_file(entry: dict, cfg: dict) -> Path:
    max_bytes = int((cfg.get("defaults") or {}).get("max_fetch_bytes") or 5_000_000)
    url = entry.get("raw_url")
    if not url:
        raise SystemExit("entry missing raw_url")
    req = urllib.request.Request(url, headers={"User-Agent": "Cam-GoogleTrends/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise SystemExit(f"file exceeds max_fetch_bytes={max_bytes}: {entry.get('path')}")
    vault_rel = cfg.get("vault_dir") or "vault/04-Research/google-trends"
    day = date.today().isoformat()
    out_dir = ROOT / vault_rel / day / "files"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = entry.get("name") or Path(entry["path"]).name
    out = out_dir / name
    out.write_bytes(data)
    return out


def search(
    *,
    query: str | None = None,
    year: str | None = None,
    ext: str | None = None,
    folder: str | None = None,
    num: int = 0,
    offline: bool = True,
    refresh: bool = False,
) -> dict:
    """In-process Trends catalog search (fixture by default — no subprocess)."""
    cfg = load_config()
    entries, source = load_catalog(cfg, offline=offline, refresh=refresh)
    defaults = cfg.get("defaults") or {}
    limit = num or int(defaults.get("num_results") or 12)
    results = filter_entries(
        entries,
        query=query,
        year=year,
        ext=ext,
        folder=folder,
    )[:limit]
    return {
        "provider": source,
        "offline": bool(offline or source == "fixture"),
        "query": query,
        "year": year,
        "filters": {"ext": ext, "folder": folder},
        "total_catalog": len(entries),
        "returned": len(results),
        "results": results,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "integration": "google-trends",
        "source_repo": "github.com/GoogleTrends/data",
        "homepage": "https://github.com/GoogleTrends/data",
        "sense": cfg.get("sense") or "sense.catalog.google_trends",
    }


def doctor(cfg: dict) -> dict:
    report = {
        "ok": True,
        "config": str(CONFIG_PATH.relative_to(ROOT)) if CONFIG_PATH.exists() else None,
        "fixture": SAMPLE.exists(),
        "cache": cache_path(cfg).exists(),
        "scripts": {
            "search": (ROOT / "scripts/google-trends-search.py").exists(),
            "pack": (ROOT / "scripts/pack-google-trends-result.py").exists(),
            "check": (ROOT / "scripts/google-trends-check.py").exists(),
        },
        "sense": cfg.get("sense"),
        "motor": cfg.get("motor"),
        "hotspot": cfg.get("hotspot"),
        "available_to": cfg.get("available_to"),
        "source_repo": cfg.get("remote"),
    }
    if not CONFIG_PATH.exists() or not SAMPLE.exists():
        report["ok"] = False
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--query", "-q", help="keyword search across path/topic/name")
    p.add_argument("--year", help="filter by year (e.g. 2016)")
    p.add_argument("--ext", help="filter by extension (csv, xlsx, …)")
    p.add_argument("--folder", help="filter by path folder substring")
    p.add_argument("--num", type=int, default=0, help="max results (0 = config default)")
    p.add_argument("--list-years", action="store_true")
    p.add_argument("--list-ext", action="store_true")
    p.add_argument("--fetch", help="download one dataset by path or filename into vault")
    p.add_argument("--offline", action="store_true", help="use bundled fixture only")
    p.add_argument("--refresh", action="store_true", help="force GitHub trees refresh")
    p.add_argument("--save-vault", action="store_true")
    p.add_argument("--doctor", action="store_true")
    args = p.parse_args()

    cfg = load_config()
    if args.doctor:
        report = doctor(cfg)
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") else 1

    if args.list_years or args.list_ext or args.fetch:
        entries, source = load_catalog(cfg, offline=args.offline, refresh=args.refresh)
    else:
        entries, source = [], ""

    if args.list_years:
        years = sorted({e.get("year") for e in entries if e.get("year")})
        print(json.dumps({"provider": source, "count": len(years), "years": years}, indent=2))
        return 0

    if args.list_ext:
        exts = sorted({e.get("ext") for e in entries if e.get("ext")})
        print(json.dumps({"provider": source, "count": len(exts), "extensions": exts}, indent=2))
        return 0

    if args.fetch:
        # For offline fetch of fixture files, still try network raw URL unless missing
        hit = resolve_fetch_path(entries, args.fetch)
        if not hit:
            print(json.dumps({"ok": False, "error": "path_not_in_catalog", "fetch": args.fetch}, indent=2))
            return 1
        if args.offline:
            # Offline: record intent + URLs without downloading
            payload = {
                "ok": True,
                "offline": True,
                "fetched": False,
                "entry": hit,
                "note": "Pass without --offline to download raw file into vault",
                "provider": source,
                "integration": "google-trends",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            print(json.dumps(payload, indent=2))
            return 0
        try:
            out = fetch_file(hit, cfg)
        except (urllib.error.URLError, urllib.error.HTTPError, SystemExit) as exc:
            print(json.dumps({"ok": False, "error": str(exc), "entry": hit}, indent=2))
            return 1
        payload = {
            "ok": True,
            "offline": False,
            "fetched": True,
            "entry": hit,
            "local_path": str(out.relative_to(ROOT)),
            "bytes": out.stat().st_size,
            "provider": source,
            "integration": "google-trends",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "cite": {
                "title": hit.get("topic") or hit.get("name"),
                "url": hit.get("html_url"),
                "date_accessed": date.today().isoformat(),
            },
        }
        print(json.dumps(payload, indent=2))
        return 0

    payload = search(
        query=args.query,
        year=args.year,
        ext=args.ext,
        folder=args.folder,
        num=args.num,
        offline=args.offline,
        refresh=args.refresh,
    )

    if args.save_vault:
        jp = save_vault(payload, args.query or args.year)
        write_markdown(payload, jp)
        payload["vault_json"] = str(jp.relative_to(ROOT))

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
