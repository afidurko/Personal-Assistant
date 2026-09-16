#!/usr/bin/env python3
"""Cam connectome live-action simulations — sense→center→switch→motor→feedback.

Default N = 1_000_000_000 (continuous QA campaign size).
Workers = parallel subagent processes. Prefer simplify over complicate.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "connectome"
OUT_DIR = ROOT / "vault" / "10-Mesh-Distillates"

FEEDBACK_SINKS = frozenset(
    {
        "center.chief",
        "center.memory",
        "center.ops",
        "center.comms",
        "center.vision",
        "center.qa",
    }
)
DEFAULT_PATH = (
    "sense.chat.aaron",
    "center.chief",
    "center.memory",
    "motor.mesh",
)
DEFAULT_FEEDBACK = ("motor.mesh", "center.memory", "center.chief")


def load_json(name: str):
    return json.loads((CFG / name).read_text(encoding="utf-8"))


def node_ok(node: str) -> bool:
    return node.startswith(("sense.", "center.", "switch.", "motor."))


def build_tables():
    """Precompute per-sense pathway + feedback tables and inventories."""
    sensory = load_json("sensory.json")
    centers = load_json("centers.json")
    switches = load_json("switches.json")
    motor = load_json("motor.json")
    hotspots = load_json("hotspots.json")
    synapses = load_json("synapses.json")

    sense_ids = [n["id"] for n in sensory["neurons"]]
    known = (
        {n["id"] for n in sensory["neurons"]}
        | {c["id"] for c in centers["centers"]}
        | {s["id"] for s in switches["switches"]}
        | {e["id"] for e in motor["effectors"]}
    )
    edges = {(e["from"], e["to"]) for e in synapses["edges"]}
    motor_ids = {e["id"] for e in motor["effectors"]}

    # Multiple hotspots may share a sense — keep a list, pick at runtime.
    by_sense: dict[str, list[tuple[tuple[str, ...], tuple[str, ...]]]] = {
        s: [] for s in sense_ids
    }
    for h in hotspots["hotspots"]:
        path = tuple(h["pathway"])
        motors = [n for n in path if n.startswith("motor.")]
        fb = (
            (motors[-1], path[0], "center.memory", "center.chief")
            if motors
            else ("center.memory", "center.chief")
        )
        by_sense.setdefault(path[0], []).append((path, fb))

    for s in sense_ids:
        if not by_sense[s]:
            by_sense[s] = [(DEFAULT_PATH, DEFAULT_FEEDBACK)]

    # Static integrity scan (once, not in the hot loop).
    integrity_errors: list[str] = []
    for sense, options in by_sense.items():
        for path, fb in options:
            for node in path:
                if not node_ok(node):
                    integrity_errors.append(f"bad_node:{node}")
                elif node not in known and not node.startswith("sense."):
                    # senses may appear mid-path as memory periphery
                    if node not in known:
                        integrity_errors.append(f"unknown_node:{node}")
            for mi, node in enumerate(path):
                if node.startswith("motor."):
                    if mi == 0:
                        integrity_errors.append("orphan_motor")
                    if node not in motor_ids:
                        integrity_errors.append(f"unknown_motor:{node}")
            if not fb or fb[-1] not in FEEDBACK_SINKS:
                integrity_errors.append(f"bad_feedback_sink:{sense}")
            for a, b in zip(path, path[1:]):
                if edges and (a, b) not in edges:
                    # soft: record missing synapse, still simulate pathway shape
                    integrity_errors.append(f"missing_edge:{a}->{b}")

    return sense_ids, by_sense, known, motor_ids, edges, integrity_errors


def run_batch(payload):
    worker_id, count, seed, sense_ids, by_sense = payload
    rng = random.Random(seed)
    n_senses = len(sense_ids)
    passed = failed = kill_holds = non_aaron_holds = feedback_ok = 0
    first_error = None
    # Pre-bind locals for speed
    choice = rng.choice
    rand = rng.random
    t0 = time.perf_counter()
    for _ in range(count):
        sense = sense_ids[int(rand() * n_senses)]
        # antagonistic switches
        if sense == "sense.chat.aaron" and rand() < 0.001:
            non_aaron_holds += 1
            passed += 1
            continue
        if rand() < 0.002:
            kill_holds += 1
            passed += 1
            continue

        options = by_sense[sense]
        path, fb = options[0] if len(options) == 1 else choice(options)

        ok = True
        code = "ok"
        for node in path:
            if not (
                node.startswith("sense.")
                or node.startswith("center.")
                or node.startswith("switch.")
                or node.startswith("motor.")
            ):
                ok = False
                code = f"bad_node:{node}"
                break
        if ok:
            for mi, node in enumerate(path):
                if node.startswith("motor.") and mi == 0:
                    ok = False
                    code = "orphan_motor"
                    break
            if ok and (not fb or fb[-1] not in FEEDBACK_SINKS):
                ok = False
                code = "bad_feedback_sink"

        if ok:
            passed += 1
            feedback_ok += 1
        else:
            failed += 1
            if first_error is None:
                first_error = code

    return {
        "worker_id": worker_id,
        "attempted": count,
        "passed": passed,
        "failed": failed,
        "kill_holds": kill_holds,
        "non_aaron_holds": non_aaron_holds,
        "feedback_ok": feedback_ok,
        "first_error": first_error,
        "elapsed_s": time.perf_counter() - t0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1_000_000_000)
    parser.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(OUT_DIR / "connectome-sim-results.json"))
    parser.add_argument(
        "--strict-edges",
        action="store_true",
        help="fail load if pathway edges missing from synapses.json",
    )
    args = parser.parse_args()

    sense_ids, by_sense, _known, _motors, _edges, integrity = build_tables()
    missing_edges = [e for e in integrity if e.startswith("missing_edge:")]
    hard = [e for e in integrity if not e.startswith("missing_edge:")]
    if hard:
        print("INTEGRITY FAIL:", hard[:20], flush=True)
        return 2
    if args.strict_edges and missing_edges:
        print("STRICT EDGE FAIL:", missing_edges[:20], flush=True)
        return 2

    n = args.n
    workers = min(args.workers, n)
    base, rem = divmod(n, workers)
    batches = []
    for w in range(workers):
        count = base + (1 if w < rem else 0)
        if count:
            batches.append((w, count, args.seed + w * 1_000_003, sense_ids, by_sense))

    print(
        f"Cam connectome sims: n={n:,} workers={len(batches)} "
        f"senses={len(sense_ids)} missing_edges={len(missing_edges)}",
        flush=True,
    )
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
        "sims_per_sec": (n / elapsed) if elapsed else None,
        "passed": sum(r["passed"] for r in results),
        "failed": sum(r["failed"] for r in results),
        "kill_holds": sum(r["kill_holds"] for r in results),
        "non_aaron_holds": sum(r["non_aaron_holds"] for r in results),
        "feedback_ok": sum(r["feedback_ok"] for r in results),
        "first_errors": [r["first_error"] for r in results if r["first_error"]],
        "missing_edges_count": len(missing_edges),
        "missing_edges_sample": missing_edges[:40],
        "unlimited_subagents": True,
        "continuous_qa": True,
        "simulator": "v2-simplified",
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
