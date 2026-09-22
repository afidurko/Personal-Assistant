#!/usr/bin/env python3
"""Run allowlisted public-apis thin-wrapper add-ons for Cam agents.

Add-ons are curated no-auth (or free-tier) HTTP helpers discovered via the
public-apis catalog. Free-form URL fetch is intentionally forbidden — only
entries in config/integrations/public-apis-addons.json may be called.

Usage:
  python3 scripts/public-apis-addon.py --list
  python3 scripts/public-apis-addon.py call weather.open_meteo --latitude 40.7 --longitude -74.0 --offline
  python3 scripts/public-apis-addon.py call geo.open_meteo --name "Berlin" --offline
  python3 scripts/public-apis-addon.py doctor
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ADDONS_PATH = ROOT / "config" / "integrations" / "public-apis-addons.json"
PARENT_PATH = ROOT / "config" / "integrations" / "public-apis.json"


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


def render_url(template: str, params: dict[str, Any]) -> str:
    encoded = {}
    for k, v in params.items():
        if isinstance(v, str):
            encoded[k] = urllib.parse.quote(v, safe="")
        else:
            encoded[k] = v

    class _Safe(dict):
        def __missing__(self, key: str) -> str:  # type: ignore[override]
            raise KeyError(key)

    try:
        return template.format_map(_Safe(**encoded))
    except KeyError as exc:
        raise SystemExit(f"url_template missing param: {exc}") from exc


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


def http_get(url: str, timeout: int, user_agent: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "json" in ctype or body.lstrip().startswith(("{", "[")):
            return json.loads(body)
        return {"raw": body, "content_type": ctype}


def call_addon(
    addon_id: str,
    raw_params: dict[str, Any],
    *,
    offline: bool = False,
) -> dict:
    if kill_blocks():
        raise SystemExit("CAM_KILL set — refusing live/offline addon motor fire")

    cfg = load_addons()
    by_id = index_addons(cfg)
    if addon_id not in by_id:
        known = ", ".join(sorted(by_id))
        raise SystemExit(f"unknown addon id: {addon_id}. Known: {known}")
    spec = by_id[addon_id]
    params = coerce_params(spec, raw_params)
    defaults = cfg.get("defaults") or {}
    timeout = int(defaults.get("timeout_s") or 20)
    ua = str(defaults.get("user_agent") or "Cam-PublicAPIs-Addon/1.0")

    if offline:
        payload = load_fixture(spec)
        source = "fixture"
        url = None
    else:
        url = render_url(spec["url_template"], params)
        try:
            payload = http_get(url, timeout=timeout, user_agent=ua)
            source = "live"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            # Fall back to fixture so agents degrade gracefully
            payload = load_fixture(spec)
            source = f"fixture_after_error:{type(exc).__name__}"

    return {
        "ok": True,
        "addon_id": addon_id,
        "name": spec.get("name"),
        "catalog_name": spec.get("catalog_name"),
        "catalog_url": spec.get("catalog_url"),
        "category": spec.get("category"),
        "auth": spec.get("auth"),
        "params": params,
        "url": url,
        "provider": source,
        "offline": offline or str(source).startswith("fixture"),
        "result": payload,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "integration": "public-apis-addons",
        "parent": "public-apis",
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
                "category": a.get("category"),
                "auth": a.get("auth"),
                "purpose": a.get("purpose"),
                "catalog_url": a.get("catalog_url"),
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
        "ok": ADDONS_PATH.exists() and PARENT_PATH.exists() and not missing_fixtures,
        "addons_config": str(ADDONS_PATH.relative_to(ROOT)),
        "parent_config": PARENT_PATH.exists(),
        "addon_count": len(by_id),
        "missing_fixtures": missing_fixtures,
        "script": (ROOT / "scripts/public-apis-addon.py").exists(),
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
    call_p.add_argument("--latitude", type=float)
    call_p.add_argument("--longitude", type=float)
    call_p.add_argument("--days", type=int)
    call_p.add_argument("--name")
    call_p.add_argument("--count", type=int)
    call_p.add_argument("--ids")
    call_p.add_argument("--vs")
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
    for key in ("latitude", "longitude", "days", "name", "count", "ids", "vs"):
        val = getattr(args, key, None)
        if val is not None:
            raw[key] = val
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
