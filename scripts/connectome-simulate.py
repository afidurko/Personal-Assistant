#!/usr/bin/env python3
"""High-throughput Cam connectome live-action simulations.

Runs N sense→center→switch→motor→feedback simulations in parallel workers.
Default N matches Aaron's request (Indian notation 1,00,000,000 = 100_000_000).
Override with --n for other scales (e.g. --n 1000000000).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "connectome"
OUT_DIR = ROOT / "vault" / "10-Mesh-Distillates"


def load_maps():
    sensory = json.loads((CFG / "sensory.json").read_text(encoding="utf-8"))
    centers = json.loads((CFG / "centers.json").read_text(encoding="utf-8"))
    switches = json.loads((CFG / "switches.json").read_text(encoding="utf-8"))
    motor = json.loads((CFG / "motor.json").read_text(encoding="utf-8"))
    hotspots = json.loads((CFG / "hotspots.json").read_text(encoding="utf-8"))
    synapses = json.loads((CFG / "synapses.json").read_text(encoding="utf-8"))
    return sensory, centers, switches, motor, hotspots, synapses


def build_index(sensory, centers, switches, motor, hotspots, synapses):
    sense_ids = [n["id"] for n in sensory["neurons"]]
    center_ids = {c["id"] for c in centers["centers"]}
    switch_ids = {s["id"] for s in switches["switches"]}
    motor_ids = {e["id"] for e in motor["effectors"]}
    edges = {(e["from"], e["to"]) for e in synapses["edges"]}
    # Prefer primary pathways (pathway[0] == sense)
    primary = {}
    for h in hotspots["hotspots"]:
        primary[h["pathway"][0]] = h
    return sense_ids, center_ids, switch_ids, motor_ids, edges, primary, hotspots["hotspots"]


@dataclass
class BatchResult:
    worker_id: int
    attempted: int
    passed: int
    failed: int
    kill_holds: int
    non_aaron_holds: int
    feedback_ok: int
    first_error: str | None
    elapsed_s: float


def simulate_one(rng: random.Random, sense_ids, primary, motor_ids, kill_prob=0.002, non_aaron_prob=0.001):
    """One live-action simulation with optional antagonistic switch outcomes."""
    sense = rng.choice(sense_ids)
    kill = rng.random() < kill_prob
    non_aaron = sense == "sense.chat.aaron" and rng.random() < non_aaron_prob

    if non_aaron:
        return "non_aaron_hold", True, False

    hot = primary.get(sense)
    if not hot:
        pathway = [sense, "center.chief", "center.router", "center.memory", "motor.mesh"]
        feedback = ["motor.mesh", "center.memory", "center.chief"]
    else:
        pathway = hot["pathway"]
        motors = [p for p in pathway if p.startswith("motor.")]
        feedback = (
            [motors[-1], sense, "center.memory", "center.chief"]
            if motors
            else ["center.memory", "center.chief"]
        )

    if kill:
        return "kill_hold", True, False

    for node in pathway:
        if not (
            node.startswith("sense.")
            or node.startswith("center.")
            or node.startswith("switch.")
            or node.startswith("motor.")
        ):
            return f"bad_node:{node}", False, False

    for mi, node in enumerate(pathway):
        if not node.startswith("motor."):
            continue
        if mi == 0:
            return "orphan_motor", False, False
        if node not in motor_ids:
            return f"unknown_motor:{node}", False, False

    if not feedback or feedback[-1] not in {
        "center.chief",
        "center.memory",
        "center.ops",
        "center.comms",
        "center.vision",
    }:
        return "bad_feedback_sink", False, False

    return "ok", True, True


def run_batch(args):
    worker_id, count, seed = args
    sensory, centers, switches, motor, hotspots, synapses = load_maps()
    sense_ids, _c, _s, motor_ids, _e, primary, _h = build_index(
        sensory, centers, switches, motor, hotspots, synapses
    )
    rng = random.Random(seed)
    passed = failed = kill_holds = non_aaron_holds = feedback_ok = 0
    first_error = None
    t0 = time.perf_counter()
    for _ in range(count):
        code, ok, fb = simulate_one(rng, sense_ids, primary, motor_ids)
        if code == "kill_hold":
            kill_holds += 1
            passed += 1
        elif code == "non_aaron_hold":
            non_aaron_holds += 1
            passed += 1
        elif ok:
            passed += 1
            if fb:
                feedback_ok += 1
        else:
            failed += 1
            if first_error is None:
                first_error = code
    return BatchResult(
        worker_id=worker_id,
        attempted=count,
        passed=passed,
        failed=failed,
        kill_holds=kill_holds,
        non_aaron_holds=non_aaron_holds,
        feedback_ok=feedback_ok,
        first_error=first_error,
        elapsed_s=time.perf_counter() - t0,
    ).__dict__


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n",
        type=int,
        default=100_000_000,
        help="total simulations (default 100,000,000 = 1,00,000,000)",
    )
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        default=str(OUT_DIR / "connectome-sim-results.json"),
    )
    args = parser.parse_args()

    n = args.n
    workers = min(args.workers, n)
    base = n // workers
    rem = n % workers
    batches = []
    offset = 0
    for w in range(workers):
        count = base + (1 if w < rem else 0)
        if count <= 0:
            continue
        batches.append((w, count, args.seed + w * 1_000_003))
        offset += count

    print(f"Cam connectome sims: n={n:,} workers={len(batches)}", flush=True)
    t0 = time.perf_counter()
    results = []
    with ProcessPoolExecutor(max_workers=len(batches)) as ex:
        futs = [ex.submit(run_batch, b) for b in batches]
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            done += r["attempted"]
            print(
                f"  worker {r['worker_id']}: {r['attempted']:,} in {r['elapsed_s']:.2f}s "
                f"(pass={r['passed']:,} fail={r['failed']:,}) total_done≈{done:,}",
                flush=True,
            )

    elapsed = time.perf_counter() - t0
    summary = {
        "n": n,
        "workers": len(batches),
        "elapsed_s": elapsed,
        "sims_per_sec": n / elapsed if elapsed else None,
        "passed": sum(r["passed"] for r in results),
        "failed": sum(r["failed"] for r in results),
        "kill_holds": sum(r["kill_holds"] for r in results),
        "non_aaron_holds": sum(r["non_aaron_holds"] for r in results),
        "feedback_ok": sum(r["feedback_ok"] for r in results),
        "first_errors": [r["first_error"] for r in results if r["first_error"]],
        "unlimited_subagents": True,
        "notation_note": "default n=100_000_000 interprets 1,00,000,000 (Indian grouping)",
        "workers_detail": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "workers_detail"}, indent=2))
    print(f"wrote {out}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
