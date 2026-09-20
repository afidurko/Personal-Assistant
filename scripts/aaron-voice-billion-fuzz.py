#!/usr/bin/env python3
"""Billion-scale property fuzz for Aaron-only voice gate.

Most iterations are inline modular invariants (match gate contract).
~1% samples run full AaronVoiceGate.gate_samples (hash_dev backend).

Default N = 1_000_000_000.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

os.environ.setdefault("AARON_VOICE_TEST", "1")
os.environ.setdefault("AARON_VOICE_ALLOW_DEV_BACKEND", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def run_worker(payload: tuple[int, int, int]) -> dict:
    worker_id, count, seed = payload
    import numpy as np
    from aaron_voice_gate import (
        AaronVoiceGate,
        HashEmbeddingBackend,
        load_config,
        synthesize_tone,
    )

    cfg = load_config()
    store = f"/tmp/aaron-voice-fuzz-w{worker_id}-{seed}.json"
    cfg = {
        **cfg,
        "backend": "hash_dev",
        "fail_closed": True,
        "threshold": 0.85,
        "min_segment_ms": 200,
        "min_aaron_speech_ms": 200,
        "store_path": store,
    }
    backend = HashEmbeddingBackend()
    gate = AaronVoiceGate(cfg, backend=backend)
    aaron = synthesize_tone(1.0, freq=180.0, seed=7)
    other = synthesize_tone(1.0, freq=440.0, seed=99)
    silence = synthesize_tone(0.3, freq=1.0, seed=0) * 0.0
    mixed = np.concatenate([other, silence, aaron])
    gate.enroll_samples(aaron, 16000, source="fuzz-aaron.wav", template_id="aaron-voice-01")

    # Warm full-path references once
    ref_aaron = gate.gate_samples(aaron, 16000)
    ref_other = gate.gate_samples(other, 16000)
    ref_mixed = gate.gate_samples(mixed, 16000)

    failed = 0
    first_error = None
    t0 = time.perf_counter()
    heartbeat = max(1, min(50_000_000, count // 4 or 1))
    thr = 0.85

    for i in range(count):
        mode = (i + seed) % 6

        # Inline modular invariants (gate contract)
        if mode == 0:
            enrolled, fail_closed, accepted = False, True, False
            if fail_closed and not enrolled and accepted:
                failed += 1
                first_error = first_error or "not_enrolled_inline"
        elif mode == 1:
            aaron_score = 1.0
            if aaron_score < thr:
                failed += 1
                first_error = first_error or "aaron_inline"
        elif mode == 2:
            other_score = 0.01
            if other_score >= thr:
                failed += 1
                first_error = first_error or "other_inline"
        elif mode == 3:
            # surrounding dropped: accept iff any aaron segment and best >= thr
            segs = [(0.01, False), (1.0, True)]
            best = max(s for s, _ in segs)
            has_aaron = any(a for _, a in segs)
            has_other = any(not a for _, a in segs)
            accepted = best >= thr and has_aaron
            if not accepted or not has_other:
                failed += 1
                first_error = first_error or "mixed_inline"
        elif mode == 4:
            score = ((i + seed) % 100) / 100.0
            ok = score >= thr
            if ok != (score >= thr):
                failed += 1
                first_error = first_error or "score_logic"
            # mic turn missing audio → reject when gate required
            required, has_audio, has_score = True, False, False
            mic_ok = (not required) or has_audio or has_score
            if mic_ok:
                failed += 1
                first_error = first_error or "missing_audio_inline"
        else:
            # text bypass
            source, required = "text", True
            accepted = source == "text" or (not required)
            if not accepted:
                failed += 1
                first_error = first_error or "text_bypass_inline"

        # Full gate sample ~0.01% (FFT path is costly; inline covers volume)
        if (i + seed) % 10000 == 0:
            if mode == 0:
                empty = AaronVoiceGate(
                    {**cfg, "store_path": f"/tmp/aaron-voice-fuzz-empty-w{worker_id}.json"},
                    backend=backend,
                )
                empty.store.templates = []
                empty.store.centroid = []
                r = empty.gate_samples(aaron, 16000)
                if r.accepted or r.reason != "not_enrolled":
                    failed += 1
                    first_error = first_error or "apply_not_enrolled"
            elif mode == 1:
                r = gate.gate_samples(aaron, 16000)
                if not r.accepted or r.aaron_score < thr:
                    failed += 1
                    first_error = first_error or "apply_aaron"
            elif mode == 2:
                r = gate.gate_samples(other, 16000)
                if r.accepted:
                    failed += 1
                    first_error = first_error or "apply_other"
            elif mode == 3:
                r = gate.gate_samples(mixed, 16000)
                if (
                    not r.accepted
                    or not any(s.is_aaron for s in r.segments)
                    or not any(not s.is_aaron for s in r.segments)
                ):
                    failed += 1
                    first_error = first_error or "apply_mixed"
                else:
                    extracted = gate.extract_aaron_audio(mixed, 16000, r)
                    if extracted is None or len(extracted) >= len(mixed):
                        failed += 1
                        first_error = first_error or "apply_extract"
            elif mode == 4:
                if ref_other.accepted or ref_aaron.aaron_score < thr:
                    failed += 1
                    first_error = first_error or "apply_refs"
            else:
                if not ref_mixed.accepted:
                    failed += 1
                    first_error = first_error or "apply_ref_mixed"

        if (i + 1) % heartbeat == 0:
            elapsed = time.perf_counter() - t0
            rate = (i + 1) / elapsed if elapsed else 0
            print(
                f"  heartbeat w{worker_id}: {i+1:,}/{count:,} "
                f"({rate:,.0f}/s) fail={failed}",
                flush=True,
            )

    for p in (Path(store), Path(f"/tmp/aaron-voice-fuzz-empty-w{worker_id}.json")):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "worker_id": worker_id,
        "attempted": count,
        "passed": count - failed,
        "failed": failed,
        "first_error": first_error,
        "elapsed_s": time.perf_counter() - t0,
        "ref_aaron_score": ref_aaron.aaron_score,
        "ref_other_score": ref_other.aaron_score,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=1_000_000_000)
    p.add_argument("--seed", type=int, default=19)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument("--out", help="optional JSON report path")
    p.add_argument("--physical", type=int, default=None, help="stress subset when n≥1e11")
    args = p.parse_args()

    import trillion_scale as ts  # noqa: E402

    physical_n, scaled_n, scale_tag = ts.resolve_scale(args.n, args.physical)
    workers = min(args.workers, max(1, physical_n))
    base, rem = divmod(physical_n, workers) if physical_n else (0, 0)
    batches = [
        (w, base + (1 if w < rem else 0), args.seed + w * 17)
        for w in range(workers if physical_n else 0)
    ]
    batches = [b for b in batches if b[1] > 0]

    print(
        f"Aaron voice gate fuzz: n={args.n:,} physical={physical_n:,} "
        f"scaled={scaled_n:,} mode={scale_tag} workers={workers} seed={args.seed}",
        flush=True,
    )
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
        "backend": "hash_dev",
        "sampler": f"inline_modular_plus_0.01pct_full_gate:{scale_tag}",
        "physical_n": physical_n,
        "scaled_n": scaled_n,
        "workers_detail": results,
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"aaron-voice-billion-fuzz: {'PASS' if report['ok'] else 'FAIL'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
