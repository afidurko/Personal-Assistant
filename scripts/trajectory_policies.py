"""Shared OCL/CPV trajectory policy application for Cam motor plans."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POL_PATH = ROOT / "config" / "connectome" / "trajectory-policies.json"


def load_policies() -> dict:
    return json.loads(POL_PATH.read_text(encoding="utf-8"))


def apply_policies(
    motor_plan: list[str],
    switch_state: dict[str, str],
    policies: list[dict] | None = None,
) -> tuple[list[str], list[dict]]:
    """Revise a motor plan against compositional / OCL policies.

    Returns (revised_plan, violations).
    """
    if policies is None:
        policies = load_policies().get("policies") or []
    plan = list(motor_plan)
    violations: list[dict] = []

    if switch_state.get("switch.kill") == "act":
        if plan:
            violations.append({"id": "kill_silences_all", "action": "clear_all_motors"})
        return [], violations

    for pol in policies:
        pid = pol.get("id", "")
        if_switch = pol.get("if_switch_act") or []
        if if_switch and any(switch_state.get(s) == "act" for s in if_switch):
            if pol.get("on_violate") == "clear_all_motors":
                if plan:
                    violations.append({"id": pid, "action": "clear_all_motors"})
                    plan = []
            continue

        if_any = set(pol.get("if_any_motors") or [])
        if_all = set(pol.get("if_all_motors") or [])
        extra = set(pol.get("if_any_motors_extra") or [])
        req = pol.get("require_switch_act") or []

        # Composition: all listed motors present
        if if_all and if_all.issubset(set(plan)):
            strip = [m for m in (pol.get("strip_motors") or []) if m in plan]
            for m in strip:
                plan.remove(m)
            violations.append(
                {
                    "id": pid,
                    "action": "strip",
                    "stripped": strip,
                    "revise_to": pol.get("revise_to"),
                }
            )
            continue

        # Any-motor trigger; optional extra motors (e.g. web_fetch + enhance)
        if if_any and (if_any & set(plan)):
            if extra and not (extra & set(plan)):
                continue
            # If require_switch_act listed, violation only when not all act
            if req:
                if all(switch_state.get(s) == "act" for s in req):
                    continue
            elif not extra:
                # bare if_any without requirements — only strip if policy says require was needed
                # Skip policies that are purely compositional (handled above) or switch-gated
                continue
            strip = [m for m in (pol.get("strip_motors") or []) if m in plan]
            for m in strip:
                plan.remove(m)
            if strip:
                violations.append(
                    {
                        "id": pid,
                        "action": "strip",
                        "stripped": strip,
                        "revise_to": pol.get("revise_to"),
                    }
                )
            continue

        # Switch requirement for motors without composition extras
        if if_any and req and (if_any & set(plan)):
            if not all(switch_state.get(s) == "act" for s in req):
                strip = [m for m in (pol.get("strip_motors") or list(if_any)) if m in plan]
                for m in strip:
                    plan.remove(m)
                violations.append(
                    {
                        "id": pid,
                        "action": "strip",
                        "stripped": strip,
                        "revise_to": pol.get("revise_to"),
                    }
                )

    return plan, violations
