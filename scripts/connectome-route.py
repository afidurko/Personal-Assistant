#!/usr/bin/env python3
"""Route a sensory spike through Cam's connectome map to motor outputs.

Validates sense → Brodmann area → switch → motor pathways using config/connectome/*.json.
Does not execute side effects — prints the motor plan Cam should run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "connectome"
import sys
sys.path.insert(0, str(ROOT / "scripts"))
import cam_workspaces as cw  # noqa: E402
import trajectory_policies as tp  # noqa: E402


_LOAD_CACHE: dict[str, object] = {}


def load(name: str):
    if name not in _LOAD_CACHE:
        _LOAD_CACHE[name] = json.loads((CFG / name).read_text(encoding="utf-8"))
    return _LOAD_CACHE[name]


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
        blob = f"{h.get('id','')} {h.get('behavior','')} {h.get('center','')} {h.get('area','')}".lower()
        score = sum(1 for token in g.split() if token and token in blob)
        if "doc" in g and "doc" in blob:
            score += 3
        if ("research" in g or "brief" in g) and "research" in blob:
            score += 3
        if ("job" in g or "career" in g) and "career" in blob:
            score += 3
        if ("qa" in g or "conflict" in g) and (
            "qa" in blob or "conflict" in blob or "cycle" in blob
        ):
            score += 4
        # "loop" alone is too common in ordinary chat — require qa/conflict context
        if "loop" in g and ("qa" in g or "conflict" in g) and (
            "qa" in blob or "conflict" in blob or "cycle" in blob
        ):
            score += 2
        if ("ios" in g or "swift" in g or "stack" in g) and (
            "ios" in blob or "swift" in blob or "stack" in blob or "cartograph" in blob
        ):
            score += 4
        if ("map" in g or "mind" in g or "cartograph" in g) and (
            "map" in blob or "cartograph" in blob or "knowledge" in blob
        ):
            score += 3
        if ("agi" in g or "arxiv" in g or "paper" in g or "scan" in g) and (
            "agi" in blob or "arxiv" in blob or "scan" in blob
        ):
            score += 4
        if ("enhance" in g or "upgrade" in g) and "enhance" in blob:
            score += 4
        if ("slm" in g or "small language" in g) and "slm" in blob:
            score += 4
        if ("embed" in g or "deep learning" in g or " dl" in f" {g}") and "dl" in blob:
            score += 4
        if ("info" in g or "lookup" in g or "find out" in g) and "info" in blob:
            score += 3
        if ("capability" in g or "complete" in g or "team" in g) and "capability" in blob:
            score += 3
        if any(
            tok in g
            for tok in (
                "public api",
                "public-apis",
                "free api",
                "api catalog",
                "open api list",
            )
        ) and ("public_apis" in blob or "public-apis" in blob or "api" in blob):
            score += 5
        if any(
            tok in g
            for tok in (
                "google trends",
                "google-trends",
                "trends data",
                "trends dataset",
                "search interest",
            )
        ) and ("google_trends" in blob or "trends" in blob):
            score += 5
        if any(
            tok in g
            for tok in (
                "inkbox",
                "agent identity",
                "agent email",
                "agent phone",
                "provision phone",
                "inkbox vault",
                "inkbox tunnel",
            )
        ) and ("inkbox" in blob or "identity" in blob or "comms" in blob or "email" in blob):
            score += 5
        if any(
            tok in g
            for tok in (
                "loop engineering",
                "loop-engineering",
                "loop audit",
                "loop-audit",
                "daily triage",
                "pr babysitter",
                "loop run",
                "motor.loop",
            )
        ) and ("loop" in blob or "triage" in blob or "qa" in blob or "cingulate" in blob):
            score += 5
        if any(
            tok in g
            for tok in (
                "code",
                "coding",
                "cline",
                "refactor",
                "implement",
                "pr ",
                "pull request",
                "test suite",
                "typescript",
                "python script",
            )
        ) and ("coding" in blob or "cline" in blob):
            score += 5
        if any(
            tok in g
            for tok in (
                "voicestudio",
                "omnivoice",
                "voice clone",
                "voice cloning",
                "local tts",
                "dubbing",
                "audiobook",
            )
        ) and ("voicestudio" in blob or "voice" in blob):
            score += 5
        scored.append((score, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def resolve_switches(
    switches: dict,
    kill: bool,
    autonomy: bool,
    enhance: bool = False,
    research_scan: bool = True,
    slm: bool = True,
    dl: bool = True,
) -> dict[str, str]:
    """Resolve circuit switches. cam_enhance stays hold unless Aaron enables it."""
    state = {}
    hold_when_no_autonomy = {
        "switch.autonomy",
        "switch.outbound",
        "switch.careers_submit",
        "switch.research_scan",
        "switch.slm_local",
        "switch.dl_local",
    }
    for s in switches["switches"]:
        sid = s["id"]
        default = (s.get("default") or "").lower()
        if sid == "switch.kill":
            state[sid] = "act" if kill else "armed_allow_motor"
            continue
        if sid == "switch.cam_enhance":
            # Aaron ultimate say — propose-only until explicitly enabled
            state[sid] = "act" if enhance else "hold"
            continue
        if sid == "switch.research_scan" and not research_scan:
            state[sid] = "hold"
            continue
        if sid == "switch.slm_local" and not slm:
            state[sid] = "hold"
            continue
        if sid == "switch.dl_local" and not dl:
            state[sid] = "hold"
            continue
        if not autonomy and sid in hold_when_no_autonomy:
            state[sid] = "hold"
            continue
        if default == "hold" or default.startswith("hold"):
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


def route(
    *,
    sense: str,
    goal: str = "",
    hotspot: str | None = None,
    kill: bool = False,
    enhance: bool = False,
    not_aaron: bool = False,
    no_autonomy: bool = False,
    workspace_id: str = "",
    role: str = "",
    research_scan: bool = True,
    slm: bool = True,
    dl: bool = True,
) -> dict:
    """In-process connectome route. Same payload as the CLI."""
    sensory = load("sensory.json")
    switches = load("switches.json")
    motor = load("motor.json")
    hotspots = load("hotspots.json")
    synapses = load("synapses.json")

    sense_ids = {n["id"] for n in sensory["neurons"]}
    if sense not in sense_ids:
        raise ValueError(f"unknown sense id: {sense}")

    if not_aaron:
        return {
            "accepted": False,
            "reason": "switch.tasking hold — only Aaron may assign tasks",
            "motor_plan": [],
        }

    switch_state = resolve_switches(
        switches,
        kill=kill,
        autonomy=not no_autonomy,
        enhance=enhance,
        research_scan=research_scan,
        slm=slm,
        dl=dl,
    )
    effector_reqs = {
        e["id"]: list(e.get("requires_switch") or []) for e in motor["effectors"]
    }
    candidates = hotspots_for_sense(hotspots, sense)
    picked = pick_hotspot(candidates, goal, hotspot or None)

    if picked:
        pathway = list(picked["pathway"])
        planned_motors = motors_from_pathway(pathway, switch_state, effector_reqs)
        for side in picked.get("side_effects") or []:
            if side in planned_motors:
                continue
            if motor_allowed(side, effector_reqs, switch_state):
                planned_motors.append(side)
        behavior = picked["behavior"]
        center = picked.get("area") or picked.get("center")
        columns = picked.get("columns") or []
        tracts = picked.get("tracts") or []
    else:
        pathway = [sense, "area.wernicke", "area.dlpfc", "area.mtl", "switch.autonomy", "motor.mesh"]
        planned_motors = (
            ["motor.mesh"]
            if motor_allowed("motor.mesh", effector_reqs, switch_state)
            else []
        )
        behavior = "generic_integrate_and_remember"
        center = "area.dlpfc"
        columns = []
        tracts = []

    known_motors = {e["id"] for e in motor["effectors"]}
    planned_motors = [m for m in planned_motors if m in known_motors]

    # OCL / CPV trajectory policies (Aaron-approved 2026-09-17)
    planned_motors, policy_violations = tp.apply_policies(planned_motors, switch_state)

    edge_pairs = {(e["from"], e["to"]) for e in synapses["edges"]}
    missing = []
    for a, b in zip(pathway, pathway[1:]):
        if (a, b) not in edge_pairs:
            missing.append([a, b])

    result = {
        "accepted": True,
        "sense": sense,
        "goal": goal,
        "area": center,
        "center": center,
        "columns": columns,
        "tracts": tracts,
        "behavior": behavior,
        "hotspot_id": picked.get("id") if picked else None,
        "alt_hotspots": [
            h["id"] for h in candidates if not picked or h["id"] != picked.get("id")
        ],
        "pathway": pathway,
        "switch_state": switch_state,
        "motor_plan": planned_motors,
        "trajectory_violations": policy_violations,
        "response_rule": motor["response_rule"],
        "missing_explicit_edges": missing[:10],
        "persona": {
            "name": "Cam",
            "voice": "soft airy fluent English",
            "sole_operator": "Aaron",
        },
        "dual_process": {
            "fast": "center.slm",
            "slow": ["center.capability", "center.chief", "center.qa"],
            "config": "config/enhancement/dual-process.json",
        },
    }
    # When coding motor is planned, attach workspace resolution for run-cline.py
    if "motor.cline" in planned_motors or (
        picked and picked.get("id") in {"hotspot.coding", "hotspot.cline_result"}
    ):
        try:
            choice = cw.choose_workspace(
                goal=goal,
                workspace_id=workspace_id or None,
                role=role or None,
            )
            result["workspace"] = {
                "id": choice["workspace"].get("id"),
                "path": choice["path"],
                "reason": choice.get("reason"),
                "score": choice.get("score"),
                "alternates": choice.get("alternates"),
                "runner": (
                    f"python3 scripts/run-cline.py --workspace-id {choice['workspace'].get('id')} "
                    f"--goal {json.dumps(goal)} \"...\""
                ),
            }
        except Exception as exc:  # noqa: BLE001
            result["workspace_error"] = str(exc)

    if kill:
        result["accepted"] = False
        result["reason"] = "switch.kill act — all motor silenced"
        result["motor_plan"] = []
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sense", required=True, help="sense.* id")
    parser.add_argument("--not-aaron", action="store_true", help="simulate unauthorized spike")
    parser.add_argument("--kill", action="store_true")
    parser.add_argument("--no-autonomy", action="store_true")
    parser.add_argument("--goal", default="", help="optional Aaron goal text")
    parser.add_argument("--hotspot", default="", help="explicit hotspot id when sense collides")
    parser.add_argument("--workspace-id", default="", help="force coding workspace id")
    parser.add_argument("--role", default="", help="Cam role for workspace allowlist")
    parser.add_argument(
        "--enhance",
        action="store_true",
        help="Aaron enables switch.cam_enhance (apply functionality changes)",
    )
    parser.add_argument("--no-research-scan", action="store_true")
    parser.add_argument("--no-slm", action="store_true")
    parser.add_argument("--no-dl", action="store_true")
    args = parser.parse_args()

    try:
        result = route(
            sense=args.sense,
            goal=args.goal,
            hotspot=args.hotspot or None,
            kill=args.kill,
            enhance=args.enhance,
            not_aaron=args.not_aaron,
            no_autonomy=args.no_autonomy,
            workspace_id=args.workspace_id,
            role=args.role,
            research_scan=not args.no_research_scan,
            slm=not args.no_slm,
            dl=not args.no_dl,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
