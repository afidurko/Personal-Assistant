#!/usr/bin/env python3
"""Run allowlisted Google Trends dataset add-ons for Cam agents.

Add-ons are curated catalog searches and small dataset previews from
GoogleTrends/data. Free-form path fetch is forbidden — only entries in
config/integrations/google-trends-addons.json may be called.

Usage:
  python3 scripts/google-trends-addon.py list
  python3 scripts/google-trends-addon.py doctor
  python3 scripts/google-trends-addon.py call trends.search_election --offline
  python3 scripts/google-trends-addon.py call trends.dataset_game_theory --offline
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ADDONS_PATH = ROOT / "config" / "integrations" / "google-trends-addons.json"
PARENT_PATH = ROOT / "config" / "integrations" / "google-trends.json"
SEARCH = ROOT / "scripts" / "google-trends-search.py"


def load_addons() -> dict:
    if not ADDONS_PATH.exists():
        raise SystemExit(f"missing addons config: {ADDONS_PATH}")
    return json.loads(ADDONS_PATH.read_text(encoding="utf-8"))


def index_addons(cfg: dict) -> dict[str, dict]:
    return {a["id"]: a for a in cfg.get("addons") or [] if isinstance(a, dict) and a.get("id")}


def kill_blocks() -> bool:
    return os.environ.get("CAM_KILL", "").strip() in {"1", "true", "yes", "on"}


def coerce_params(spec: dict, raw: dict[str, Any]) -> dict[str, Any]:
    params_spec = spec.get("params") or {}
    out: dict[str, Any] = {}
    for name, meta in params_spec.items():
        if not isinstance(meta, dict):
            continue
        if name in raw and raw[name] is not None:
            val = raw[name]
        elif "default" in meta:
            val = meta["default"]
        elif meta.get("required"):
            raise SystemExit(f"missing required param: --{name}")
        else:
            continue
        typ = meta.get("type")
        if typ == "integer":
            val = int(val)
            if "min" in meta and val < meta["min"]:
                raise SystemExit(f"--{name} below min {meta['min']}")
            if "max" in meta and val > meta["max"]:
                raise SystemExit(f"--{name} above max {meta['max']}")
        elif typ == "number":
            val = float(val)
        else:
            val = str(val)
        out[name] = val
    return out


def load_fixture(spec: dict) -> dict:
    rel = spec.get("fixture")
    if not rel:
        raise SystemExit(f"addon {spec.get('id')} missing fixture")
    path = ROOT / rel
    if not path.exists():
        raise SystemExit(f"missing fixture: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = dict(data)
        data.setdefault("_fixture", True)
        return data
    return {"data": data, "_fixture": True}


def run_catalog_search(query: str, num: int, *, offline: bool) -> dict:
    cmd = [
        sys.executable,
        str(SEARCH),
        "--query",
        query,
        "--num",
        str(num),
    ]
    if offline:
        cmd.append("--offline")
    out = subprocess.check_output(cmd, text=True, cwd=str(ROOT))
    return json.loads(out)


def preview_dataset(path: str, preview_lines: int, *, offline: bool, ua: str) -> dict:
    raw_url = f"https://raw.githubusercontent.com/GoogleTrends/data/master/{path}"
    html_url = f"https://github.com/GoogleTrends/data/blob/master/{path}"
    if offline:
        # Caller should use fixture; this is a safety path
        return {
            "path": path,
            "raw_url": raw_url,
            "html_url": html_url,
            "preview": "",
            "preview_lines": 0,
            "note": "offline requires fixture",
        }
    req = urllib.request.Request(raw_url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=45) as resp:
        text = resp.read(200_000).decode("utf-8", errors="replace")
    lines = text.splitlines()[:preview_lines]
    return {
        "path": path,
        "raw_url": raw_url,
        "html_url": html_url,
        "preview": "\n".join(lines) + ("\n" if lines else ""),
        "preview_lines": len(lines),
        "bytes_read": min(len(text.encode("utf-8")), 200_000),
    }


def call_addon(
    addon_id: str,
    raw_params: dict[str, Any],
    *,
    offline: bool = False,
) -> dict:
    if kill_blocks():
        raise SystemExit("CAM_KILL set — refusing google-trends addon motor fire")

    cfg = load_addons()
    by_id = index_addons(cfg)
    if addon_id not in by_id:
        known = ", ".join(sorted(by_id))
        raise SystemExit(f"unknown addon id: {addon_id}. Known: {known}")
    spec = by_id[addon_id]
    params = coerce_params(spec, raw_params)
    defaults = cfg.get("defaults") or {}
    ua = str(defaults.get("user_agent") or "Cam-GoogleTrends-Addon/1.0")
    kind = spec.get("kind") or "catalog_search"

    if offline:
        payload = load_fixture(spec)
        source = "fixture"
    elif kind == "catalog_search":
        query = spec.get("query") or ""
        num = int(params.get("num") or defaults.get("num_results") or 5)
        try:
            payload = run_catalog_search(query, num, offline=False)
            source = payload.get("provider") or "live"
        except Exception as exc:  # noqa: BLE001
            payload = load_fixture(spec)
            source = f"fixture_after_error:{type(exc).__name__}"
    elif kind == "dataset_preview":
        path = spec.get("path") or ""
        preview_lines = int(params.get("preview_lines") or 20)
        try:
            payload = preview_dataset(path, preview_lines, offline=False, ua=ua)
            source = "live_raw"
        except (urllib.error.URLError, TimeoutError, UnicodeError) as exc:
            payload = load_fixture(spec)
            source = f"fixture_after_error:{type(exc).__name__}"
    else:
        raise SystemExit(f"unsupported addon kind: {kind}")

    return {
        "ok": True,
        "addon_id": addon_id,
        "name": spec.get("name"),
        "kind": kind,
        "query": spec.get("query"),
        "path": spec.get("path"),
        "purpose": spec.get("purpose"),
        "params": params,
        "provider": source,
        "offline": offline or str(source).startswith("fixture"),
        "result": payload,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "integration": "google-trends-addons",
        "parent": "google-trends",
        "source_repo": "github.com/GoogleTrends/data",
        "available_to": cfg.get("available_to"),
    }


def list_addons() -> dict:
    cfg = load_addons()
    items = []
    for a in cfg.get("addons") or []:
        items.append(
            {
                "id": a.get("id"),
                "name": a.get("name"),
                "kind": a.get("kind"),
                "purpose": a.get("purpose"),
                "query": a.get("query"),
                "path": a.get("path"),
                "params": list((a.get("params") or {}).keys()),
            }
        )
    return {
        "count": len(items),
        "addons": items,
        "available_to": cfg.get("available_to"),
        "rules": cfg.get("rules"),
    }


def doctor() -> dict:
    cfg = load_addons()
    by_id = index_addons(cfg)
    missing_fixtures = []
    for a in by_id.values():
        rel = a.get("fixture")
        if not rel or not (ROOT / rel).exists():
            missing_fixtures.append(a.get("id"))
    report = {
        "ok": ADDONS_PATH.exists() and PARENT_PATH.exists() and not missing_fixtures and SEARCH.exists(),
        "addons_config": str(ADDONS_PATH.relative_to(ROOT)),
        "parent_config": PARENT_PATH.exists(),
        "addon_count": len(by_id),
        "missing_fixtures": missing_fixtures,
        "script": (ROOT / "scripts/google-trends-addon.py").exists(),
        "search_script": SEARCH.exists(),
    }
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list allowlisted add-ons")
    sub.add_parser("doctor", help="verify add-on wiring + fixtures")

    call_p = sub.add_parser("call", help="call one allowlisted add-on")
    call_p.add_argument("addon_id")
    call_p.add_argument("--offline", action="store_true")
    call_p.add_argument("--num", type=int)
    call_p.add_argument("--preview-lines", type=int)
    call_p.add_argument("--json-params", help="extra JSON object of params")

    args = p.parse_args()
    if args.cmd == "list":
        print(json.dumps(list_addons(), indent=2))
        return 0
    if args.cmd == "doctor":
        report = doctor()
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") else 1

    raw: dict[str, Any] = {}
    if args.num is not None:
        raw["num"] = args.num
    if args.preview_lines is not None:
        raw["preview_lines"] = args.preview_lines
    if args.json_params:
        extra = json.loads(args.json_params)
        if not isinstance(extra, dict):
            raise SystemExit("--json-params must be an object")
        raw.update(extra)

    payload = call_addon(args.addon_id, raw, offline=bool(args.offline))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
