#!/usr/bin/env python3
"""Validate / demo Cam trajectory (OCL/CPV) policies against connectome-route plans."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trajectory_policies as tp  # noqa: E402


def route(**kwargs) -> dict:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "connectome-route.py"),
        "--sense",
        kwargs.get("sense", "sense.chat.aaron"),
    ]
    if kwargs.get("goal"):
        cmd += ["--goal", kwargs["goal"]]
    if kwargs.get("hotspot"):
        cmd += ["--hotspot", kwargs["hotspot"]]
    if kwargs.get("enhance"):
        cmd.append("--enhance")
    if kwargs.get("kill"):
        cmd.append("--kill")
    return json.loads(subprocess.check_output(cmd, text=True))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    cfg = tp.load_policies()
    errors: list[str] = []
    demos = []

    r1 = route(sense="sense.chat.aaron", goal="apply enhance", hotspot="hotspot.cam_enhance")
    if "motor.enhance" in (r1.get("motor_plan") or []):
        errors.append("enhance_fired_without_aaron")
    demos.append(
        {
            "case": "enhance_hold",
            "motor_plan": r1.get("motor_plan"),
            "violations": r1.get("trajectory_violations"),
        }
    )

    r2 = route(
        sense="sense.chat.aaron",
        goal="apply enhance",
        hotspot="hotspot.cam_enhance",
        enhance=True,
    )
    if "motor.enhance" not in (r2.get("motor_plan") or []):
        errors.append("enhance_missing_when_aaron_approved")
    demos.append({"case": "enhance_act", "motor_plan": r2.get("motor_plan")})

    r3 = route(sense="sense.chat.aaron", goal="hi", kill=True)
    if r3.get("motor_plan"):
        errors.append("kill_left_motors")
    demos.append({"case": "kill", "motor_plan": r3.get("motor_plan")})

    synth_state = dict(r2.get("switch_state") or {})
    synth_state["switch.cam_enhance"] = "act"
    plan4, v4 = tp.apply_policies(
        ["motor.jobs", "motor.enhance", "motor.mesh"], synth_state
    )
    if "motor.enhance" in plan4:
        errors.append("cpv_enhance_jobs_not_stripped")
    if "motor.jobs" not in plan4:
        errors.append("cpv_jobs_should_remain")
    demos.append({"case": "enhance_plus_jobs", "motor_plan": plan4, "violations": v4})

    # outbound hold
    hold_state = dict(r1.get("switch_state") or {})
    hold_state["switch.outbound"] = "hold"
    plan5, v5 = tp.apply_policies(
        ["motor.text", "motor.mesh"], hold_state
    )
    if "motor.text" in plan5:
        errors.append("outbound_not_stripped_on_hold")
    if "motor.mesh" not in plan5:
        errors.append("mesh_should_remain_when_outbound_held")
    demos.append({"case": "outbound_hold", "motor_plan": plan5, "violations": v5})

    # VoiceStudio file render alone is OK; audible speak still needs outbound+presence
    vs_state = dict(r1.get("switch_state") or {})
    vs_state["switch.outbound"] = "hold"
    vs_state["switch.presence"] = "hold"
    plan6, v6 = tp.apply_policies(
        ["motor.voicestudio", "motor.speak", "motor.mesh"], vs_state
    )
    if "motor.speak" in plan6:
        errors.append("voicestudio_audible_not_stripped_when_outbound_held")
    if "motor.voicestudio" not in plan6:
        errors.append("voicestudio_api_should_remain_for_file_render")
    if "motor.mesh" not in plan6:
        errors.append("mesh_should_remain_with_voicestudio")
    demos.append({"case": "voicestudio_file_only", "motor_plan": plan6, "violations": v6})

    # identity hold → speak stripped (FunASR Aaron gate)
    id_state = dict(r1.get("switch_state") or {})
    id_state["switch.identity"] = "hold"
    plan7, v7 = tp.apply_policies(["motor.speak", "motor.mesh"], id_state)
    if "motor.speak" in plan7:
        errors.append("speak_not_stripped_on_identity_hold")
    if "motor.mesh" not in plan7:
        errors.append("mesh_should_remain_when_identity_held")
    demos.append({"case": "identity_hold_speak", "motor_plan": plan7, "violations": v7})

    if cfg.get("status") != "applied":
        errors.append("policies_not_applied")

    report = {
        "ok": not errors,
        "errors": errors,
        "policy_count": len(cfg.get("policies") or []),
        "demos": demos,
        "config": "config/connectome/trajectory-policies.json",
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"trajectory-policy-check: {'PASS' if report['ok'] else 'FAIL'}")
        for e in errors:
            print(f"  HARD {e}")
        print(f"  policies={report['policy_count']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
