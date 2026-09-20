#!/usr/bin/env python3
"""Cam avatar contract check — offline, no weights required.

Validates the avatar section of the home build plan against the checkout:
persona + portrait exist, muscle-grade spec is complete, tier ladder is sound,
gates reference real switches, and reports model-cache state via the
provisioner's cache layout. This is the plan section 3.2 step-5 check.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "config" / "system" / "build-plan.json"
SWITCHES = ROOT / "config" / "connectome" / "switches.json"
CACHE = ROOT / "data" / "models" / "avatar"

REQUIRED_MUSCLE = {
    "blendshapes": "arkit_52",
    "action_units": "facs",
    "grade": "human_believable",
}


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser(description="Cam avatar contract check")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    avatar = plan.get("avatar") or {}
    failures: list[str] = []
    warnings: list[str] = []

    for key in ("persona", "face_asset"):
        rel = avatar.get(key, "")
        if not rel or not (ROOT / rel).exists():
            failures.append(f"missing {key}: {rel}")

    spec = avatar.get("muscle_spec") or {}
    for key, want in REQUIRED_MUSCLE.items():
        if spec.get(key) != want:
            failures.append(f"muscle_spec.{key} must be {want}")
    if not (spec.get("target_fps_min") or 0) >= 25:
        failures.append("muscle_spec.target_fps_min must be >= 25")
    if not avatar.get("brain_rule"):
        failures.append("brain_rule missing — avatar must never be a second brain")

    sw_data = json.loads(SWITCHES.read_text(encoding="utf-8"))
    sw_items = sw_data.get("switches") if isinstance(sw_data, dict) else sw_data
    switch_ids = {s.get("id") for s in (sw_items or []) if isinstance(s, dict)}

    tiers = avatar.get("tiers") or []
    models = {}
    for tier in tiers:
        for sw in tier.get("requires_switch") or []:
            if sw not in switch_ids:
                failures.append(f"tier {tier.get('id')}: unknown switch {sw}")
        integ = tier.get("integration")
        if integ:
            p = ROOT / integ
            if not p.exists():
                failures.append(f"tier {tier.get('id')}: missing {integ}")
            elif p.is_dir() and not any(p.iterdir()):
                warnings.append(f"tier {tier.get('id')}: submodule not initialized {integ}")
        if tier.get("id") == "hf_realtime":
            models = tier.get("models") or {}

    cached = []
    for role, repo_id in sorted(models.items()):
        target = CACHE / repo_id.replace("/", "__")
        has = target.is_dir() and any(p.is_file() for p in target.rglob("*"))
        (cached if has else warnings).append(
            f"{role}: {repo_id}" if has else f"weights not cached: {role} {repo_id}"
        )

    report = {
        "at": utc(),
        "ok": not failures,
        "failures": failures,
        "warnings": warnings,
        "models_cached": cached,
        "tier_ids": [t.get("id") for t in tiers],
        "portrait": avatar.get("face_asset"),
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"avatar-check: {'OK' if report['ok'] else 'FAIL'} · tiers {report['tier_ids']}")
        for w in warnings:
            print(f"  warn: {w}")
        for f in failures:
            print(f"  FAIL: {f}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
