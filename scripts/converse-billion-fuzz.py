#!/usr/bin/env python3
"""Trillion-scale overlay × intent matrix for Cam converse.

Companion to cam-reason-billion-fuzz. Physical stress + modular scale at N≥1e11.
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
import converse_overlays as co  # noqa: E402
import trillion_scale as ts  # noqa: E402


def _assert_catalog_smoke() -> None:
    import cam_inproc

    smoke = cam_inproc.catalog_sense_smoke()
    routed = smoke.get("route") or {}
    if "motor.public_apis" not in (routed.get("motor_plan") or []):
        raise AssertionError("public_apis_route_motor")
    hit = smoke.get("public_apis") or {}
    if not hit.get("offline") or int(hit.get("returned") or 0) < 1:
        raise AssertionError("public_apis_offline_empty")
    trends = smoke.get("google_trends") or {}
    if not trends.get("offline") or int(trends.get("returned") or 0) < 1:
        raise AssertionError("google_trends_offline_empty")


def run_worker(payload: tuple[int, int, int]) -> dict:
    worker_id, count, seed = payload
    import cam_reason as cr

    cfg = co.load_overlays()
    check = co.check_overlays(cfg)
    if not check.get("ok"):
        return {
            "worker_id": worker_id,
            "attempted": 0,
            "passed": 0,
            "failed": 1,
            "first_error": f"overlay_check:{check.get('errors')}",
            "elapsed_s": 0.0,
        }

    probes = co.overlay_probes(cfg)
    intent_probes = list((cfg.get("intent_probes") or {}).items())
    if not probes or not intent_probes:
        return {
            "worker_id": worker_id,
            "attempted": 0,
            "passed": 0,
            "failed": 1,
            "first_error": "empty_probes",
            "elapsed_s": 0.0,
        }

    try:
        _assert_catalog_smoke()
        hi = co.speak_from_trace(
            "hi cam",
            {"classification": {"intents": ["greeting"]}, "path": "fast"},
        )
        if "Aaron" not in hi:
            raise AssertionError("greeting_overlay")
    except Exception as exc:  # noqa: BLE001
        return {
            "worker_id": worker_id,
            "attempted": 0,
            "passed": 0,
            "failed": 1,
            "first_error": f"bootstrap:{type(exc).__name__}:{exc}",
            "elapsed_s": 0.0,
        }

    failed = 0
    first_error = None
    t0 = time.perf_counter()
    heartbeat = max(1, min(50_000_000, count // 4 or 1))

    for i in range(count):
        mode = (i + seed) % 6
        try:
            if mode == 0:
                oid, probe, must = probes[(i + seed) % len(probes)]
                hit = co.match_overlay(probe.lower(), cfg)
                if not hit or hit.get("id") != oid:
                    raise AssertionError(f"match:{oid}:{probe}")
                reply = co.speak_from_trace(probe, {"classification": {"intents": ["general"]}})
                if must not in reply:
                    raise AssertionError(f"reply:{oid}")
            elif mode == 1:
                intent, probe = intent_probes[(i + seed) % len(intent_probes)]
                c = cr.classify_intent(probe)
                if intent not in (c.get("intents") or []):
                    raise AssertionError(f"intent:{intent}:{probe}")
                reply = co.speak_from_trace(
                    probe, {"classification": c, "path": "fast"}
                )
                expect = (cfg.get("intents") or {}).get(intent) or ""
                overlay = co.match_overlay(probe.lower(), cfg)
                if overlay:
                    if overlay.get("reply") != reply:
                        raise AssertionError(f"intent_overlay:{intent}")
                elif reply != expect:
                    raise AssertionError(f"intent_reply:{intent}")
            elif mode == 2:
                empty = co.speak_from_trace("", {"path": "fast"})
                if empty != cfg.get("empty"):
                    raise AssertionError("empty")
            elif mode == 3:
                reply = co.speak_from_trace(
                    "implement a small refactor",
                    {
                        "path": "slow",
                        "hotspot_id": "hotspot.coding",
                        "motor_plan": ["motor.cline"],
                        "classification": {"intents": ["general"]},
                    },
                )
                if "hotspot.coding" not in reply or "motor.cline" not in reply:
                    raise AssertionError("slow_plan")
            elif mode == 4:
                blob = json.dumps(cfg)
                if "cam-face-higgsfield" in blob or "Speak clip" in blob:
                    raise AssertionError("speak_clip_in_overlays")
            else:
                short = "ping"
                reply = co.speak_from_trace(
                    short,
                    {"path": "fast", "classification": {"intents": ["general"]}},
                )
                if short not in reply:
                    raise AssertionError("echo")
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
        "elapsed_s": time.perf_counter() - t0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=ts.THREE_TRILLION)
    p.add_argument("--seed", type=int, default=29)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument("--out", help="optional JSON report path")
    p.add_argument("--physical", type=int, default=None)
    args = p.parse_args()

    physical_n, scaled_n, scale_tag = ts.resolve_scale(args.n, args.physical)
    print(
        f"converse-fuzz: n={args.n:,} physical={physical_n:,} scaled={scaled_n:,} "
        f"mode={scale_tag}",
        flush=True,
    )

    workers = min(args.workers, max(1, physical_n))
    base, rem = divmod(physical_n, workers) if physical_n else (0, 0)
    batches = [
        (w, base + (1 if w < rem else 0), args.seed + w * 13)
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
                    f"(pass={r['passed']:,} fail={r['failed']})",
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
        "seed": args.seed,
        "ok": failed == 0,
        "sampler": f"overlay_intent_matrix:{scale_tag}",
        "physical_n": physical_n,
        "scaled_n": scaled_n,
        "workers_detail": results,
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"converse-billion-fuzz: {'PASS' if report['ok'] else 'FAIL'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
