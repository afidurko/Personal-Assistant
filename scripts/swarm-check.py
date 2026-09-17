#!/usr/bin/env python3
"""Validate Cam HAAS-pattern configs: privileges, lineage, boss/worker primitives.

Does not talk to OpenAI or nulltickets. Exit 0 only when contracts pass.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWARM = ROOT / "config" / "swarm"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class SwarmError(Exception):
    pass


def subset(child: set[str], parent: set[str]) -> bool:
    return child <= parent


def spawn_child(parent: dict, role: str, requested: list[str] | None, catalog: dict) -> dict:
    aaron_only = set(catalog["privilege_catalog"]["aaron_only"])
    grantable = set(catalog["privilege_catalog"]["agent_grantable"])
    parent_privs = set(parent["privileges"])
    defaults = catalog["role_defaults"].get(role) or catalog["role_defaults"]["default_subagent"]
    base = set(requested if requested is not None else defaults["privileges"])

    illegal = base & aaron_only
    if illegal:
        raise SwarmError(f"cannot grant aaron_only privileges: {sorted(illegal)}")

    unknown = base - grantable - aaron_only
    if unknown:
        raise SwarmError(f"unknown privileges: {sorted(unknown)}")

    if not subset(base, parent_privs):
        raise SwarmError(
            f"privilege escalation blocked: child wants {sorted(base - parent_privs)}"
        )

    if not catalog["inheritance_rules"]["spawn_one_level_below_only"]:
        raise SwarmError("misconfigured: spawn_one_level_below_only must be true")

    child_level = parent["level"] + 1
    return {
        "id": f"{parent['id']}/{role}@{child_level}",
        "role": role,
        "level": child_level,
        "parent_id": parent["id"],
        "privileges": sorted(base),
        "lineage": list(parent.get("lineage", [])) + [parent["id"]],
    }


def may_terminate(caller: dict, target: dict, is_aaron: bool = False) -> bool:
    if is_aaron:
        return True
    if "terminate_lineage" not in caller["privileges"]:
        return False
    if target.get("parent_id") == caller["id"]:
        return True
    return caller["id"] in target.get("lineage", [])


def simulate_primitives(prims: dict, privileges: dict) -> list[dict]:
    events: list[dict] = []
    chief = {
        "id": "agent.chief",
        "role": "chief",
        "level": 1,
        "privileges": list(privileges["role_defaults"]["chief"]["privileges"]),
        "lineage": [],
    }
    broker = spawn_child(chief, "capability-broker", None, privileges)
    events.append({"op": "synapse.spawn", "parent": chief["id"], "child": broker["id"]})

    worker = spawn_child(broker, "task-executor", None, privileges)
    events.append(
        {
            "op": "synapse.assign_task",
            "from": broker["id"],
            "to": worker["id"],
            "task": "complete unit under standing autonomy",
        }
    )
    events.append(
        {
            "op": "synapse.broadcast",
            "from": broker["id"],
            "channel": "team.capability",
            "message": "unit assigned",
        }
    )
    events.append(
        {
            "op": "synapse.send_message",
            "from": worker["id"],
            "to": broker["id"],
            "message": "progress: started",
        }
    )
    events.append(
        {
            "op": "synapse.resolve_task",
            "from": worker["id"],
            "status": "done",
            "distillate": "unit complete",
        }
    )

    try:
        spawn_child(worker, "rogue", ["kill_master", "task_giver"], privileges)
        raise SwarmError("expected aaron_only grant to fail")
    except SwarmError as e:
        events.append({"op": "denied", "reason": str(e)})

    try:
        spawn_child(
            worker,
            "rogue2",
            list(worker["privileges"]) + ["outbound_send"],
            privileges,
        )
        raise SwarmError("expected privilege escalation to fail")
    except SwarmError as e:
        events.append({"op": "denied", "reason": str(e)})

    if not may_terminate(broker, worker):
        raise SwarmError("broker should terminate its worker")
    if may_terminate(worker, broker):
        raise SwarmError("worker must not terminate ancestor")
    events.append(
        {
            "op": "synapse.terminate_lineage",
            "from": broker["id"],
            "target": worker["id"],
            "ok": True,
        }
    )
    events.append(
        {
            "op": "synapse.terminate_lineage",
            "from": "Aaron",
            "target": "all",
            "ok": may_terminate(chief, broker, is_aaron=True),
        }
    )

    ids = {p["id"] for p in prims["primitives"]}
    required = {
        "synapse.assign_task",
        "synapse.broadcast",
        "synapse.resolve_task",
        "synapse.send_message",
        "synapse.spawn",
        "synapse.terminate_lineage",
    }
    missing = required - ids
    if missing:
        raise SwarmError(f"missing primitives: {sorted(missing)}")

    return events


def check_files() -> list[str]:
    required = [
        SWARM / "privileges.json",
        SWARM / "primitives.json",
        SWARM / "autonomy-triad.json",
        ROOT / "config" / "teams" / "tooling.json",
        ROOT / "config" / "roles" / "tool-creator.md",
        ROOT / "config" / "roles" / "tool-user.md",
        ROOT / "config" / "tools" / "registry.json",
        ROOT / "docs" / "HAAS_CAM_PATTERNS.md",
    ]
    return [str(p.relative_to(ROOT)) for p in required if not p.exists()]


def check_connectome_wiring(privileges: dict) -> list[str]:
    errors: list[str] = []
    centers = load(ROOT / "config" / "connectome" / "centers.json")
    center_ids = {c["id"] for c in centers["centers"]}
    if "center.tooling" not in center_ids:
        errors.append("center.tooling missing from centers.json")
    if "team.tooling" not in centers.get("teams", []):
        errors.append("team.tooling missing from centers.teams")

    recursion = centers.get("recursion", {})
    if recursion.get("privilege_inheritance") is not True:
        errors.append("centers.recursion.privilege_inheritance must be true")
    if recursion.get("lineage_terminate") is not True:
        errors.append("centers.recursion.lineage_terminate must be true")
    if recursion.get("unlimited") is not True:
        errors.append("unlimited spawn must remain true")

    motor = load(ROOT / "config" / "connectome" / "motor.json")
    motor_ids = {e["id"] for e in motor["effectors"]}
    if "motor.tool" not in motor_ids:
        errors.append("motor.tool missing")

    sensory = load(ROOT / "config" / "connectome" / "sensory.json")
    sense_ids = {n["id"] for n in sensory["neurons"]}
    if "sense.swarm.message" not in sense_ids:
        errors.append("sense.swarm.message missing")

    hotspots = load(ROOT / "config" / "connectome" / "hotspots.json")
    hotspot_ids = {h["id"] for h in hotspots["hotspots"]}
    if "hotspot.tooling" not in hotspot_ids:
        errors.append("hotspot.tooling missing")

    aaron_only = set(privileges["privilege_catalog"]["aaron_only"])
    for role, spec in privileges["role_defaults"].items():
        overlap = aaron_only & set(spec["privileges"])
        if overlap:
            errors.append(f"role {role} has aaron_only privileges: {sorted(overlap)}")

    triad = load(SWARM / "autonomy-triad.json")
    blob = " ".join(triad.get("explicit_non_goals", [])).lower()
    if "oversight" not in blob and "unsupervised" not in blob:
        errors.append("autonomy-triad must document HAAS non-goals")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print machine-readable report")
    args = parser.parse_args()

    report: dict = {"ok": False, "errors": [], "events": [], "missing_files": []}

    missing = check_files()
    report["missing_files"] = missing
    if missing:
        report["errors"].extend([f"missing file: {m}" for m in missing])
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            for e in report["errors"]:
                print(f"FAIL: {e}", file=sys.stderr)
        return 1

    privileges = load(SWARM / "privileges.json")
    prims = load(SWARM / "primitives.json")

    try:
        report["events"] = simulate_primitives(prims, privileges)
    except SwarmError as e:
        report["errors"].append(str(e))

    report["errors"].extend(check_connectome_wiring(privileges))

    chief = {
        "id": "agent.chief",
        "role": "chief",
        "level": 1,
        "privileges": list(privileges["role_defaults"]["chief"]["privileges"]),
        "lineage": [],
    }
    node = chief
    try:
        for _ in range(5):
            node = spawn_child(node, "default_subagent", None, privileges)
        report["deep_spawn_levels"] = node["level"]
        if node["level"] != 6:
            report["errors"].append(f"expected deep spawn level 6, got {node['level']}")
    except SwarmError as e:
        report["errors"].append(f"deep spawn failed (should be unlimited): {e}")

    report["ok"] = len(report["errors"]) == 0

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if report["ok"]:
            print("OK: privilege inheritance, lineage terminate, and primitives validated")
            print(f"  simulated events: {len(report['events'])}")
            print(f"  deep spawn reached level: {report.get('deep_spawn_levels')}")
        else:
            for e in report["errors"]:
                print(f"FAIL: {e}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
