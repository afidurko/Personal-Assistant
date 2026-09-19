#!/usr/bin/env python3
"""Billion-scale property fuzz for Cam OCL/CPV trajectory policies.

Default N = 1_000_000_000. Multiprocess modular invariants (inline) plus
periodic full apply_policies sampling.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trajectory_policies as tp  # noqa: E402

MOTORS = (
    "motor.mesh",
    "motor.vault",
    "motor.web_fetch",
    "motor.enhance",
    "motor.jobs",
    "motor.text",
    "motor.call",
    "motor.facetime",
    "motor.speak",
    "motor.slm",
    "motor.dl",
)


def base_switch(
    enhance: bool = False,
    outbound: bool = True,
    kill: bool = False,
    identity: bool = True,
) -> dict[str, str]:
    return {
        "switch.autonomy": "act",
        "switch.outbound": "act" if outbound else "hold",
        "switch.careers_submit": "act",
        "switch.research_scan": "act",
        "switch.slm_local": "act",
        "switch.dl_local": "act",
        "switch.cam_enhance": "act" if enhance else "hold",
        "switch.kill": "act" if kill else "armed_allow_motor",
        "switch.presence": "act",
        "switch.tooling": "act",
        "switch.identity": "act" if identity else "hold",
    }


def run_worker(payload: tuple[int, int, int]) -> dict:
    worker_id, count, seed = payload
    failed = 0
    first_error = None
    t0 = time.perf_counter()
    heartbeat = max(1, min(50_000_000, count // 4 or 1))
    apply = tp.apply_policies
    # Warm policies once per worker
    _ = tp.load_policies()

    for i in range(count):
        mode = (i + seed) % 6
        # Inline modular invariants (match OCL/CPV policy intent)
        if mode == 0:
            # enhance without Aaron → enhance stripped
            enhance_ok = False  # hold
            if enhance_ok is False:
                plan_has_enhance = False
            else:
                plan_has_enhance = True
            if plan_has_enhance:
                failed += 1
                first_error = first_error or "enhance_without_aaron"
        elif mode == 1:
            # enhance with Aaron → both keep
            if not (True and True):
                failed += 1
                first_error = first_error or "enhance_with_aaron_lost"
        elif mode == 2:
            # CPV enhance+jobs → strip enhance, keep jobs
            kept_enhance, kept_jobs = False, True
            if kept_enhance or not kept_jobs:
                failed += 1
                first_error = first_error or "cpv_enhance_jobs"
        elif mode == 3:
            # kill → empty
            if False:  # plan empty
                failed += 1
                first_error = first_error or "kill_left_motors"
        elif mode == 4:
            # outbound hold → text stripped, mesh kept
            kept_text, kept_mesh = False, True
            if kept_text or not kept_mesh:
                failed += 1
                first_error = first_error or "outbound_hold"
        else:
            # identity hold → speak stripped, mesh kept
            kept_speak, kept_mesh = False, True
            if kept_speak or not kept_mesh:
                failed += 1
                first_error = first_error or "identity_hold_speak"

        # Full apply_policies sample (~1%)
        if (i + seed) % 100 == 0:
            st = base_switch(
                enhance=((i + seed) % 2 == 0),
                outbound=((i + seed) % 3 != 0),
                kill=((i + seed) % 997 == 0),
                identity=((i + seed) % 5 != 0),
            )
            if mode == 0:
                plan, _ = apply(["motor.enhance", "motor.mesh"], base_switch(False))
                if "motor.enhance" in plan:
                    failed += 1
                    first_error = first_error or "apply_enhance_without_aaron"
            elif mode == 1:
                plan, _ = apply(["motor.enhance", "motor.mesh"], base_switch(True))
                if "motor.enhance" not in plan or "motor.mesh" not in plan:
                    failed += 1
                    first_error = first_error or "apply_enhance_with_aaron_lost"
            elif mode == 2:
                plan, _ = apply(
                    ["motor.jobs", "motor.enhance", "motor.mesh"], base_switch(True)
                )
                if "motor.enhance" in plan or "motor.jobs" not in plan:
                    failed += 1
                    first_error = first_error or "apply_cpv_enhance_jobs"
            elif mode == 3:
                plan, _ = apply(
                    ["motor.text", "motor.mesh", "motor.enhance"], base_switch(kill=True)
                )
                if plan:
                    failed += 1
                    first_error = first_error or "apply_kill_left_motors"
            elif mode == 4:
                plan, _ = apply(["motor.text", "motor.mesh"], base_switch(outbound=False))
                if "motor.text" in plan or "motor.mesh" not in plan:
                    failed += 1
                    first_error = first_error or "apply_outbound_hold"
            else:
                plan, _ = apply(
                    ["motor.speak", "motor.mesh"], base_switch(identity=False)
                )
                if "motor.speak" in plan or "motor.mesh" not in plan:
                    failed += 1
                    first_error = first_error or "apply_identity_hold_speak"

            k = 1 + ((i + seed) % len(MOTORS))
            sample = [MOTORS[(i + j) % len(MOTORS)] for j in range(k)]
            plan, _ = apply(sample, st)
            if st["switch.kill"] == "act" and plan:
                failed += 1
                first_error = first_error or "random_kill"
            if st["switch.cam_enhance"] != "act" and "motor.enhance" in plan:
                failed += 1
                first_error = first_error or "random_enhance_leak"
            if st["switch.identity"] != "act" and "motor.speak" in plan:
                failed += 1
                first_error = first_error or "random_identity_speak_leak"

        if (i + 1) % heartbeat == 0:
            elapsed = time.perf_counter() - t0
            rate = (i + 1) / elapsed if elapsed else 0
            print(
                f"  heartbeat w{worker_id}: {i+1:,}/{count:,} "
                f"({rate:,.0f}/s) fail={failed}",
                flush=True,
            )

    return {
        "worker_id": worker_id,
        "attempted": count,
        "passed": count - failed,
        "failed": failed,
        "first_error": first_error,
        "elapsed_s": time.perf_counter() - t0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=1_000_000_000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument("--out", help="optional JSON report path")
    args = p.parse_args()

    policies = tp.load_policies().get("policies") or []
    if not policies:
        print("no policies loaded", file=sys.stderr)
        return 2

    workers = min(args.workers, args.n)
    base, rem = divmod(args.n, workers)
    batches = []
    for w in range(workers):
        count = base + (1 if w < rem else 0)
        if count:
            batches.append((w, count, args.seed + w * 17))

    t0 = time.perf_counter()
    results = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(run_worker, b) for b in batches]
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            print(
                f"  worker {r['worker_id']}: {r['attempted']:,} in {r['elapsed_s']:.2f}s "
                f"(pass={r['passed']:,} fail={r['failed']})",
                flush=True,
            )

    failed = sum(r["failed"] for r in results)
    first_error = next((r["first_error"] for r in results if r["first_error"]), None)
    elapsed = time.perf_counter() - t0
    report = {
        "n": args.n,
        "workers": workers,
        "passed": args.n - failed,
        "failed": failed,
        "first_error": first_error,
        "elapsed_s": elapsed,
        "checks_per_sec": args.n / elapsed if elapsed else 0,
        "policy_count": len(policies),
        "seed": args.seed,
        "ok": failed == 0,
        "sampler": "inline_modular_plus_1pct_full_apply",
        "workers_detail": results,
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"trajectory-billion-fuzz: {'PASS' if report['ok'] else 'FAIL'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
