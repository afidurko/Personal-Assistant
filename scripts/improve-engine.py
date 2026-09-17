#!/usr/bin/env python3
"""improve_engine — turn system-health findings into Cam tasks.

Reads vault/10-Mesh-Distillates/system-health.json and writes:
  - vault/10-Mesh-Distillates/improve-tasks.json  (machine)
  - vault/03-Projects/Improve-Engine-Tasks.md    (human)
Also appends a live-activity event for neuron.improve_engine.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEALTH = ROOT / "vault" / "10-Mesh-Distillates" / "system-health.json"
OUT_JSON = ROOT / "vault" / "10-Mesh-Distillates" / "improve-tasks.json"
OUT_MD = ROOT / "vault" / "03-Projects" / "Improve-Engine-Tasks.md"
EVENTS = ROOT / "vault" / "10-Mesh-Distillates" / "activity-events.jsonl"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emit_activity(neuron: str, intensity: float, tracts: list[str], reason: str) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": utc(),
        "neuron": neuron,
        "kind": "loop",
        "area": "area.apfc",
        "intensity": intensity,
        "tracts": tracts,
        "reason": reason,
        "source": "improve_engine",
    }
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def task_from_check(c: dict) -> dict | None:
    st = c.get("status", "idle")
    if st not in ("warning", "critical"):
        return None
    neuron = c.get("neuron", "unknown")
    title = {
        "neuron.submodule_health": "Init/sync git submodules",
        "neuron.tailscale_reach": "Restore Tailscale reach to Aaron devices",
        "neuron.secret_hygiene": "Quarantine credential-like tracked files",
        "neuron.vuln_scan": "Review static hygiene findings",
        "neuron.drift_scan": "Reconcile docs/config drift vs cortex",
        "neuron.arch_scan": "Remove abs-path coupling in scripts",
        "neuron.converse_health": "Start converse server or mark idle OK",
        "neuron.persist_sync": "Run persist-export / restore manifests",
        "neuron.connectome_check": "Fix connectome graph integrity",
        "neuron.vitals_loop": "Investigate host load before ASR/converse starve",
        "neuron.integration_pulse": "Restore missing integration paths",
        "neuron.priority_boot": "Fix priority-boot.json",
    }.get(neuron, f"Remediate {neuron}")
    return {
        "id": f"improve.{neuron.replace('neuron.', '')}.{st}",
        "title": title,
        "severity": "high" if st == "critical" else "medium",
        "status": st,
        "neuron": neuron,
        "area": "area.apfc",
        "detail": {k: v for k, v in c.items() if k not in ("neuron",)},
        "suggested_cmd": _cmd_for(neuron),
        "created_at": utc(),
        "source": "neuron.improve_engine",
    }


def _cmd_for(neuron: str) -> str:
    return {
        "neuron.submodule_health": "git submodule update --init --depth 1",
        "neuron.tailscale_reach": "tailscale status --json  # ensure aaron-iphone/aaron-ipad online",
        "neuron.persist_sync": "python3 scripts/persist-export.py --seed-only",
        "neuron.connectome_check": "python3 scripts/connectome-check.py --json",
        "neuron.converse_health": "bash scripts/serve-cam-converse.sh",
        "neuron.priority_boot": "edit config/priority-boot.json",
    }.get(neuron, "python3 scripts/system-health-scan.py")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not HEALTH.exists():
        print("missing system-health.json — run system-health-scan.py first", file=sys.stderr)
        return 1
    health = json.loads(HEALTH.read_text(encoding="utf-8"))
    tasks = []
    for c in health.get("checks") or []:
        t = task_from_check(c)
        if t:
            tasks.append(t)

    report = {
        "at": utc(),
        "health_overall": health.get("overall"),
        "task_count": len(tasks),
        "tasks": tasks,
        "neuron": "neuron.improve_engine",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Improve Engine Tasks",
        "",
        f"Generated `{report['at']}` from health overall **{report['health_overall']}**.",
        "",
        "| Severity | Task | Neuron | Cmd |",
        "|---|---|---|---|",
    ]
    if not tasks:
        lines.append("| — | none — mesh green | — | — |")
    for t in tasks:
        lines.append(
            f"| {t['severity']} | {t['title']} | `{t['neuron']}` | `{t['suggested_cmd']}` |"
        )
    lines += ["", "Machine copy: `vault/10-Mesh-Distillates/improve-tasks.json`", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")

    emit_activity(
        "neuron.improve_engine",
        0.9 if tasks else 0.3,
        ["tract.ifof", "tract.slf", "tract.cingulum"],
        f"tasks:{len(tasks)}",
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"improve-engine: {len(tasks)} tasks (health={report['health_overall']})")
        for t in tasks:
            print(f"  [{t['severity']}] {t['title']}")
        print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
