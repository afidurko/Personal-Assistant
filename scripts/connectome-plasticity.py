#!/usr/bin/env python3
"""Apply neuroplasticity / neurogenesis updates to Cam tract mesh.

Simulates LTP on successful act pathways, LTD on errors, pruning of weak
tracts, and MTL neurogenesis of immature columns. Writes a rewindable
timeline for the 3D cortex viz.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "connectome"
OUT = ROOT / "vault" / "10-Mesh-Distillates"
WEIGHTS = OUT / "tract-weights.json"
TIMELINE = OUT / "plasticity-timeline.json"
COLUMNS = OUT / "neurogenesis-columns.json"


def load(name: str):
    return json.loads((CFG / name).read_text(encoding="utf-8"))


def default_weights(tracts: dict) -> dict:
    return {t["id"]: 0.55 for t in tracts["tracts"]}


def append_event(timeline: list, event: dict) -> None:
    event = dict(event)
    event["t"] = len(timeline)
    event["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    timeline.append(event)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sense", default="sense.chat.aaron")
    p.add_argument("--goal", default="")
    p.add_argument("--error", default="", help="missing_edge|qa_veto|kill|pruned_tract")
    p.add_argument("--neurogenesis", action="store_true")
    p.add_argument("--mature", action="store_true", help="age all immature MTL columns one stage")
    p.add_argument("--reset", action="store_true")
    args = p.parse_args()

    plasticity = load("plasticity.json")
    tracts = load("tracts.json")
    hotspots = load("hotspots.json")

    OUT.mkdir(parents=True, exist_ok=True)
    weights = default_weights(tracts)
    if WEIGHTS.exists() and not args.reset:
        weights.update(json.loads(WEIGHTS.read_text(encoding="utf-8")).get("weights", {}))
    timeline = []
    if TIMELINE.exists() and not args.reset:
        timeline = json.loads(TIMELINE.read_text(encoding="utf-8")).get("events", [])
    columns = []
    if COLUMNS.exists() and not args.reset:
        columns = json.loads(COLUMNS.read_text(encoding="utf-8")).get("columns", [])

    rules = plasticity["rules"]
    ltp = rules["ltp"]
    ltd = rules["ltd"]
    prune = rules["pruning"]
    neuro = rules["neurogenesis"]

    # Pick hotspot for sense
    cands = [h for h in hotspots["hotspots"] if h["pathway"] and h["pathway"][0] == args.sense]
    if not cands:
        cands = [h for h in hotspots["hotspots"] if args.sense in h["pathway"]]
    hot = cands[0] if cands else None
    used_tracts = list((hot or {}).get("tracts") or [])
    pathway = list((hot or {}).get("pathway") or [args.sense])

    if args.neurogenesis:
        age0 = neuro["stages"][0]
        col = {
            "id": f"neuron.mtl_new_{len(columns)+1:03d}",
            "area": neuro["site"],
            "kind": "loop",
            "age": 0,
            "label": age0["label"],
            "plasticity_gain": age0["plasticity_gain"],
            "can_motor": age0["can_motor"],
        }
        columns.append(col)
        append_event(
            timeline,
            {
                "type": "neurogenesis",
                "column": col["id"],
                "area": neuro["site"],
                "stage": age0["label"],
                "status": "ok",
            },
        )

    if args.mature and columns:
        stages = neuro["stages"]
        for col in columns:
            age = min(int(col.get("age", 0)) + 1, len(stages) - 1)
            st = stages[age]
            col["age"] = age
            col["label"] = st["label"]
            col["plasticity_gain"] = st["plasticity_gain"]
            col["can_motor"] = st["can_motor"]
            append_event(
                timeline,
                {
                    "type": "neurogenesis_mature",
                    "column": col["id"],
                    "stage": st["label"],
                    "status": "ok",
                },
            )

    # Record pathway hops
    for a, b in zip(pathway, pathway[1:]):
        append_event(
            timeline,
            {
                "type": "synapse",
                "from": a,
                "to": b,
                "status": "error" if args.error == "missing_edge" and b.startswith("motor.") else "ok",
                "code": args.error if args.error == "missing_edge" and b.startswith("motor.") else None,
            },
        )

    if args.error == "kill":
        append_event(timeline, {"type": "error", "code": "kill", "status": "error"})
        for tid in used_tracts:
            weights[tid] = max(ltd["floor"], weights.get(tid, 0.55) + ltd["delta"])
    elif args.error == "qa_veto":
        append_event(
            timeline,
            {"type": "error", "code": "qa_veto", "status": "hold", "area": "area.cingulate"},
        )
        for tid in used_tracts:
            weights[tid] = max(ltd["floor"], weights.get(tid, 0.55) + ltd["delta"])
    elif args.error == "missing_edge":
        append_event(
            timeline,
            {
                "type": "error",
                "code": "missing_edge",
                "status": "error",
                "tracts": used_tracts,
            },
        )
        for tid in used_tracts:
            weights[tid] = max(ltd["floor"], weights.get(tid, 0.55) + ltd["delta"])
    elif not args.error and hot:
        # LTP success
        gain = 1.0
        immature = [c for c in columns if c.get("area") == "area.mtl" and c.get("age", 0) < 3]
        if immature:
            gain = max(c.get("plasticity_gain", 1.0) for c in immature) or 1.0
        for tid in used_tracts:
            weights[tid] = min(ltp["cap"], weights.get(tid, 0.55) + ltp["delta"] * gain)
        # heterosynaptic LTD on unused tracts (mild)
        for tid in list(weights):
            if tid not in used_tracts:
                weights[tid] = max(ltd["floor"], weights[tid] - 0.02)
        append_event(
            timeline,
            {
                "type": "ltp",
                "tracts": used_tracts,
                "gain": gain,
                "status": "ok",
                "hotspot": hot["id"],
                "pathway": pathway,
            },
        )

    # Prune weak
    pruned = []
    for tid, w in list(weights.items()):
        if w < prune["threshold"]:
            pruned.append(tid)
            append_event(
                timeline,
                {"type": "prune", "tract": tid, "weight": w, "status": "reroute", "code": "pruned_tract"},
            )

    payload_w = {"version": 1, "weights": weights, "pruned": pruned}
    payload_t = {"version": 1, "events": timeline, "rules": "config/connectome/plasticity.json"}
    payload_c = {"version": 1, "columns": columns, "site": neuro["site"]}
    WEIGHTS.write_text(json.dumps(payload_w, indent=2) + "\n", encoding="utf-8")
    TIMELINE.write_text(json.dumps(payload_t, indent=2) + "\n", encoding="utf-8")
    COLUMNS.write_text(json.dumps(payload_c, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "sense": args.sense,
                "error": args.error or None,
                "weights": {k: round(v, 3) for k, v in weights.items()},
                "pruned": pruned,
                "columns": len(columns),
                "timeline_events": len(timeline),
                "out": {
                    "weights": str(WEIGHTS.relative_to(ROOT)),
                    "timeline": str(TIMELINE.relative_to(ROOT)),
                    "columns": str(COLUMNS.relative_to(ROOT)),
                },
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
