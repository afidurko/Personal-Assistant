#!/usr/bin/env python3
"""Provision Cam avatar model weights from the home build plan.

Resolves the Hugging Face model list for the `hf_realtime` avatar tier from
config/system/build-plan.json and reports (or downloads) them into a local
cache. Offline-safe: restricted egress reports what is missing instead of
failing. Weights are opt-in downloads and never land in git.

Examples:
  python3 scripts/avatar-fetch-models.py            # report cache status
  python3 scripts/avatar-fetch-models.py --json
  python3 scripts/avatar-fetch-models.py --download # fetch missing (needs egress + huggingface_hub)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config" / "system" / "build-plan.json"
DEFAULT_CACHE = ROOT / "data" / "models" / "avatar"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hf_tier(plan: dict) -> dict:
    for tier in (plan.get("avatar") or {}).get("tiers") or []:
        if tier.get("id") == "hf_realtime":
            return tier
    return {}


def cache_state(cache: Path, repo_id: str) -> dict:
    """A model is cached when its directory exists and holds any real file."""
    target = cache / repo_id.replace("/", "__")
    files = (
        [p for p in target.rglob("*") if p.is_file()] if target.is_dir() else []
    )
    return {
        "repo_id": repo_id,
        "path": str(target.relative_to(ROOT)),
        "cached": bool(files),
        "files": len(files),
    }


def download(cache: Path, repo_id: str) -> dict:
    state = cache_state(cache, repo_id)
    if state["cached"]:
        state["action"] = "already_cached"
        return state
    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except ImportError:
        state["action"] = "skipped_no_huggingface_hub"
        return state
    target = cache / repo_id.replace("/", "__")
    try:
        snapshot_download(repo_id=repo_id, local_dir=str(target))
        state = cache_state(cache, repo_id)
        state["action"] = "downloaded"
    except Exception as e:  # egress blocked / auth — report, never crash
        state["action"] = f"download_failed: {str(e)[:160]}"
    return state


def main() -> int:
    ap = argparse.ArgumentParser(description="Provision Cam avatar models (HF tier)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--download", action="store_true", help="fetch missing weights")
    ap.add_argument(
        "--cache",
        default=os.environ.get("CAM_AVATAR_MODEL_CACHE", str(DEFAULT_CACHE)),
    )
    args = ap.parse_args()

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    tier = hf_tier(plan)
    models = tier.get("models") or {}
    cache = Path(args.cache)

    entries = []
    for role, repo_id in sorted(models.items()):
        state = (
            download(cache, repo_id) if args.download else cache_state(cache, repo_id)
        )
        state["role"] = role
        entries.append(state)

    report = {
        "at": utc(),
        "tier": "hf_realtime",
        "cache": str(cache),
        "models": entries,
        "cached_count": sum(1 for e in entries if e["cached"]),
        "model_count": len(entries),
        "ok": bool(entries),
        "note": "offline-safe: missing weights are reported, not fatal",
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"avatar models [{report['cached_count']}/{report['model_count']} cached] → {cache}")
        for e in entries:
            mark = "✓" if e["cached"] else "·"
            action = f" ({e['action']})" if e.get("action") else ""
            print(f"  {mark} {e['role']}: {e['repo_id']}{action}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
