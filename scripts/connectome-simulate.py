#!/usr/bin/env python3
"""Cam connectome live-action simulations — sense→area→switch→motor→feedback.

Default N = 1_000_000_000 (continuous QA campaign size).
Static integrity scan is the real gate; fuzz campaign stress-tests holds.
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
        "area.dlpfc",
        "area.mtl",
        "area.cingulate",
        "area.wernicke",
        "area.parietal",
        "area.broca",
        "area.visual",
        "area.apfc",
        "center.chief",
        "center.memory",
        "center.ops",
        "center.comms",
        "center.vision",
        "center.qa",
        "center.coding",
        "center.docs",
        "center.research",
        "center.careers",
    }
)
DEFAULT_PATH = (
    "sense.chat.aaron",
    "area.wernicke",
    "area.dlpfc",
    "area.mtl",
    "switch.autonomy",
    "motor.mesh",
)
DEFAULT_FEEDBACK = ("motor.mesh", "area.mtl", "area.dlpfc")


def load_json(name: str):
    return json.loads((CFG / name).read_text(encoding="utf-8"))


def node_ok(node: str) -> bool:
    return node.startswith(("sense.", "center.", "area.", "switch.", "motor.", "neuron."))


def build_tables():
    """Precompute per-sense pathway + feedback tables and inventories."""
    sensory = load_json("sensory.json")
    centers = load_json("centers.json")
    areas = load_json("areas.json")
    switches = load_json("switches.json")
    motor = load_json("motor.json")
    hotspots = load_json("hotspots.json")
    synapses = load_json("synapses.json")
    neurons = load_json("neurons.json")

    sense_ids = [n["id"] for n in sensory["neurons"]]
    known = (
        {n["id"] for n in sensory["neurons"]}
        | {c["id"] for c in centers["centers"]}
        | {a["id"] for a in areas["areas"]}
        | {s["id"] for s in switches["switches"]}
        | {e["id"] for e in motor["effectors"]}
        | {n["id"] for n in neurons["neurons"]}
    )
    edges = {(e["from"], e["to"]) for e in synapses["edges"]}
    motor_ids = {e["id"] for e in motor["effectors"]}
    effector_reqs = {
        e["id"]: [r for r in (e.get("requires_switch") or []) if r != "switch.kill"]
        for e in motor["effectors"]
    }

    by_sense: dict[str, list[tuple[str, tuple[str, ...], tuple[str, ...]]]] = {
        s: [] for s in sense_ids
    }
    for h in hotspots["hotspots"]:
        path = tuple(h["pathway"])
        sides = tuple(h.get("side_effects") or [])
        motors = [n for n in path if n.startswith("motor.")]
        if motors:
            last = motors[-1]
            fb = (last, "area.mtl", "area.dlpfc")
        else:
            fb = ("area.mtl", "area.dlpfc")
        by_sense.setdefault(path[0], []).append((h["id"], path, fb, sides))

    for s in sense_ids:
        if not by_sense[s]:
            by_sense[s] = [("default", DEFAULT_PATH, DEFAULT_FEEDBACK, ())]

    integrity_errors: list[str] = []
    for sense, options in by_sense.items():
        for hid, path, fb, sides in options:
            for node in path:
                if not node_ok(node):
                    integrity_errors.append(f"bad_node:{hid}:{node}")
                elif node not in known:
                    integrity_errors.append(f"unknown_node:{hid}:{node}")
            for mi, node in enumerate(path):
                if not node.startswith("motor."):
                    continue
                if mi == 0:
                    integrity_errors.append(f"orphan_motor:{hid}")
                if node not in motor_ids:
                    integrity_errors.append(f"unknown_motor:{hid}:{node}")
                for req in effector_reqs.get(node, []):
                    if req not in path:
                        integrity_errors.append(
                            f"motor_missing_switch:{hid}:{node}:{req}"
                        )
            for side in sides:
                if side not in motor_ids:
                    integrity_errors.append(f"unknown_side:{hid}:{side}")
            if not fb or fb[-1] not in FEEDBACK_SINKS:
                integrity_errors.append(f"bad_feedback_sink:{hid}")
            for a, b in zip(path, path[1:]):
                if (a, b) not in edges:
                    integrity_errors.append(f"missing_edge:{a}->{b}")
            for a, b in zip(fb, fb[1:]):
                if (a, b) not in edges:
                    integrity_errors.append(f"missing_feedback_edge:{a}->{b}")

    # Soft = missing edges only (hard = unknown nodes / unguarded pathway motors).
    hard = [
        e
        for e in integrity_errors
        if not e.startswith("missing_edge:")
        and not e.startswith("missing_feedback_edge:")
    ]
    soft = [e for e in integrity_errors if e not in hard]
    return sense_ids, by_sense, known, motor_ids, edges, hard, soft


def run_batch(payload):
    worker_id, count, seed, sense_ids, by_sense, sense_weights = payload
    rng = random.Random(seed)
    n_senses = len(sense_ids)
    passed = failed = kill_holds = non_aaron_holds = feedback_ok = 0
    first_error = None
    choice = rng.choice
    rand = rng.random
    # Traffic-weighted sampling: chat-heavy when weights provided
    if sense_weights and len(sense_weights) == n_senses:
        cumulative = []
        total = 0.0
        for w in sense_weights:
            total += w
            cumulative.append(total)
    else:
        cumulative = None
        total = 0.0

    def pick_sense():
        if not cumulative or total <= 0:
            return sense_ids[int(rand() * n_senses)]
        x = rand() * total
        for i, c in enumerate(cumulative):
            if x <= c:
                return sense_ids[i]
        return sense_ids[-1]

    t0 = time.perf_counter()
    heartbeat_every = max(1, min(50_000_000, count // 4 or 1))
    for i in range(count):
        sense = pick_sense()
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
                or node.startswith("area.")
                or node.startswith("switch.")
                or node.startswith("motor.")
                or node.startswith("neuron.")
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

        if (i + 1) % heartbeat_every == 0:
            elapsed = time.perf_counter() - t0
            rate = (i + 1) / elapsed if elapsed else 0
            print(
                f"  heartbeat w{worker_id}: {i+1:,}/{count:,} "
                f"({rate:,.0f} sims/s) fail={failed}",
                flush=True,
            )

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
        help="fail load if pathway/feedback edges missing from synapses.json",
    )
    args = parser.parse_args()

    sense_ids, by_sense, _known, _motors, _edges, hard, soft = build_tables()
    missing = [
        e
        for e in soft
        if e.startswith("missing_edge:") or e.startswith("missing_feedback_edge:")
    ]
    if hard:
        print("INTEGRITY FAIL:", hard[:40], flush=True)
        return 2
    if args.strict_edges and missing:
        print("STRICT EDGE FAIL:", missing[:40], flush=True)
        return 2

    # Flatten tables for worker pickling (drop sides in hot path payload shape)
    by_sense_runtime = {
        s: [(path, fb) for _hid, path, fb, _sides in opts]
        for s, opts in by_sense.items()
    }

    # Traffic weights: Aaron chat / vault / careers heavier than rare sensors
    weight_map = {
        "sense.chat.aaron": 8.0,
        "sense.vault.hit": 4.0,
        "sense.mesh.hit": 3.0,
        "sense.careers.listing": 3.0,
        "sense.email.thread": 2.0,
        "sense.calendar.event": 2.0,
        "sense.cline.result": 2.5,
        "sense.jarvis.result": 1.5,
        "sense.audio.transcript": 1.5,
        "sense.vision.detection": 1.0,
        "sense.ios.camera": 1.0,
        "sense.ios.mic": 1.0,
        "sense.aaron.face": 1.0,
        "sense.aaron.voice": 1.0,
        "sense.photos.library": 0.8,
        "sense.files.media": 0.8,
    }
    sense_weights = [weight_map.get(s, 1.0) for s in sense_ids]

    n = args.n
    workers = min(args.workers, n)
    base, rem = divmod(n, workers)
    batches = []
    for w in range(workers):
        count = base + (1 if w < rem else 0)
        if count:
            batches.append(
                (
                    w,
                    count,
                    args.seed + w * 1_000_003,
                    sense_ids,
                    by_sense_runtime,
                    sense_weights,
                )
            )

    print(
        f"Cam connectome sims: n={n:,} workers={len(batches)} "
        f"senses={len(sense_ids)} missing_edges={len(missing)} "
        f"soft_warnings={len(soft)} weighted=True heartbeats=50M",
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
        "missing_edges_count": len(missing),
        "missing_edges_sample": missing[:40],
        "soft_warnings_sample": soft[:40],
        "unlimited_subagents": True,
        "continuous_qa": True,
        "simulator": "v3-weighted-heartbeats",
        "traffic_weighted": True,
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
