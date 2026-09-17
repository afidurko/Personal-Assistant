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
EVENTS = ROOT / "vault" / "10-Mesh-Distillates" / "activity-events.jsonl"
IMPROVE = ROOT / "vault" / "10-Mesh-Distillates" / "improve-tasks.json"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def recent_event_rows(max_age_s: float = 120.0) -> list[dict]:
    if not EVENTS.exists():
        return []
    now = time.time()
    rows = []
    for ln in EVENTS.read_text(encoding="utf-8").splitlines()[-200:]:
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        # keep recent-ish; if no parseable ts, keep last 40 anyway
        rows.append(row)
    return rows[-40:]


def main() -> int:
    neurons = load(CFG / "neurons.json", {}).get("neurons", [])
    tracts = load(CFG / "tracts.json", {}).get("tracts", [])
    health = load(HEALTH, {})
    timeline = load(TIMELINE, {})
    improve = load(IMPROVE, {})

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
        elif status == "healthy" and ("health" in nid or "scan" in nid or "vitals" in nid or "tailscale" in nid):
            intensity = 0.45
            reason = "health:healthy"
        elif rec in ("always_on", "standing", "standing_scan", "continuous", "boot"):
            if (i + phase) % 5 == 0:
                intensity = 0.55 if kind == "loop" else 0.4
                reason = f"standing:{rec}"
        elif rec in ("per_task", "on_map_spike", "per_outbound", "after_health_scan"):
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

    # Real process events from scripts (improve/lease/fornix/dual-stream/qa)
    by_neuron = {f["neuron"]: f for f in firing}
    for row in recent_event_rows():
        nid = row.get("neuron")
        if not nid:
            continue
        intensity = float(row.get("intensity") or 0.7)
        entry = {
            "neuron": nid,
            "kind": row.get("kind") or "agent",
            "area": row.get("area"),
            "intensity": intensity,
            "reason": row.get("reason") or row.get("source") or "event",
            "tracts": row.get("tracts") or area_tracts.get(row.get("area") or "", [])[:6],
            "source": row.get("source"),
        }
        prev = by_neuron.get(nid)
        if not prev or intensity >= prev.get("intensity", 0):
            by_neuron[nid] = entry
    firing = list(by_neuron.values())

    # Improve-engine open tasks keep aPFC lit
    if improve.get("task_count"):
        by_neuron.setdefault(
            "neuron.improve_engine",
            {
                "neuron": "neuron.improve_engine",
                "kind": "loop",
                "area": "area.apfc",
                "intensity": 0.8,
                "reason": f"open_tasks:{improve['task_count']}",
                "tracts": ["tract.ifof", "tract.slf"],
            },
        )
        firing = list(by_neuron.values())

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
        "improve_tasks": improve.get("task_count", 0),
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
