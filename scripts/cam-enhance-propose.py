#!/usr/bin/env python3
"""Route a Cam enhancement proposal through the Aaron gate.

Does not mutate config unless --apply is set AND --aaron-approve is passed
(simulates switch.cam_enhance act). Default is propose-only motor plan.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_inproc  # noqa: E402


def route(enhance: bool) -> dict:
    return cam_inproc.route(
        sense="sense.chat.aaron",
        goal="apply cam enhance functionality from AGI scan proposal",
        hotspot="hotspot.cam_enhance",
        enhance=enhance,
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proposal", help="path to proposal markdown")
    p.add_argument(
        "--aaron-approve",
        action="store_true",
        help="Aaron enables switch.cam_enhance for this run",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Reserved: apply hooks (still requires --aaron-approve)",
    )
    args = p.parse_args()

    plan = route(enhance=args.aaron_approve)
    result = {
        "proposal": args.proposal,
        "aaron_approve": args.aaron_approve,
        "apply_requested": args.apply,
        "switch_cam_enhance": plan.get("switch_state", {}).get("switch.cam_enhance"),
        "motor_plan": plan.get("motor_plan"),
        "pathway": plan.get("pathway"),
        "behavior": plan.get("behavior"),
        "note": (
            "Functionality apply armed"
            if args.aaron_approve and "motor.enhance" in (plan.get("motor_plan") or [])
            else "Propose-only — Aaron has ultimate say (pass --aaron-approve to arm motor.enhance)"
        ),
    }
    if args.apply and not args.aaron_approve:
        result["ok"] = False
        result["error"] = "refusing apply without --aaron-approve (switch.cam_enhance)"
        print(json.dumps(result, indent=2))
        return 2
    if args.apply and args.aaron_approve:
        result["ok"] = True
        result["applied"] = False
        result["message"] = (
            "Gate open — implementer subagents would patch config from proposal; "
            "no automatic patch in this thin glue script (prefer explicit PR)."
        )
    else:
        result["ok"] = True
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
