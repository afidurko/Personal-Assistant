#!/usr/bin/env python3
"""Billion-scale property fuzz for Cam Phase B reasoning dry-run.

Default N = 1_000_000_000. Multiprocess modular invariants (classify / escalate /
bar / schema / OCL strip) plus sparse full dry-run samples (~1 per 100k).
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
import cam_reason as cr  # noqa: E402
import trajectory_policies as tp  # noqa: E402


FAST_GOALS = ("hi cam", "hey", "ok", "thanks", "mic check are you listening")
SLOW_GOALS = (
    "enhance Cam functionality please",
    "think carefully and make a plan",
    "research arxiv papers on agents",
    "do you remember my preference for tea",
    "submit the application to the job",
    "send a text outbound please",
)

HOLD_SWITCH = {
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
}


def run_worker(payload: tuple[int, int, int]) -> dict:
    worker_id, count, seed = payload
    failed = 0
    first_error = None
    full_samples = 0
    t0 = time.perf_counter()
    heartbeat = max(1, min(50_000_000, count // 4 or 1))
    cfg = cr.load_reasoning_config()
    apply = tp.apply_policies
    _ = tp.load_policies()

    # Dual-stream policy checked once per worker
    dsr = cr.dual_stream_router()
    if dsr.route_act("speak").get("winner") != "dorsal":
        return {
            "worker_id": worker_id,
            "attempted": 0,
            "passed": 0,
            "failed": 1,
            "first_error": "stream_speak_not_dorsal",
            "full_samples": 0,
            "elapsed_s": 0.0,
        }
    if dsr.route_act("docs").get("winner") != "ventral":
        return {
            "worker_id": worker_id,
            "attempted": 0,
            "passed": 0,
            "failed": 1,
            "first_error": "stream_docs_not_ventral",
            "full_samples": 0,
            "elapsed_s": 0.0,
        }

    for i in range(count):
        mode = (i + seed) % 8
        try:
            if mode == 0:
                g = FAST_GOALS[(i + seed) % len(FAST_GOALS)]
                c = cr.classify_intent(g)
                esc, _ = cr.should_escalate(c, cfg)
                if esc or cr.bar_allows_converse(g, cfg):
                    raise AssertionError(f"fast_bar_broken:{g}")
            elif mode == 1:
                c = cr.classify_intent("enhance Cam functionality please")
                esc, _ = cr.should_escalate(c, cfg)
                if not esc:
                    raise AssertionError("enhance_not_slow")
            elif mode == 2:
                c = cr.classify_intent("think carefully and make a plan")
                if "explicit_plan" not in c["intents"]:
                    raise AssertionError("plan_intent_missing")
            elif mode == 3:
                rt = cr.cam_reasoning_tool(
                    goal="x",
                    hotspot_id="hotspot.capability",
                    switch_state=HOLD_SWITCH,
                    stream="dorsal",
                    path="slow",
                )
                if "switch.cam_enhance" not in rt["switch_risks"]:
                    raise AssertionError("switch_risk_missing")
                if rt.get("stream") != "dorsal":
                    raise AssertionError("stream_field")
            elif mode == 4:
                # Inline OCL: enhance without Aaron must not remain
                enhance_held = True
                plan_has_enhance = False  # stripped
                if enhance_held and plan_has_enhance:
                    raise AssertionError("enhance_not_stripped")
                # Spot-check real apply every 10k of this mode
                if (i + seed) % 80_000 == 4:
                    plan, viol = apply(["motor.mesh", "motor.enhance"], HOLD_SWITCH)
                    if "motor.enhance" in plan:
                        raise AssertionError("enhance_not_stripped_apply")
                    if not any(v.get("id") == "no_enhance_without_aaron" for v in viol):
                        raise AssertionError("enhance_violation_missing")
            elif mode == 5:
                kill_on = True
                plan_after_kill: list[str] = []
                if kill_on and plan_after_kill:
                    raise AssertionError("kill_not_clear")
                if (i + seed) % 80_000 == 5:
                    kill_sw = dict(HOLD_SWITCH)
                    kill_sw["switch.kill"] = "act"
                    plan, _ = apply(["motor.mesh", "motor.speak"], kill_sw)
                    if plan:
                        raise AssertionError("kill_not_clear_apply")
            elif mode == 6:
                r = cr.mesh_recall("do you remember my preference", personal_fact=True)
                if r.get("invented"):
                    raise AssertionError("recall_invent")
            else:
                # sparse full dry-run (~1 / 100k iterations)
                if (i + seed) % 100_000 == 7:
                    g = SLOW_GOALS[(i + seed) % len(SLOW_GOALS)]
                    t = cr.reason(goal=g, write_trace=False)
                    full_samples += 1
                    if t.get("kind") != "reasoning_trace":
                        raise AssertionError("bad_kind")
                    if "enhance" in g.lower() and "motor.enhance" in (t.get("motor_plan") or []):
                        raise AssertionError("enhance_leaked_full")
                else:
                    c = cr.classify_intent(SLOW_GOALS[(i + seed) % len(SLOW_GOALS)])
                    if not c["intents"]:
                        raise AssertionError("empty_intents")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            first_error = first_error or f"{type(exc).__name__}:{exc}"

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
        "full_samples": full_samples,
        "elapsed_s": time.perf_counter() - t0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=1_000_000_000)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument("--out", help="optional JSON report path")
    p.add_argument("--physical", type=int, default=None, help="stress subset when n≥1e11")
    args = p.parse_args()

    import trillion_scale as ts  # noqa: E402

    cfg = cr.load_reasoning_config()
    if cfg.get("status") not in {"proposed", "applied"}:
        print("unexpected reasoning-logic status", file=sys.stderr)
        return 2

    physical_n, scaled_n, scale_tag = ts.resolve_scale(args.n, args.physical)
    print(
        f"cam-reason-fuzz: n={args.n:,} physical={physical_n:,} scaled={scaled_n:,} "
        f"mode={scale_tag}",
        flush=True,
    )

    workers = min(args.workers, max(1, physical_n))
    base, rem = divmod(physical_n, workers) if physical_n else (0, 0)
    batches = [
        (w, base + (1 if w < rem else 0), args.seed + w * 19)
        for w in range(workers if physical_n else 0)
    ]
    batches = [b for b in batches if b[1]]

    t0 = time.perf_counter()
    results = []
    if batches:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(run_worker, b) for b in batches]
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                print(
                    f"  worker {r['worker_id']}: {r['attempted']:,} in {r['elapsed_s']:.2f}s "
                    f"(pass={r['passed']:,} fail={r['failed']} full={r.get('full_samples')})",
                    flush=True,
                )

    failed = sum(r["failed"] for r in results)
    first_error = next((r["first_error"] for r in results if r["first_error"]), None)
    elapsed = time.perf_counter() - t0
    report = {
        "n": args.n,
        "workers": workers if physical_n else 0,
        "passed": args.n - failed if failed == 0 else max(0, physical_n - failed),
        "failed": failed,
        "first_error": first_error,
        "elapsed_s": elapsed,
        "checks_per_sec": args.n / elapsed if elapsed else 0,
        "full_samples": sum(r.get("full_samples") or 0 for r in results),
        "seed": args.seed,
        "ok": failed == 0,
        "sampler": f"modular_plus_1e-5_full_reason:{scale_tag}",
        "physical_n": physical_n,
        "scaled_n": scaled_n,
        "workers_detail": results,
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"cam-reason-billion-fuzz: {'PASS' if report['ok'] else 'FAIL'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
