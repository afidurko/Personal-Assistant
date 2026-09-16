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
    primary = [h for h in hotspots["hotspots"] if h["pathway"] and h["pathway"][0] == sense_id]
    if primary:
        return primary
    return [h for h in hotspots["hotspots"] if sense_id in h["pathway"]]


def pick_hotspot(candidates: list[dict], goal: str = "") -> dict | None:
    if not candidates:
        return None
    if len(candidates) == 1 or not goal:
        return candidates[0]
    g = goal.lower()
    scored = []
    for h in candidates:
        blob = f"{h.get('id','')} {h.get('behavior','')} {h.get('center','')}".lower()
        score = sum(1 for token in g.split() if token and token in blob)
        # light keyword boosts
        if "doc" in g and "doc" in blob:
            score += 3
        if "research" in g or "brief" in g:
            if "research" in blob:
                score += 3
        if "job" in g or "career" in g:
            if "career" in blob:
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
        default = s.get("default", "act")
        if default in {"standing_on", "act_under_autonomy", "studio_when_available", "aaron_only"}:
            state[sid] = "act"
        else:
            state[sid] = "act"
    if kill:
        for sid in list(state):
            if sid != "switch.kill":
                state[sid] = "hold"
        state["switch.kill"] = "act"
    return state


def motors_from_pathway(pathway: list[str], switch_state: dict[str, str]) -> list[str]:
    motors = [p for p in pathway if p.startswith("motor.")]
    # If pathway lists motors after a switch, honor hold
    if any(p.startswith("switch.") and switch_state.get(p) == "hold" for p in pathway):
        return []
    if switch_state.get("switch.kill") == "act":
        return []
    return motors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sense", required=True, help="sense.* id")
    parser.add_argument("--from-aaron", action="store_true", default=True)
    parser.add_argument("--not-aaron", action="store_true", help="simulate unauthorized spike")
    parser.add_argument("--kill", action="store_true")
    parser.add_argument("--no-autonomy", action="store_true")
    parser.add_argument("--goal", default="", help="optional Aaron goal text")
    args = parser.parse_args()

    sensory = load("sensory.json")
    centers = load("centers.json")
    switches = load("switches.json")
    motor = load("motor.json")
    hotspots = load("hotspots.json")
    synapses = load("synapses.json")

    sense_ids = {n["id"] for n in sensory["neurons"]}
    if args.sense not in sense_ids:
        raise SystemExit(f"unknown sense id: {args.sense}")

    if args.not_aaron or (args.sense == "sense.chat.aaron" and args.not_aaron):
        print(json.dumps({
            "accepted": False,
            "reason": "switch.tasking hold — only Aaron may assign tasks",
            "motor": [],
        }, indent=2))
        return 0

    switch_state = resolve_switches(switches, kill=args.kill, autonomy=not args.no_autonomy)
    candidates = hotspots_for_sense(hotspots, args.sense)
    hotspot = pick_hotspot(candidates, args.goal)

    if hotspot:
        pathway = list(hotspot["pathway"])
        planned_motors = motors_from_pathway(pathway, switch_state)
        for side in hotspot.get("side_effects") or []:
            if side not in planned_motors and switch_state.get("switch.kill") != "act":
                planned_motors.append(side)
        behavior = hotspot["behavior"]
        center = hotspot["center"]
    else:
        pathway = [args.sense, "center.chief", "center.memory", "motor.mesh"]
        planned_motors = [] if switch_state.get("switch.kill") == "act" else ["motor.mesh"]
        behavior = "generic_integrate_and_remember"
        center = "center.chief"

    # Validate motors exist
    known_motors = {e["id"] for e in motor["effectors"]}
    planned_motors = [m for m in planned_motors if m in known_motors]

    # Synapse existence check (soft)
    edge_pairs = {(e["from"], e["to"]) for e in synapses["edges"]}
    missing = []
    for a, b in zip(pathway, pathway[1:]):
        if a.startswith("motor.") or b.startswith("motor."):
            continue
        if (a, b) not in edge_pairs and not a.startswith("switch.") and not b.startswith("switch."):
            # switches may not be fully edged for all pairs; warn lightly
            missing.append([a, b])

    result = {
        "accepted": True,
        "sense": args.sense,
        "goal": args.goal,
        "center": center,
        "behavior": behavior,
        "hotspot_id": hotspot.get("id") if hotspot else None,
        "alt_hotspots": [h["id"] for h in candidates if not hotspot or h["id"] != hotspot.get("id")],
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
