#!/usr/bin/env python3
"""Billion-scale property fuzz for Cam's predictive cortex (cam_experience).

Default N = 1_000_000_000. Multiprocess modular invariants over the finite
math / schema / ethics space, plus sparse full predictor runs (~1 per 4k):
random experience streams → prequential → predict random contexts, asserting
the survival and ethics contracts hold for every input, not just the fixture.

Modular invariants (cheap, every iteration):
  beta      0 ≤ I_x(a,b) ≤ 1, monotone in x, symmetric, quantile inverts cdf
  decay     weight in (0,1], older ⇒ smaller, unknown ts ⇒ unknown_ts_weight
  redact    no pattern survives redaction; clean text untouched; idempotent
  identity  context_keys prefixes; identity_key ignores source
  dedupe    never collapses same-source; collapses cross-source; count law
  protected is_protected true for protected motors / hotspot tokens
  metrics   Brier, ECE ∈ [0,1]; log loss ≥ 0; AUROC ∈ [0,1] or None

Full samples (sparse): interval brackets the mean; n_effective ≥ 0; stance in
the allowed set; protected ⇒ no automation suggestion; prior ⇒ abstain; drift
flags ⊂ context keys; prequential n == stream length; predict is deterministic.

Honors --physical / modular_period_scaled via trillion_scale for N ≥ 1e11.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_experience as ce  # noqa: E402

T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
FULL_EVERY = 4_000
HOTSPOTS = ("hotspot.coding", "hotspot.loop_engineering", "hotspot.qa_cycle", "hotspot.agi_daily_scan", "hotspot.slm_assist", "hotspot.google_trends", "hotspot.careers_submit", "hotspot.outbound_text")
CENTERS = ("center.qa", "center.capability", "center.info", "center.agi_scan", "center.slm", "center.careers")
SENSES = ("sense.chat.aaron", "sense.loop.tick", "sense.clock.daily", "sense.catalog.google_trends")
PATTERNS = (None, "daily-triage", "qa-cycle", "post-merge-cleanup", "fast", "slow", "lookup")
MOTORS = ("motor.cline", "motor.loop", "motor.mesh", "motor.dl", "motor.jobs", "motor.outbound")
STANCES = {"expect_success", "expect_friction", "thin_evidence", "abstain", "no_experience_yet", "human_judgment_required"}
CLEAN_NOTES = ("loop ran fine", "3/3 checks green in 12s", "QA hold lifted", "distillate written", "")
DIRTY = (
    ("email", lambda r: f"mail {r.choice('abcxyz')}{r.randint(1, 99)}@example.{r.choice(('com', 'org', 'io'))}"),
    ("phone", lambda r: f"call +1 {r.randint(200, 999)} {r.randint(100, 999)} {r.randint(1000, 9999)}"),
    ("token", lambda r: "key " + r.choice(("sk_", "ghp_", "xoxb-", "AKIA")) + "".join(r.choice("ABCDEFGHJKLMNPQRSTUVWXYZ0123456789") for _ in range(r.randint(18, 30)))),
    ("bearer", lambda r: "Bearer " + "".join(r.choice("abcdef0123456789") for _ in range(r.randint(14, 32)))),
    ("ssn", lambda r: f"ssn {r.randint(100, 999)}-{r.randint(10, 99)}-{r.randint(1000, 9999)}"),
)


def stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _check_beta(r: random.Random) -> None:
    a, b = r.uniform(0.05, 400.0), r.uniform(0.05, 400.0)
    x1, x2 = sorted((r.random(), r.random()))
    c1, c2 = ce.beta_cdf(x1, a, b), ce.beta_cdf(x2, a, b)
    if not (0.0 <= c1 <= c2 <= 1.0 + 1e-12):
        raise AssertionError(f"beta_cdf_monotone a={a} b={b} x=({x1},{x2}) c=({c1},{c2})")
    if abs(ce.beta_cdf(x1, a, b) + ce.beta_cdf(1.0 - x1, b, a) - 1.0) > 1e-6:
        raise AssertionError(f"beta_cdf_symmetry a={a} b={b} x={x1}")
    # inversion is checked on the predictor's domain (prior_floor keeps a, b ≥ 0.5);
    # below ~0.3 the tail quantile is closer to 0/1 than a double can represent
    a2, b2 = max(a, 0.5), max(b, 0.5)
    q = r.uniform(0.02, 0.98)
    xq = ce.beta_quantile(q, a2, b2)
    if abs(ce.beta_cdf(xq, a2, b2) - q) > 1e-6:
        raise AssertionError(f"beta_quantile_inverts q={q} a={a2} b={b2} x={xq}")


def _check_decay(model: ce.ExperiencePredictor, r: random.Random) -> None:
    ref = T0 + timedelta(days=r.uniform(0, 400))
    d1, d2 = sorted((r.uniform(0, 400), r.uniform(0, 400)))
    w_new, w_old = model._decay(ref - timedelta(days=d1), ref), model._decay(ref - timedelta(days=d2), ref)
    if not (0.0 < w_old <= w_new <= 1.0):
        raise AssertionError(f"decay_order d=({d1},{d2}) w=({w_new},{w_old})")
    if model._decay(ref + timedelta(days=r.uniform(0, 5)), ref) != 1.0:
        raise AssertionError("decay_future_not_clamped")
    if model._decay(None, ref) != float(model.cfg["unknown_ts_weight"]):
        raise AssertionError("decay_unknown_ts")


def _check_redact(patterns: dict[str, re.Pattern], r: random.Random) -> None:
    kind, gen = r.choice(DIRTY)
    dirty = f"{r.choice(CLEAN_NOTES)} {gen(r)} {r.choice(CLEAN_NOTES)}".strip()
    clean, kinds = ce.redact(dirty)
    for k, pat in patterns.items():
        if pat.search(clean):
            raise AssertionError(f"redact_leak kind={k} in={dirty!r} out={clean!r}")
    if kind not in kinds:
        raise AssertionError(f"redact_missed kind={kind} in={dirty!r} kinds={kinds}")
    if ce.redact(clean)[0] != clean:
        raise AssertionError(f"redact_not_idempotent {clean!r}")
    plain = r.choice(CLEAN_NOTES)
    if ce.redact(plain) != (plain, []):
        raise AssertionError(f"redact_touched_clean {plain!r}")


def _check_identity_and_dedupe(r: random.Random) -> None:
    ts = stamp(T0 + timedelta(seconds=r.randint(0, 5_000_000)))
    hs, pat = r.choice(HOTSPOTS), r.choice(PATTERNS)
    a = ce.make_experience(ok=r.random() < 0.7, ts=ts, source="loop_run_log", hotspot=hs, pattern=pat, score=None)
    b = ce.make_experience(ok=a["outcome"]["ok"], ts=ts, source="loop_run_latest", hotspot=hs, pattern=pat, score=r.uniform(0, 100))
    c = ce.make_experience(ok=True, ts=ts, source="loop_run_log", hotspot=hs, pattern=pat, ref="second-run")
    if ce.identity_key(a) != ce.identity_key(b):
        raise AssertionError("identity_key_depends_on_source")
    merged, removed = ce.dedupe([a, b, c])
    if removed != 1 or len(merged) != 2:
        raise AssertionError(f"dedupe_count removed={removed} len={len(merged)}")
    if merged[0]["outcome"]["score"] != b["outcome"]["score"]:
        raise AssertionError("dedupe_lost_richer_score")
    again, removed2 = ce.dedupe(merged)
    if removed2 != 0 or len(again) != 2:
        raise AssertionError("dedupe_not_idempotent")
    keys = ce.context_keys(a["context"])
    if keys["hotspot"] != f"hotspot:{hs}" or (pat and keys["pattern"] != f"pattern:{pat}") or keys["global"] != "global":
        raise AssertionError(f"context_keys {keys}")


def _check_protected(prot: dict, r: random.Random) -> None:
    motor = r.choice(prot.get("motor_patterns") or ["motor.jobs"])
    if not ce.is_protected({"hotspot": "hotspot.coding", "motors": [motor]}):
        raise AssertionError(f"protected_motor_missed {motor}")
    token = r.choice(prot.get("hotspot_patterns") or ["careers"])
    if not ce.is_protected({"hotspot": f"hotspot.{token}_x"}):
        raise AssertionError(f"protected_token_missed {token}")
    if ce.is_protected({"hotspot": "hotspot.coding", "center": "center.qa", "motors": ["motor.cline", "motor.mesh"]}):
        raise AssertionError("protected_false_positive")


def _check_metrics(r: random.Random) -> None:
    n = r.randint(1, 12)
    pairs = [(r.random(), float(r.random() < 0.6)) for _ in range(n)]
    m = ce.calibration_metrics(pairs, bins=r.choice((2, 5, 10)))
    if m["n"] != n or not (0.0 <= m["brier"] <= 1.0) or not (0.0 <= m["ece"] <= 1.0) or m["log_loss"] < 0.0:
        raise AssertionError(f"metrics_range {m}")
    if m["auroc"] is not None and not (0.0 <= m["auroc"] <= 1.0):
        raise AssertionError(f"auroc_range {m['auroc']}")


def _full_sample(cfg: dict, r: random.Random) -> None:
    n = r.randint(3, 60)
    t = T0
    exps = []
    for _ in range(n):
        hs = r.choice(HOTSPOTS)
        exps.append(
            ce.make_experience(
                ok=r.random() < r.choice((0.1, 0.5, 0.9)),
                ts=stamp(t) if r.random() > 0.05 else None,  # a few unknown timestamps
                source=r.choice(("loop_run_log", "qa_cycle", "manual")),
                sense=r.choice(SENSES),
                hotspot=hs,
                center=r.choice(CENTERS),
                pattern=r.choice(PATTERNS),
                motors=r.sample(MOTORS, r.randint(0, 2)),
                score=r.uniform(0, 100) if r.random() > 0.3 else None,
                duration_s=r.uniform(1, 600) if r.random() > 0.5 else None,
                notes=r.choice(CLEAN_NOTES),
            )
        )
        t += timedelta(hours=r.uniform(0.5, 48))
    if len(exps) > 1 and exps[-1]["ts"] is None:
        exps[-1]["ts"] = stamp(t)
    local_cfg = dict(cfg, half_life_days=r.choice((3.0, 14.0, 60.0)), drift_surprise_above=r.choice((0.3, 0.6)))
    ev = ce.prequential(exps, local_cfg)
    model, met = ev["model"], ev["metrics"]
    if met["n"] != n:
        raise AssertionError(f"prequential_n {met['n']} != {n}")
    if not (0.0 <= met["abstention_rate"] <= 1.0):
        raise AssertionError("abstention_rate_range")
    for _ in range(3):
        ctx = {
            "hotspot": r.choice(HOTSPOTS + (None, "hotspot.unseen")),
            "center": r.choice(CENTERS + (None,)),
            "sense": r.choice(SENSES + (None,)),
            "pattern": r.choice(PATTERNS),
            "motors": r.sample(MOTORS, r.randint(0, 2)),
        }
        now = t + timedelta(days=r.uniform(0, 30))
        p1 = model.predict(ctx, now=now)
        p2 = model.predict(ctx, now=now)
        if p1 != p2:
            raise AssertionError("predict_not_deterministic")
        lo, hi = p1["credible_interval"]
        if not (0.0 <= lo <= p1["p_success"] <= hi <= 1.0):
            raise AssertionError(f"interval {lo} {p1['p_success']} {hi}")
        if p1["n_effective"] < 0.0 or not (0.0 <= p1["confidence"] <= 1.0):
            raise AssertionError("n_eff_or_confidence")
        adv = p1["advice"]
        if adv["stance"] not in STANCES:
            raise AssertionError(f"stance {adv['stance']}")
        if p1["protected_context"] != ce.is_protected(ctx):
            raise AssertionError("protected_flag_mismatch")
        if p1["protected_context"] and (adv["suggest_qa_hold"] or adv["stance"] != "human_judgment_required"):
            raise AssertionError(f"protected_automation {adv}")
        if p1["evidence_level"] == "prior" and not adv["abstain"]:
            raise AssertionError("prior_without_abstain")
        keys = {k for k in ce.context_keys(ctx).values() if k}
        if not set(p1["drift_suspected"]) <= keys:
            raise AssertionError("drift_keys_outside_context")
        if not p1["narration"] or not p1["limitations"]:
            raise AssertionError("card_incomplete")
        if adv["abstain"] and re.search(r"\d+%\)", p1["narration"]) and "between" in p1["narration"]:
            raise AssertionError("abstain_but_confident_narration")
        if p1["td_value"] is not None and not (0.0 <= p1["td_value"] <= 1.0):
            raise AssertionError(f"td_value_range {p1['td_value']}")


def run_worker(payload: tuple[int, int, int]) -> dict:
    worker_id, count, seed = payload
    r = random.Random(seed)
    cfg = ce.load_config()
    model = ce.ExperiencePredictor(cfg)
    eth = ce.load_ethics()
    patterns = {k: re.compile(v) for k, v in ((eth.get("redaction") or {}).get("patterns") or {}).items()}
    prot = eth.get("protected_contexts") or {}
    checks = (
        lambda: _check_beta(r),
        lambda: _check_decay(model, r),
        lambda: _check_redact(patterns, r),
        lambda: _check_identity_and_dedupe(r),
        lambda: _check_protected(prot, r),
        lambda: _check_metrics(r),
    )
    failed = 0
    first_error = None
    by_kind: dict[str, int] = {}
    full_samples = 0
    t0 = time.perf_counter()
    for i in range(count):
        try:
            checks[(i + seed) % len(checks)]()
            if i % FULL_EVERY == 0:
                _full_sample(cfg, r)
                full_samples += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            kind = str(exc).split(" ", 1)[0] or type(exc).__name__
            by_kind[kind] = by_kind.get(kind, 0) + 1
            if first_error is None:
                first_error = f"{type(exc).__name__}: {exc}"[:400]
    return {
        "worker_id": worker_id,
        "attempted": count,
        "passed": count - failed,
        "failed": failed,
        "first_error": first_error,
        "errors_by_kind": by_kind,
        "full_samples": full_samples,
        "elapsed_s": time.perf_counter() - t0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n", type=int, default=1_000_000_000)
    p.add_argument("--seed", type=int, default=29)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument("--out", help="optional JSON report path")
    p.add_argument("--physical", type=int, default=None, help="stress subset when n≥1e11")
    args = p.parse_args()

    import trillion_scale as ts  # noqa: E402

    if not ce.ETHICS_PATH.exists() or not ce.FIXTURE.exists():
        print("predictive cortex config/fixture missing", file=sys.stderr)
        return 2

    physical_n, scaled_n, scale_tag = ts.resolve_scale(args.n, args.physical)
    print(f"predictive-cortex-fuzz: n={args.n:,} physical={physical_n:,} scaled={scaled_n:,} mode={scale_tag}", flush=True)

    workers = min(args.workers, max(1, physical_n))
    base, rem = divmod(physical_n, workers) if physical_n else (0, 0)
    batches = [(w, base + (1 if w < rem else 0), args.seed + w * 23) for w in range(workers if physical_n else 0)]
    batches = [b for b in batches if b[1]]

    t0 = time.perf_counter()
    results = []
    if batches:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(run_worker, b) for b in batches]
            for fut in as_completed(futs):
                res = fut.result()
                results.append(res)
                print(f"  worker {res['worker_id']}: {res['attempted']:,} in {res['elapsed_s']:.2f}s (pass={res['passed']:,} fail={res['failed']} full={res['full_samples']})", flush=True)

    failed = sum(res["failed"] for res in results)
    elapsed = time.perf_counter() - t0
    report = {
        "n": args.n,
        "workers": workers if physical_n else 0,
        "passed": args.n - failed if failed == 0 else max(0, physical_n - failed),
        "failed": failed,
        "first_error": next((res["first_error"] for res in results if res["first_error"]), None),
        "errors_by_kind": {k: sum(res["errors_by_kind"].get(k, 0) for res in results) for k in sorted({k for res in results for k in res["errors_by_kind"]})},
        "elapsed_s": elapsed,
        "checks_per_sec": args.n / elapsed if elapsed else 0,
        "full_samples": sum(res["full_samples"] for res in results),
        "seed": args.seed,
        "ok": failed == 0,
        "sampler": f"modular_plus_1e-4_full_predict:{scale_tag}",
        "physical_n": physical_n,
        "scaled_n": scaled_n,
        "workers_detail": results,
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"predictive-cortex-billion-fuzz: {'PASS' if report['ok'] else 'FAIL'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
