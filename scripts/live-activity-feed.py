#!/usr/bin/env python3
"""Derive live agent/task activity from Cam connectome + health scan.

Writes vault/10-Mesh-Distillates/live-activity.json for the DTI cortex viz.
Standing loops and recent health findings become 'firing' columns that light tracts.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "connectome"
OUT = ROOT / "vault" / "10-Mesh-Distillates" / "live-activity.json"
HEALTH = ROOT / "vault" / "10-Mesh-Distillates" / "system-health.json"
TIMELINE = ROOT / "vault" / "10-Mesh-Distillates" / "plasticity-timeline.json"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def main() -> int:
    neurons = load(CFG / "neurons.json", {}).get("neurons", [])
    tracts = load(CFG / "tracts.json", {}).get("tracts", [])
    health = load(HEALTH, {})
    timeline = load(TIMELINE, {})

    # Map area → tracts touching it
    area_tracts: dict[str, list[str]] = {}
    for tr in tracts:
        for end in tr.get("ends") or []:
            if end.startswith("area."):
                area_tracts.setdefault(end, []).append(tr["id"])

    health_by_neuron = {
        c["neuron"]: c.get("status", "idle") for c in health.get("checks") or []
    }

    firing = []
    now = time.time()
    # Phase by wall clock so standing loops appear to tick
    phase = int(now // 8) % max(len(neurons), 1)

    for i, n in enumerate(neurons):
        nid = n["id"]
        rec = n.get("recurrence", "")
        kind = n.get("kind", "agent")
        area = n.get("area")
        status = health_by_neuron.get(nid)

        intensity = 0.0
        reason = None
        if status in ("warning", "critical"):
            intensity = 0.95 if status == "critical" else 0.75
            reason = f"health:{status}"
        elif status == "healthy" and "health" in nid or "scan" in nid or "vitals" in nid:
            intensity = 0.45
            reason = "health:healthy"
        elif rec in ("always_on", "standing", "standing_scan", "continuous", "boot"):
            # Round-robin standing activity so the mesh stays alive
            if (i + phase) % 5 == 0:
                intensity = 0.55 if kind == "loop" else 0.4
                reason = f"standing:{rec}"
        elif rec in ("per_task", "on_map_spike", "per_outbound"):
            if (i + phase) % 11 == 0:
                intensity = 0.35
                reason = "idle_ready"

        if intensity <= 0:
            continue
        firing.append(
            {
                "neuron": nid,
                "kind": kind,
                "area": area,
                "intensity": intensity,
                "reason": reason,
                "tracts": area_tracts.get(area, [])[:6],
            }
        )

    # Recent timeline events → task spikes
    recent_tasks = []
    for ev in (timeline.get("events") or [])[-12:]:
        if ev.get("type") in ("ltp", "health_scan", "synapse", "neurogenesis"):
            recent_tasks.append(
                {
                    "type": ev.get("type"),
                    "tracts": ev.get("tracts") or [],
                    "overall": ev.get("overall"),
                    "t": ev.get("t"),
                }
            )

    report = {
        "at": utc(),
        "epoch": int(now),
        "firing": sorted(firing, key=lambda x: -x["intensity"]),
        "active_areas": sorted({f["area"] for f in firing if f.get("area")}),
        "active_tracts": sorted(
            {tid for f in firing for tid in f.get("tracts") or []}
        ),
        "recent_tasks": recent_tasks,
        "health_overall": health.get("overall", "unknown"),
        "neuron_count": len(neurons),
        "firing_count": len(firing),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"live-activity: {report['firing_count']} firing · health={report['health_overall']}")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
