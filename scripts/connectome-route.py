#!/usr/bin/env python3
"""Route a sensory spike through Cam's connectome map to motor outputs.

Validates sense → center → switch → motor pathways using config/connectome/*.json.
Does not execute side effects — prints the motor plan Cam should run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "connectome"


def load(name: str):
    return json.loads((CFG / name).read_text(encoding="utf-8"))


def hotspots_for_sense(hotspots: dict, sense_id: str) -> list[dict]:
    primary = [
        h for h in hotspots["hotspots"] if h["pathway"] and h["pathway"][0] == sense_id
    ]
    if primary:
        return primary
    return [h for h in hotspots["hotspots"] if sense_id in h["pathway"]]


def pick_hotspot(
    candidates: list[dict], goal: str = "", hotspot_id: str | None = None
) -> dict | None:
    if not candidates:
        return None
    if hotspot_id:
        for h in candidates:
            if h["id"] == hotspot_id:
                return h
        return None
    if len(candidates) == 1 or not goal:
        return candidates[0]
    g = goal.lower()
    scored = []
    for h in candidates:
        blob = f"{h.get('id','')} {h.get('behavior','')} {h.get('center','')}".lower()
        score = sum(1 for token in g.split() if token and token in blob)
        if "doc" in g and "doc" in blob:
            score += 3
        if ("research" in g or "brief" in g) and "research" in blob:
            score += 3
        if ("job" in g or "career" in g) and "career" in blob:
            score += 3
        scored.append((score, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def resolve_switches(switches: dict, kill: bool, autonomy: bool) -> dict[str, str]:
    state = {}
    for s in switches["switches"]:
        sid = s["id"]
        if sid == "switch.kill":
            state[sid] = "act" if kill else "armed_allow_motor"
            continue
        if not autonomy and sid in {
            "switch.autonomy",
            "switch.outbound",
            "switch.careers_submit",
        }:
            state[sid] = "hold"
            continue
        state[sid] = "act"
    if kill:
        for sid in list(state):
            if sid != "switch.kill":
                state[sid] = "hold"
        state["switch.kill"] = "act"
    return state


def motor_allowed(
    motor_id: str,
    effector_reqs: dict[str, list[str]],
    switch_state: dict[str, str],
) -> bool:
    if switch_state.get("switch.kill") == "act":
        return False
    for req in effector_reqs.get(motor_id, []):
        if req == "switch.kill":
            # armed_allow_motor is the non-kill state
            if switch_state.get("switch.kill") == "act":
                return False
            continue
        if switch_state.get(req) == "hold":
            return False
    return True


def motors_from_pathway(
    pathway: list[str],
    switch_state: dict[str, str],
    effector_reqs: dict[str, list[str]],
) -> list[str]:
    if switch_state.get("switch.kill") == "act":
        return []
    if any(p.startswith("switch.") and switch_state.get(p) == "hold" for p in pathway):
        return []
    out = []
    for p in pathway:
        if p.startswith("motor.") and motor_allowed(p, effector_reqs, switch_state):
            out.append(p)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sense", required=True, help="sense.* id")
    parser.add_argument("--not-aaron", action="store_true", help="simulate unauthorized spike")
    parser.add_argument("--kill", action="store_true")
    parser.add_argument("--no-autonomy", action="store_true")
    parser.add_argument("--goal", default="", help="optional Aaron goal text")
    parser.add_argument("--hotspot", default="", help="explicit hotspot id when sense collides")
    args = parser.parse_args()

    sensory = load("sensory.json")
    switches = load("switches.json")
    motor = load("motor.json")
    hotspots = load("hotspots.json")
    synapses = load("synapses.json")

    sense_ids = {n["id"] for n in sensory["neurons"]}
    if args.sense not in sense_ids:
        raise SystemExit(f"unknown sense id: {args.sense}")

    if args.not_aaron:
        print(
            json.dumps(
                {
                    "accepted": False,
                    "reason": "switch.tasking hold — only Aaron may assign tasks",
                    "motor_plan": [],
                },
                indent=2,
            )
        )
        return 0

    switch_state = resolve_switches(
        switches, kill=args.kill, autonomy=not args.no_autonomy
    )
    effector_reqs = {
        e["id"]: list(e.get("requires_switch") or []) for e in motor["effectors"]
    }
    candidates = hotspots_for_sense(hotspots, args.sense)
    hotspot = pick_hotspot(candidates, args.goal, args.hotspot or None)

    if hotspot:
        pathway = list(hotspot["pathway"])
        planned_motors = motors_from_pathway(pathway, switch_state, effector_reqs)
        for side in hotspot.get("side_effects") or []:
            if side in planned_motors:
                continue
            if motor_allowed(side, effector_reqs, switch_state):
                planned_motors.append(side)
        behavior = hotspot["behavior"]
        center = hotspot["center"]
    else:
        pathway = [args.sense, "center.chief", "center.memory", "switch.autonomy", "motor.mesh"]
        planned_motors = (
            ["motor.mesh"]
            if motor_allowed("motor.mesh", effector_reqs, switch_state)
            else []
        )
        behavior = "generic_integrate_and_remember"
        center = "center.chief"

    known_motors = {e["id"] for e in motor["effectors"]}
    planned_motors = [m for m in planned_motors if m in known_motors]

    edge_pairs = {(e["from"], e["to"]) for e in synapses["edges"]}
    missing = []
    for a, b in zip(pathway, pathway[1:]):
        if (a, b) not in edge_pairs:
            missing.append([a, b])

    result = {
        "accepted": True,
        "sense": args.sense,
        "goal": args.goal,
        "center": center,
        "behavior": behavior,
        "hotspot_id": hotspot.get("id") if hotspot else None,
        "alt_hotspots": [
            h["id"] for h in candidates if not hotspot or h["id"] != hotspot.get("id")
        ],
        "pathway": pathway,
        "switch_state": switch_state,
        "motor_plan": planned_motors,
        "response_rule": motor["response_rule"],
        "missing_explicit_edges": missing[:10],
        "persona": {
            "name": "Cam",
            "voice": "soft airy fluent English",
            "sole_operator": "Aaron",
        },
    }
    if args.kill:
        result["accepted"] = False
        result["reason"] = "switch.kill act — all motor silenced"
        result["motor_plan"] = []
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
