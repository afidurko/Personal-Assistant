#!/usr/bin/env python3
"""Validate the Cam home build plan against the actual checkout.

Offline, no network. Confirms config/system/build-plan.json is internally
coherent (priority ladder, avatar muscle spec, phases with exit checks) and
that every non-planned path it references exists in this environment, so plan
drift fails the bus loudly.
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

EXPECTED_PRIORITY_IDS = [
    "real_world_execution",
    "agi_assist",
    "human_ultimate_say",
    "interactivity_presence",
]
MUSCLE_KEYS = {
    "blendshapes",
    "action_units",
    "visemes_min",
    "target_fps_min",
    "first_lip_latency_ms_max",
    "blink_per_min",
    "grade",
    "exit_check",
}
HF_MODEL_KEYS = {"face_lipsync", "face_expression", "asr", "tts_fallback"}


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def path_status(rel: str) -> str:
    p = ROOT / rel
    if not p.exists():
        return "missing"
    if p.is_dir() and rel.startswith("integrations/") and not any(p.iterdir()):
        return "empty_submodule"
    return "ok"


def known_switch_ids() -> set[str]:
    data = json.loads(SWITCHES.read_text(encoding="utf-8"))
    items = data.get("switches") if isinstance(data, dict) else data
    return {s.get("id") for s in (items or []) if isinstance(s, dict)}


def check(plan: dict) -> dict:
    failures: list[str] = []
    warnings: list[str] = []
    landed_planned: list[str] = []

    def require_paths(rels: list[str], where: str) -> None:
        for rel in rels:
            st = path_status(rel)
            if st == "missing":
                failures.append(f"{where}: missing path {rel}")
            elif st == "empty_submodule":
                warnings.append(f"{where}: submodule not initialized {rel}")

    def note_planned(rels: list[str], where: str) -> None:
        for rel in rels:
            if path_status(rel) == "ok":
                landed_planned.append(f"{where}: planned path already landed {rel}")

    if plan.get("assistant") != "Cam" or plan.get("human") != "Aaron":
        failures.append("identity: assistant must be Cam and human must be Aaron")
    if path_status(plan.get("doc", "")) != "ok":
        failures.append(f"doc: missing {plan.get('doc')}")

    priorities = plan.get("priorities") or []
    ranks = [p.get("rank") for p in priorities]
    ids = [p.get("id") for p in priorities]
    if ranks != [1, 2, 3, 4]:
        failures.append(f"priorities: ranks must be exactly [1,2,3,4], got {ranks}")
    if ids != EXPECTED_PRIORITY_IDS:
        failures.append(f"priorities: ids must be {EXPECTED_PRIORITY_IDS}, got {ids}")
    for p in priorities:
        require_paths(p.get("enforced_by") or [], f"priority {p.get('id')}")
    p3 = next((p for p in priorities if p.get("id") == "human_ultimate_say"), {})
    if not (p3.get("hard_rules") or []):
        failures.append("priority human_ultimate_say: hard_rules must not be empty")

    home = plan.get("home") or {}
    require_paths(
        [home.get("registry", ""), home.get("bus", ""), home.get("connectome", "")]
        + (home.get("memory") or []),
        "home",
    )

    avatar = plan.get("avatar") or {}
    require_paths([avatar.get("persona", ""), avatar.get("face_asset", "")], "avatar")
    if not avatar.get("brain_rule"):
        failures.append("avatar: brain_rule required (avatar must never be a second brain)")
    missing_muscle = MUSCLE_KEYS - set((avatar.get("muscle_spec") or {}).keys())
    if missing_muscle:
        failures.append(f"avatar.muscle_spec: missing keys {sorted(missing_muscle)}")

    switch_ids = known_switch_ids()
    tiers = avatar.get("tiers") or []
    tier_ids = {t.get("id") for t in tiers}
    for expected in ("hf_realtime", "studio_full_presence", "custom_finetune"):
        if expected not in tier_ids:
            failures.append(f"avatar.tiers: missing tier {expected}")
    for tier in tiers:
        where = f"avatar.tier {tier.get('id')}"
        for sw in tier.get("requires_switch") or []:
            if sw not in switch_ids:
                failures.append(f"{where}: unknown switch {sw}")
        if not tier.get("requires_switch"):
            failures.append(f"{where}: requires_switch must not be empty")
        if tier.get("id") == "hf_realtime":
            models = tier.get("models") or {}
            missing = HF_MODEL_KEYS - set(models.keys())
            if missing:
                failures.append(f"{where}: models missing {sorted(missing)}")
            require_paths(
                [tier.get("tts_primary", ""), tier.get("identity_gate", "")], where
            )
            note_planned(tier.get("planned_paths") or [], where)
        if tier.get("integration"):
            require_paths([tier["integration"]], where)
        if tier.get("policy"):
            require_paths([tier["policy"]], where)

    channels = (plan.get("auto_update") or {}).get("channels") or []
    if len(channels) < 3:
        failures.append("auto_update: at least 3 channels required")
    for ch in channels:
        where = f"auto_update.{ch.get('id')}"
        require_paths(ch.get("paths") or [], where)
        note_planned(ch.get("planned_paths") or [], where)

    phases = plan.get("phases") or []
    if len(phases) < 5:
        failures.append("phases: at least 5 phases required")
    last_priority = 0
    for ph in phases:
        where = f"phase {ph.get('id')}"
        for key in ("id", "priority", "title", "status", "exit_check"):
            if not ph.get(key):
                failures.append(f"{where}: missing {key}")
        pr = ph.get("priority") or 0
        if pr not in (1, 2, 3, 4):
            failures.append(f"{where}: priority must be 1..4")
        if pr < last_priority:
            failures.append(f"{where}: phases must be ordered by priority ladder")
        last_priority = max(last_priority, pr)

    return {
        "at": utc(),
        "ok": not failures,
        "plan": plan.get("id"),
        "failures": failures,
        "warnings": warnings,
        "landed_planned": landed_planned,
        "priority_order": ids,
        "tier_count": len(tiers),
        "phase_count": len(phases),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate Cam home build plan")
    ap.add_argument("--json", action="store_true", help="print JSON report")
    args = ap.parse_args()

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    report = check(plan)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"build-plan: {report['plan']} — {'OK' if report['ok'] else 'FAIL'}")
        print(f"priorities: {' > '.join(report['priority_order'])}")
        print(f"avatar tiers: {report['tier_count']} · phases: {report['phase_count']}")
        for w in report["warnings"]:
            print(f"  warn: {w}")
        for note in report["landed_planned"]:
            print(f"  note: {note}")
        for f in report["failures"]:
            print(f"  FAIL: {f}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
