#!/usr/bin/env python3
"""MemoryBear client — cognitive memory read/write for Cam.

Connectome:
  sense.memorybear.hit → center.memory → switch.autonomy → motor.memorybear

Usage:
  python3 scripts/memorybear.py --doctor --offline
  python3 scripts/memorybear.py read --query "Aaron prefs" --offline
  python3 scripts/memorybear.py write --message "Prefer soft airy voice" --offline
  python3 scripts/memorybear.py read --query "open projects"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "integrations" / "memorybear.json"
SAMPLE_READ = ROOT / "scripts" / "testdata" / "sample-memorybear-read.json"
sys.path.insert(0, str(ROOT / "scripts"))
import cam_privacy as privacy  # noqa: E402


def require_owner_memory() -> None:
    """Charter P4: MemoryBear (and its vault mirror) is the owner's memory,
    keyed by the owner's end_user_id. A guest principal never reads or writes
    it — their memory lives in their own root and nowhere else."""
    pid = privacy.current_principal()
    if pid != privacy.OWNER:
        raise SystemExit(f"memorybear is owner-only memory; principal {pid!r} keeps memory in "
                         f"data/principals/{pid}/ (no shared memory between people)")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def env_or_cfg(*keys: str, default: str | None = None) -> str | None:
    for key in keys:
        val = os.environ.get(key)
        if val:
            return val
    return default


def api_base(cfg: dict) -> str:
    provider = cfg.get("provider") or {}
    env_name = provider.get("api_base_env") or "MEMORYBEAR_API_BASE"
    return (
        env_or_cfg(env_name, "MEMORYBEAR_BASE_URL")
        or provider.get("api_base_default")
        or "http://127.0.0.1:8002"
    ).rstrip("/")


def api_key(cfg: dict) -> str | None:
    provider = cfg.get("provider") or {}
    env_name = provider.get("credential_env") or "MEMORYBEAR_API_KEY"
    return env_or_cfg(env_name)


def end_user_id(cfg: dict) -> str | None:
    provider = cfg.get("provider") or {}
    env_name = provider.get("end_user_env") or "MEMORYBEAR_END_USER_ID"
    return env_or_cfg(env_name, "MEMORYBEAR_USER_ID")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_vault(payload: dict, slug: str) -> Path:
    cfg = load_config()
    vault_rel = cfg.get("vault_dir") or "vault/10-Mesh-Distillates/memorybear"
    day = date.today().isoformat()
    out_dir = ROOT / vault_rel / day
    out_dir.mkdir(parents=True, exist_ok=True)
    clean = "".join(c if c.isalnum() or c in "-_" else "-" for c in slug.strip().lower())[:48]
    path = out_dir / f"{clean or 'memorybear'}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def http_json(
    method: str,
    url: str,
    *,
    key: str,
    body: dict | None = None,
    timeout: float = 45.0,
) -> dict:
    data = None
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": "Cam-MemoryBear/1.0",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise SystemExit(f"MemoryBear HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"MemoryBear unreachable: {exc.reason}") from exc


def offline_read(query: str, search_switch: str) -> dict:
    raw = json.loads(SAMPLE_READ.read_text(encoding="utf-8"))
    raw["query"] = query
    raw["search_switch"] = search_switch
    raw["fetched_at"] = utc_now()
    raw["sense"] = "sense.memorybear.hit"
    raw["motor"] = "motor.memorybear"
    return raw


def offline_write(message: str) -> dict:
    return {
        "provider": "fixture",
        "offline": True,
        "ok": True,
        "operation": "write",
        "message": message,
        "msg_id": "mem-fixture-write-1",
        "fetched_at": utc_now(),
        "sense": "sense.memorybear.hit",
        "motor": "motor.memorybear",
    }


def live_read(cfg: dict, query: str, search_switch: str, enable_rerank: bool) -> dict:
    key = api_key(cfg)
    euid = end_user_id(cfg)
    if not key or not euid:
        raise SystemExit(
            "MEMORYBEAR_API_KEY and MEMORYBEAR_END_USER_ID required for live reads. "
            "Use --offline for dry runs."
        )
    endpoints = cfg.get("endpoints") or {}
    path = endpoints.get("read_sync") or "/v1/memory/read/sync"
    url = f"{api_base(cfg)}{path}"
    body = {
        "end_user_id": euid,
        "message": query,
        "search_switch": search_switch,
        "enable_rerank": enable_rerank,
    }
    resp = http_json("POST", url, key=key, body=body)
    data = resp.get("data") if isinstance(resp, dict) else None
    if not isinstance(data, dict):
        data = resp if isinstance(resp, dict) else {"raw": resp}
    return {
        "provider": "memorybear_v1",
        "offline": False,
        "ok": True,
        "operation": "read",
        "query": query,
        "search_switch": search_switch,
        "answer": data.get("answer") or data.get("content"),
        "intermediate_outputs": data.get("intermediate_outputs") or data.get("memories") or [],
        "raw": resp,
        "fetched_at": utc_now(),
        "sense": "sense.memorybear.hit",
        "motor": "motor.memorybear",
        "api_base": api_base(cfg),
    }


def live_write(cfg: dict, message: str) -> dict:
    key = api_key(cfg)
    euid = end_user_id(cfg)
    if not key or not euid:
        raise SystemExit(
            "MEMORYBEAR_API_KEY and MEMORYBEAR_END_USER_ID required for live writes. "
            "Use --offline for dry runs."
        )
    endpoints = cfg.get("endpoints") or {}
    path = endpoints.get("write") or "/v1/memory/write"
    url = f"{api_base(cfg)}{path}"
    body = {"end_user_id": euid, "message": message}
    resp = http_json("POST", url, key=key, body=body)
    data = resp.get("data") if isinstance(resp, dict) else None
    if not isinstance(data, dict):
        data = resp if isinstance(resp, dict) else {"raw": resp}
    return {
        "provider": "memorybear_v1",
        "offline": False,
        "ok": True,
        "operation": "write",
        "message": message,
        "msg_id": data.get("msg_id") or data.get("id") or data.get("task_id"),
        "raw": resp,
        "fetched_at": utc_now(),
        "sense": "sense.memorybear.hit",
        "motor": "motor.memorybear",
        "api_base": api_base(cfg),
    }


def doctor(cfg: dict, offline: bool) -> dict:
    report = {
        "ok": True,
        "offline": offline,
        "config_path": str(CONFIG_PATH.relative_to(ROOT)),
        "config_present": CONFIG_PATH.exists(),
        "submodule": "integrations/memorybear",
        "submodule_populated": any(
            p.name != ".git" for p in (ROOT / "integrations" / "memorybear").iterdir()
        )
        if (ROOT / "integrations" / "memorybear").exists()
        else False,
        "api_base": api_base(cfg),
        "api_key_set": bool(api_key(cfg)),
        "end_user_set": bool(end_user_id(cfg)),
        "sense": cfg.get("sense"),
        "motor": cfg.get("motor"),
        "mesh_namespace": cfg.get("mesh_namespace"),
        "fetched_at": utc_now(),
    }
    if not report["config_present"]:
        report["ok"] = False
        report["error"] = "missing config/integrations/memorybear.json"
        return report
    if offline:
        sample = offline_read("doctor smoke", "express")
        report["fixture_ok"] = bool(sample.get("answer"))
        report["ok"] = report["ok"] and report["fixture_ok"]
        return report
    # Live: optional lightweight GET of service info if key present
    if not report["api_key_set"]:
        report["ok"] = False
        report["error"] = "MEMORYBEAR_API_KEY not set (use --offline)"
        return report
    url = f"{api_base(cfg)}/v1/memory"
    try:
        http_json("GET", url, key=api_key(cfg) or "", timeout=10.0)
        report["live_reachable"] = True
    except SystemExit as exc:
        report["ok"] = False
        report["live_reachable"] = False
        report["error"] = str(exc)
    return report


def main() -> int:
    cfg = load_config()
    defaults = cfg.get("defaults") or {}
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--offline", action="store_true", help="use fixtures; no network")
    common.add_argument("--json", action="store_true", help="force JSON stdout")
    common.add_argument("--save-vault", action="store_true", default=False)
    common.add_argument("--no-save-vault", action="store_true")

    parser = argparse.ArgumentParser(description=__doc__, parents=[common])
    parser.add_argument("--doctor", action="store_true", help="wiring / credential smoke")
    sub = parser.add_subparsers(dest="cmd")

    p_read = sub.add_parser("read", help="Recall via /v1/memory/read/sync", parents=[common])
    p_read.add_argument("--query", required=True)
    p_read.add_argument(
        "--search-switch",
        default=defaults.get("search_switch") or "express",
        choices=["deep", "normal", "quick", "express", "meta"],
    )
    p_read.add_argument("--rerank", action="store_true")

    p_write = sub.add_parser("write", help="Persist via /v1/memory/write", parents=[common])
    p_write.add_argument("--message", required=True)

    args = parser.parse_args()
    require_owner_memory()
    save_vault_flag = bool(defaults.get("save_to_vault")) or args.save_vault
    if args.no_save_vault:
        save_vault_flag = False

    if args.doctor or args.cmd is None:
        payload = doctor(cfg, offline=args.offline or not api_key(cfg))
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("ok") else 1

    if args.cmd == "read":
        payload = (
            offline_read(args.query, args.search_switch)
            if args.offline
            else live_read(cfg, args.query, args.search_switch, args.rerank)
        )
        if save_vault_flag:
            path = save_vault(payload, f"read-{args.query}")
            payload["vault_path"] = str(path.relative_to(ROOT))
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("ok", True) else 1

    if args.cmd == "write":
        payload = (
            offline_write(args.message) if args.offline else live_write(cfg, args.message)
        )
        if save_vault_flag:
            path = save_vault(payload, f"write-{args.message[:40]}")
            payload["vault_path"] = str(path.relative_to(ROOT))
        print(json.dumps(payload, indent=2))
        return 0 if payload.get("ok", True) else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
