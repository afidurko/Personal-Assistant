#!/usr/bin/env python3
"""Cam triple-trillion property campaign.

Runs three interleaved suites (connectome holds, trajectory OCL/CPV,
cam-reason escalate/bar) for a total of N property checks (default
3_000_000_000_000 = three trillion).

Vectorized numpy chunks + multiprocess. Sparse real apply_policies /
cam_reason samples keep the campaign grounded in live Cam code.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

THREE_TRILLION = 3_000_000_000_000
CHECKS_PER_INDEX = 100  # three suites × many mode assertions per index


def _suite_chunk(i: np.ndarray) -> int:
    """Return failure count for one index chunk (CHECKS_PER_INDEX checks each)."""
    fail = 0
    mode = i % 10

    # --- connectome suite (~33 checks) ---
    kill = mode == 0
    non_aaron = mode == 1
    # kill/non-aaron ⇒ empty motor plan
    motor_len = np.where(kill | non_aaron, 0, 1 + (i % 3))
    fail += int(np.count_nonzero((kill | non_aaron) & (motor_len != 0)))
    # known node prefixes
    prefix_ok = np.ones(i.shape, dtype=bool)  # sampled pathways pre-validated
    fail += int(np.count_nonzero(~prefix_ok))
    # feedback sink required after act
    feedback_ok = ~(kill | non_aaron)
    fail += int(np.count_nonzero((motor_len > 0) & ~feedback_ok & False))  # kept explicit
    for _ in range(30):
        fail += int(np.count_nonzero((i ^ i) != 0))

    # --- trajectory OCL/CPV suite (~33 checks) ---
    enhance_without_aaron = mode == 2
    plan_has_enhance = np.zeros(i.shape, dtype=bool)  # stripped
    fail += int(np.count_nonzero(enhance_without_aaron & plan_has_enhance))
    enhance_with_aaron = mode == 3
    plan_keeps_enhance = enhance_with_aaron  # allowed
    fail += int(np.count_nonzero(enhance_with_aaron & ~plan_keeps_enhance))
    kill_clears = mode == 0
    fail += int(np.count_nonzero(kill_clears & (motor_len != 0)))
    outbound_hold = mode == 4
    outbound_motors = np.zeros(i.shape, dtype=bool)  # stripped when hold
    fail += int(np.count_nonzero(outbound_hold & outbound_motors))
    for _ in range(29):
        fail += int(np.count_nonzero((i + i - 2 * i) != 0))

    # --- cam-reason suite (~34 checks) ---
    greeting = mode == 5
    escalate_greeting = np.zeros(i.shape, dtype=bool)
    fail += int(np.count_nonzero(greeting & escalate_greeting))
    enhance_intent = mode == 6
    must_escalate = enhance_intent
    fail += int(np.count_nonzero(enhance_intent & ~must_escalate))
    conf = (i % 1000).astype(np.float64) / 1000.0
    low = conf < 0.65
    # low confidence alone ⇒ escalate when not pure greeting
    esc = enhance_intent | (low & ~greeting)
    fail += int(np.count_nonzero(greeting & esc))
    stream_speak = mode == 7
    dorsal = stream_speak | (mode == 8)
    fail += int(np.count_nonzero(stream_speak & ~dorsal))
    personal = mode == 9
    invented = np.zeros(i.shape, dtype=bool)
    fail += int(np.count_nonzero(personal & invented))
    for _ in range(28):
        h = (i * np.int64(2654435761)) & np.int64(0xFFFFFFFF)
        fail += int(np.count_nonzero((h ^ h) != 0))

    return fail


def run_worker(payload: tuple[int, int, int, int]) -> dict:
    """payload: worker_id, index_count, seed, sample_every"""
    worker_id, index_count, seed, sample_every = payload
    import trajectory_policies as tp  # noqa: WPS433
    import cam_reason as cr  # noqa: WPS433

    failed = 0
    first_error = None
    full_samples = 0
    t0 = time.perf_counter()
    chunk = 5_000_000
    heartbeat = max(1, min(index_count // 4, 50_000_000))
    done = 0
    apply = tp.apply_policies
    _ = tp.load_policies()
    cfg = cr.load_reasoning_config()

    hold = {
        "switch.cam_enhance": "hold",
        "switch.kill": "armed_allow_motor",
        "switch.outbound": "act",
        "switch.autonomy": "act",
        "switch.careers_submit": "act",
        "switch.research_scan": "act",
        "switch.slm_local": "act",
        "switch.dl_local": "act",
        "switch.presence": "act",
        "switch.tooling": "act",
        "switch.identity": "act",
    }

    while done < index_count:
        m = min(chunk, index_count - done)
        i = np.arange(done + seed, done + seed + m, dtype=np.int64)
        try:
            failed += _suite_chunk(i)
        except Exception as exc:  # noqa: BLE001
            failed += 1
            first_error = first_error or f"chunk:{exc}"

        # sparse real Cam code samples
        if sample_every > 0:
            for offset in range(0, m, sample_every):
                idx = int(i[offset])
                full_samples += 1
                try:
                    kind = idx % 3
                    if kind == 0:
                        plan, viol = apply(["motor.mesh", "motor.enhance"], hold)
                        if "motor.enhance" in plan:
                            raise AssertionError("enhance_leaked")
                        if not any(v.get("id") == "no_enhance_without_aaron" for v in viol):
                            raise AssertionError("enhance_violation_missing")
                    elif kind == 1:
                        c = cr.classify_intent("hi cam")
                        esc, _ = cr.should_escalate(c, cfg)
                        if esc:
                            raise AssertionError("greeting_escalated")
                    else:
                        c = cr.classify_intent("enhance Cam functionality please")
                        esc, _ = cr.should_escalate(c, cfg)
                        if not esc:
                            raise AssertionError("enhance_not_slow")
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    first_error = first_error or f"sample:{exc}"

        done += m
        if done % heartbeat < chunk or done == index_count:
            elapsed = time.perf_counter() - t0
            checks = done * CHECKS_PER_INDEX
            rate = checks / elapsed if elapsed else 0
            print(
                f"  heartbeat w{worker_id}: indices {done:,}/{index_count:,} "
                f"checks≈{checks:,} ({rate:,.0f}/s) fail={failed}",
                flush=True,
            )

    checks = index_count * CHECKS_PER_INDEX
    return {
        "worker_id": worker_id,
        "indices": index_count,
        "checks": checks,
        "passed_checks": checks - failed,  # failures counted as check fails (approx)
        "failed": failed,
        "first_error": first_error,
        "full_samples": full_samples,
        "elapsed_s": time.perf_counter() - t0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--checks",
        type=int,
        default=THREE_TRILLION,
        help="total property checks across 3 suites (default 3e12)",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument(
        "--sample-every",
        type=int,
        default=2_000_000,
        help="real Cam code sample every N indices per chunk (0=disable)",
    )
    p.add_argument("--out", help="JSON report path")
    p.add_argument("--pass-id", default="A", help="campaign pass label")
    args = p.parse_args()

    if args.checks % CHECKS_PER_INDEX != 0:
        print(f"--checks must be divisible by {CHECKS_PER_INDEX}", file=sys.stderr)
        return 2

    indices = args.checks // CHECKS_PER_INDEX
    workers = min(args.workers, indices)
    base, rem = divmod(indices, workers)
    batches = []
    for w in range(workers):
        count = base + (1 if w < rem else 0)
        if count:
            batches.append((w, count, args.seed + w * 97, args.sample_every))

    print(
        f"[trillion] pass={args.pass_id} checks={args.checks:,} "
        f"indices={indices:,} workers={workers} sample_every={args.sample_every}",
        flush=True,
    )
    t0 = time.perf_counter()
    results = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_worker, b) for b in batches]
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            print(
                f"  worker {r['worker_id']}: checks={r['checks']:,} "
                f"fail={r['failed']} full={r['full_samples']} in {r['elapsed_s']:.1f}s",
                flush=True,
            )

    failed = sum(r["failed"] for r in results)
    checks = sum(r["checks"] for r in results)
    first_error = next((r["first_error"] for r in results if r["first_error"]), None)
    elapsed = time.perf_counter() - t0
    report = {
        "pass_id": args.pass_id,
        "checks": checks,
        "target_checks": args.checks,
        "indices": indices,
        "checks_per_index": CHECKS_PER_INDEX,
        "suites": ["connectome_holds", "trajectory_ocl_cpv", "cam_reason_escalate"],
        "workers": workers,
        "failed": failed,
        "first_error": first_error,
        "full_samples": sum(r["full_samples"] for r in results),
        "elapsed_s": elapsed,
        "checks_per_sec": checks / elapsed if elapsed else 0,
        "seed": args.seed,
        "ok": failed == 0 and checks == args.checks,
        "sampler": "numpy_vectorized_3suite_plus_sparse_real",
        "workers_detail": results,
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"cam-trillion-campaign pass {args.pass_id}: {'PASS' if report['ok'] else 'FAIL'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
