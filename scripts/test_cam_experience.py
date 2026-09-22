#!/usr/bin/env python3
"""Unit tests for Cam predictive cortex (cam_experience + cam-predict CLI)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_experience as ce  # noqa: E402

CLI = ROOT / "scripts" / "cam-predict.py"
T0 = datetime(2026, 9, 1, tzinfo=timezone.utc)


def stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def stream(spec: list[tuple[str, bool]], start: datetime = T0, step_hours: int = 6) -> list[dict]:
    out = []
    t = start
    for hotspot, ok in spec:
        out.append(
            ce.make_experience(
                ok=ok,
                ts=stamp(t),
                source="test",
                sense="sense.chat.aaron",
                hotspot=hotspot,
                center="center.qa" if "qa" in hotspot else "center.capability",
                score=90.0 if ok else 40.0,
                duration_s=10.0,
            )
        )
        t += timedelta(hours=step_hours)
    return out


class BetaMathTests(unittest.TestCase):
    def test_beta_cdf_uniform(self) -> None:
        self.assertAlmostEqual(ce.beta_cdf(0.3, 1.0, 1.0), 0.3, places=6)

    def test_beta_cdf_symmetric(self) -> None:
        self.assertAlmostEqual(ce.beta_cdf(0.5, 2.0, 2.0), 0.5, places=6)
        self.assertAlmostEqual(ce.beta_cdf(0.5, 5.0, 5.0), 0.5, places=6)

    def test_beta_quantile_inverts_cdf(self) -> None:
        for a, b, q in ((2.0, 5.0, 0.05), (7.5, 1.5, 0.95), (1.0, 1.0, 0.5)):
            x = ce.beta_quantile(q, a, b)
            self.assertAlmostEqual(ce.beta_cdf(x, a, b), q, places=5)


class PredictorTests(unittest.TestCase):
    def test_prior_when_no_experience(self) -> None:
        m = ce.ExperiencePredictor()
        r = m.predict({"hotspot": "hotspot.x"}, now=T0)
        self.assertAlmostEqual(r["p_success"], 0.5)
        self.assertEqual(r["evidence_level"], "prior")
        self.assertEqual(r["advice"]["stance"], "no_experience_yet")

    def test_learns_hotspot_rate_and_backs_off(self) -> None:
        m = ce.ExperiencePredictor()
        for exp in stream([("hotspot.good", True)] * 8 + [("hotspot.bad", False)] * 8):
            m.update(exp)
        now = T0 + timedelta(days=5)
        good = m.predict({"hotspot": "hotspot.good", "center": "center.capability", "sense": "sense.chat.aaron"}, now=now)
        bad = m.predict({"hotspot": "hotspot.bad", "center": "center.capability", "sense": "sense.chat.aaron"}, now=now)
        self.assertGreater(good["p_success"], 0.8)
        self.assertLess(bad["p_success"], 0.2)
        self.assertEqual(good["evidence_level"], "hotspot")
        # unseen hotspot backs off to center-level evidence (mixed → near 0.5)
        unseen = m.predict({"hotspot": "hotspot.new", "center": "center.capability", "sense": "sense.chat.aaron"}, now=now)
        self.assertEqual(unseen["evidence_level"], "center")
        self.assertTrue(0.3 < unseen["p_success"] < 0.7)
        self.assertLessEqual(good["credible_interval"][0], good["p_success"])
        self.assertLessEqual(good["p_success"], good["credible_interval"][1])

    def test_forgetting_prefers_recent_outcomes(self) -> None:
        m = ce.ExperiencePredictor({"half_life_days": 2.0})
        old = stream([("hotspot.h", False)] * 6, start=T0, step_hours=1)
        recent = stream([("hotspot.h", True)] * 3, start=T0 + timedelta(days=20), step_hours=1)
        for exp in old + recent:
            m.update(exp)
        r = m.predict({"hotspot": "hotspot.h"}, now=T0 + timedelta(days=20, hours=4))
        self.assertGreater(r["p_success"], 0.7)

    def test_td_value_and_surprise(self) -> None:
        m = ce.ExperiencePredictor({"td_alpha": 0.5})
        exps = [
            ce.make_experience(ok=ok, ts=stamp(T0 + timedelta(hours=i)), hotspot="hotspot.h")
            for i, ok in enumerate((True, True, False))
        ]
        s1 = m.update(exps[0])
        m.update(exps[1])
        s3 = m.update(exps[2])
        self.assertIn("hotspot", s1)
        # a failure after successes is a bigger surprise than the first success
        self.assertGreater(s3["hotspot"], s1["hotspot"])
        r = m.predict({"hotspot": "hotspot.h"}, now=T0 + timedelta(days=1))
        self.assertIsNotNone(r["td_value"])
        self.assertTrue(0.0 <= r["td_value"] <= 1.0)
        self.assertTrue(r["advice"]["suggest_qa_hold"])


class CalibrationTests(unittest.TestCase):
    def test_perfect_predictor(self) -> None:
        pairs = [(1.0, 1.0)] * 5 + [(0.0, 0.0)] * 5
        m = ce.calibration_metrics(pairs)
        self.assertEqual(m["brier"], 0.0)
        self.assertEqual(m["ece"], 0.0)
        self.assertEqual(m["auroc"], 1.0)

    def test_constant_half_on_balanced_is_calibrated(self) -> None:
        pairs = [(0.5, 1.0), (0.5, 0.0)] * 10
        m = ce.calibration_metrics(pairs)
        self.assertAlmostEqual(m["brier"], 0.25)
        self.assertAlmostEqual(m["ece"], 0.0)
        self.assertIsNone(m["auroc"] if m["auroc"] is None else None)

    def test_prequential_on_separable_stream_has_skill(self) -> None:
        spec = []
        for i in range(60):
            spec.append(("hotspot.good", i % 10 != 0))   # 90% ok
            spec.append(("hotspot.bad", i % 10 == 0))    # 10% ok
        ev = ce.prequential(stream(spec, step_hours=2))
        met = ev["metrics"]
        self.assertEqual(met["n"], 120)
        self.assertGreater(met["brier_skill"], 0.3)
        self.assertGreater(met["auroc"], 0.85)
        self.assertLess(met["ece"], 0.2)
        self.assertIn("score_mae", met)


class IngestTests(unittest.TestCase):
    def test_loop_log_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "loop-run-log.md"
            p.write_text(
                "| When (UTC) | Pattern | Level | Status | Score | Notes |\n"
                "|---|---|---|---|---|---|\n"
                "| — | — | — | bootstrapped | — | Spine created |\n"
                "| 2026-09-19T21:56:44Z | `daily-triage` | L1 | ok | 67 | actions=3 |\n"
                "| 2026-09-20T01:31:56Z | `daily-triage` | L1 | fail | 20 | actions=1 |\n",
                encoding="utf-8",
            )
            rows = ce.ingest_loop_log(p)
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["outcome"]["ok"])
        self.assertFalse(rows[1]["outcome"]["ok"])
        self.assertEqual(rows[0]["context"]["pattern"], "daily-triage")
        self.assertEqual(rows[0]["outcome"]["score"], 67.0)

    def test_fixture_loads_sorted(self) -> None:
        exps, counts = ce.load_experiences(offline=True)
        self.assertGreaterEqual(counts["fixture"], 50)
        stamps = [e["ts"] for e in exps]
        self.assertEqual(stamps, sorted(stamps))

    def test_record_appends_to_override_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "exp.jsonl"
            exp = ce.make_experience(ok=True, hotspot="hotspot.t", score=77)
            ce.record_experience(exp, log)
            ce.record_experience(ce.make_experience(ok=False, hotspot="hotspot.t"), log)
            self.assertEqual(len(ce.read_jsonl(log)), 2)


class CliTests(unittest.TestCase):
    def test_offline_predict_by_hotspot(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(CLI), "--offline", "--no-write", "--hotspot", "hotspot.loop_engineering", "--pattern", "daily-triage", "--sense", "sense.loop.tick"],
            text=True,
        )
        doc = json.loads(out)
        self.assertEqual(doc["kind"], "experience_prediction")
        self.assertTrue(0.0 <= doc["prediction"]["p_success"] <= 1.0)
        self.assertNotEqual(doc["prediction"]["evidence_level"], "prior")
        self.assertIn("switch.cam_enhance", doc["gate"])

    def test_offline_goal_routes_through_connectome(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(CLI), "--offline", "--no-write", "--sense", "sense.experience.outcome", "--goal", "predict outcome from experience"],
            text=True,
        )
        doc = json.loads(out)
        self.assertEqual(doc["route"]["hotspot_id"], "hotspot.predict_from_experience")
        self.assertIn("motor.dl", doc["route"]["motor_plan"])

    def test_offline_report(self) -> None:
        out = subprocess.check_output([sys.executable, str(CLI), "--offline", "--no-write", "--report"], text=True)
        doc = json.loads(out)
        self.assertEqual(doc["kind"], "predictive_cortex_report")
        self.assertEqual(doc["calibration"]["n"], doc["experience_count"])
        self.assertTrue(any(r["key"] == "global" for r in doc["contexts"]))

    def test_record_requires_outcome_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, CAM_EXPERIENCE_LOG=str(Path(tmp) / "exp.jsonl"))
            proc = subprocess.run([sys.executable, str(CLI), "--record", "--hotspot", "hotspot.t"], capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 2)
            proc = subprocess.run([sys.executable, str(CLI), "--record", "--ok", "--hotspot", "hotspot.t", "--score", "88"], capture_output=True, text=True, env=env)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(len(ce.read_jsonl(Path(tmp) / "exp.jsonl")), 1)


class SurvivalTests(unittest.TestCase):
    """Each test encodes a way the first draft would have failed."""

    def test_cross_source_duplicate_collapses_but_same_source_does_not(self) -> None:
        ts = stamp(T0)
        a = ce.make_experience(ok=True, ts=ts, source="loop_run_log", hotspot="hotspot.loop_engineering", pattern="daily-triage", score=None)
        b = ce.make_experience(ok=True, ts=ts, source="loop_run_latest", hotspot="hotspot.loop_engineering", pattern="daily-triage", score=91.0)
        q1 = ce.make_experience(ok=True, ts=ts, source="qa_cycle", hotspot="hotspot.qa_cycle", pattern="qa-cycle", ref="cycle-01")
        q2 = ce.make_experience(ok=False, ts=ts, source="qa_cycle", hotspot="hotspot.qa_cycle", pattern="qa-cycle", ref="cycle-02")
        merged, removed = ce.dedupe([a, b, q1, q2])
        self.assertEqual(removed, 1)
        self.assertEqual(len(merged), 3)
        loop = next(m for m in merged if m["context"]["hotspot"] == "hotspot.loop_engineering")
        self.assertEqual(loop["outcome"]["score"], 91.0)  # richer field merged in
        self.assertEqual(loop["source"], "loop_run_latest+loop_run_log")

    def test_live_load_removes_latest_json_duplicate(self) -> None:
        exps, counts = ce.load_experiences()
        loop = [e for e in exps if e["context"]["hotspot"] == "hotspot.loop_engineering"]
        stamps = [e["ts"] for e in loop]
        self.assertEqual(len(stamps), len(set(stamps)), "same loop run counted twice")
        self.assertGreaterEqual(counts["_duplicates_removed"], 0)

    def test_unknown_timestamp_is_not_fresh(self) -> None:
        m = ce.ExperiencePredictor({"unknown_ts_weight": 0.25})
        ref = T0 + timedelta(days=1)
        self.assertAlmostEqual(m._decay(None, ref), 0.25)
        self.assertGreater(m._decay(T0, ref), 0.9)
        bad = ce.make_experience(ok=False, ts="not-a-date", hotspot="hotspot.h")
        m.update(bad)
        self.assertEqual(m.predict({"hotspot": "hotspot.h"}, now=ref)["n_effective"], 0.25)

    def test_source_error_is_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.jsonl"
            bad.write_bytes(b"\xff\xfe not utf8 \x00")
            exps, counts = ce.load_experiences(offline=True, extra=[bad])
            self.assertGreaterEqual(counts["fixture"], 50)
            self.assertEqual(counts["_source_errors"], 1)
            self.assertEqual(ce.LAST_SOURCE_ERRORS[0]["source"], "extra:bad.jsonl")
            self.assertGreaterEqual(len(exps), 50)

    def test_drift_detection_widens_interval(self) -> None:
        m = ce.ExperiencePredictor({"half_life_days": 365.0, "drift_surprise_above": 0.6, "drift_ewma_beta": 0.5})
        t = T0
        for _ in range(12):
            m.update(ce.make_experience(ok=True, ts=stamp(t), hotspot="hotspot.h", score=None))
            t += timedelta(hours=1)
        stable = m.predict({"hotspot": "hotspot.h"}, now=t)
        self.assertFalse(stable["drift_suspected"])
        for _ in range(3):
            m.update(ce.make_experience(ok=False, ts=stamp(t), hotspot="hotspot.h", score=None))
            t += timedelta(hours=1)
        shifted = m.predict({"hotspot": "hotspot.h"}, now=t)
        self.assertIn("hotspot:hotspot.h", shifted["drift_suspected"])
        self.assertTrue(shifted["advice"]["suggest_gather_more"])
        width = lambda r: r["credible_interval"][1] - r["credible_interval"][0]  # noqa: E731
        self.assertGreater(width(shifted), width(stable))
        # without inflation the same evidence would give a narrower interval
        m.cfg["drift_inflation"] = 1.0
        self.assertLess(width(m.predict({"hotspot": "hotspot.h"}, now=t)), width(shifted))

    def test_single_child_parent_is_weak_prior(self) -> None:
        # center.qa evidence comes only from hotspot.qa_cycle; a sibling hotspot must not inherit it fully
        spec = [("hotspot.qa_cycle", True)] * 40
        exps = stream(spec)
        strong = ce.ExperiencePredictor({"backoff_single_child_factor": 1.0, "half_life_days": 365.0})
        weak = ce.ExperiencePredictor({"backoff_single_child_factor": 0.5, "half_life_days": 365.0})
        for e in exps:
            strong.update(e)
            weak.update(e)
        ctx = {"hotspot": "hotspot.new_loop", "center": "center.qa", "sense": "sense.chat.aaron"}
        now = T0 + timedelta(days=11)
        ps, pw = strong.predict(ctx, now=now), weak.predict(ctx, now=now)
        self.assertLess(pw["p_success"], ps["p_success"])
        self.assertGreater(pw["credible_interval"][1] - pw["credible_interval"][0], ps["credible_interval"][1] - ps["credible_interval"][0])
        self.assertEqual(next(c for c in pw["backoff_chain"] if c["level"] == "center")["children"], 1)

    def test_stale_context_reported(self) -> None:
        exps = stream([("hotspot.old", True), ("hotspot.old", True)])
        with tempfile.TemporaryDirectory() as tmp:
            extra = Path(tmp) / "old.jsonl"
            extra.write_text("".join(json.dumps(e) + "\n" for e in exps), encoding="utf-8")
            rep = ce.build_report(offline=True, extra=[extra], now=T0 + timedelta(days=40))
        keys = {s["key"] for s in rep["coverage"]["stale_contexts"]}
        self.assertIn("hotspot:hotspot.old", keys)

    def test_offline_report_uses_fixture_clock(self) -> None:
        rep = ce.build_report(offline=True)
        self.assertEqual(rep["coverage"]["stale_contexts"], [])

    def test_runtime_log_rotates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "exp.jsonl"
            cfg = dict(ce.DEFAULTS, max_runtime_rows=5, keep_runtime_rows=2)
            for i in range(7):
                ce.record_experience(ce.make_experience(ok=True, ts=stamp(T0 + timedelta(hours=i)), hotspot="hotspot.r"), log, cfg)
            live = ce.read_jsonl(log)
            archives = list(Path(tmp).glob("exp-*.jsonl"))
            self.assertEqual(len(archives), 1)
            self.assertLessEqual(len(live), 5)
            self.assertEqual(len(live) + sum(len(ce.read_jsonl(a)) for a in archives), 7)

    def test_kill_switch_refuses_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "exp.jsonl"
            old = os.environ.get("CAM_KILL")
            os.environ["CAM_KILL"] = "1"
            try:
                with self.assertRaises(ce.KillSwitchActive):
                    ce.record_experience(ce.make_experience(ok=True, hotspot="hotspot.k"), log)
                with self.assertRaises(ce.KillSwitchActive):
                    ce.write_distillate({"kind": "x"}, "never-written.json")
                env = dict(os.environ, CAM_EXPERIENCE_LOG=str(log))
                proc = subprocess.run([sys.executable, str(CLI), "--record", "--ok", "--hotspot", "hotspot.k"], capture_output=True, text=True, env=env)
                self.assertEqual(proc.returncode, 3)
                self.assertEqual(json.loads(proc.stdout)["error"], "kill_switch_active")
                # reading stays allowed under kill
                proc = subprocess.run([sys.executable, str(CLI), "--offline", "--hotspot", "hotspot.coding"], capture_output=True, text=True, env=env)
                self.assertEqual(proc.returncode, 0)
            finally:
                if old is None:
                    del os.environ["CAM_KILL"]
                else:
                    os.environ["CAM_KILL"] = old
            self.assertFalse(log.exists())
            self.assertFalse((ce.DISTILL_DIR / "never-written.json").exists())

    def test_schema_version_stamped(self) -> None:
        self.assertEqual(ce.make_experience(ok=True)["schema"], ce.SCHEMA_VERSION)


class EthicsTests(unittest.TestCase):
    def test_redaction_on_record(self) -> None:
        fake_key = "ghp_" + "A" * 28  # assembled at runtime so no secret-shaped literal lands in git
        exp = ce.make_experience(ok=True, hotspot="hotspot.h", notes=f"mail aaron@example.com, call +1 555 010 9999, key {fake_key}")
        self.assertNotIn("@", exp["notes"])
        self.assertNotIn("ghp_", exp["notes"])
        self.assertNotIn("9999", exp["notes"])
        self.assertEqual(exp["redacted"], ["email", "phone", "token"])
        clean = ce.make_experience(ok=True, hotspot="hotspot.h", notes="loop ran fine, 3/3 checks green in 12s")
        self.assertNotIn("redacted", clean)
        self.assertEqual(clean["notes"], "loop ran fine, 3/3 checks green in 12s")

    def test_protected_context_requires_human_judgment(self) -> None:
        m = ce.ExperiencePredictor()
        for e in stream([("hotspot.careers_submit", False)] * 6):
            m.update(e)
        r = m.predict({"hotspot": "hotspot.careers_submit", "motors": ["motor.jobs"]}, now=T0 + timedelta(days=2))
        self.assertTrue(r["protected_context"])
        self.assertEqual(r["advice"]["stance"], "human_judgment_required")
        self.assertFalse(r["advice"]["suggest_qa_hold"])  # low p would normally suggest a hold
        self.assertIn("call is yours", r["narration"])
        plain = m.predict({"hotspot": "hotspot.coding"}, now=T0)
        self.assertFalse(plain["protected_context"])
        self.assertTrue(ce.is_protected({"hotspot": "hotspot.x", "motors": ["motor.outbound"]}))

    def test_abstains_on_thin_evidence(self) -> None:
        m = ce.ExperiencePredictor()
        for e in stream([("hotspot.a", True)] * 30):
            m.update(e)
        thin = m.predict({"hotspot": "hotspot.b", "sense": "sense.chat.aaron"}, now=T0 + timedelta(days=8))
        self.assertTrue(thin["advice"]["abstain"])
        self.assertEqual(thin["advice"]["stance"], "abstain")
        self.assertIn("don't know", thin["narration"])
        rich = m.predict({"hotspot": "hotspot.a", "sense": "sense.chat.aaron"}, now=T0 + timedelta(days=8))
        self.assertFalse(rich["advice"]["abstain"])
        self.assertIn("%", rich["narration"])
        self.assertIn("between", rich["narration"])  # the range travels with the number

    def test_prediction_card_fields_and_limitations(self) -> None:
        m = ce.ExperiencePredictor()
        r = m.predict({"hotspot": "hotspot.h"})
        for field in ("p_success", "credible_interval", "n_effective", "evidence_level", "evidence", "advice", "limitations", "narration"):
            self.assertIn(field, r)
        self.assertTrue(r["limitations"])
        self.assertEqual(r["advice"]["stance"], "no_experience_yet")
        self.assertIn("won't give you a number", r["narration"])

    def test_calibration_parity_flags_overconfident_group(self) -> None:
        good = [(0.9, 1.0)] * 9 + [(0.1, 0.0)] * 9
        bad = [(0.95, 0.0)] * 10  # confidently wrong
        agg = ce.calibration_metrics(good + bad)["ece"]
        par = ce.calibration_parity({"hotspot.good": good, "hotspot.bad": bad, "hotspot.tiny": [(0.5, 1.0)]}, agg, 10)
        self.assertEqual(par["flagged"], ["hotspot.bad"])
        self.assertEqual({g["group"] for g in par["groups"]}, {"hotspot.good", "hotspot.bad"})  # tiny group skipped

    def test_prequential_reports_abstention_and_parity(self) -> None:
        exps, _ = ce.load_experiences(offline=True)
        met = ce.prequential(exps, ce.load_config())["metrics"]
        self.assertTrue(0.0 <= met["abstention_rate"] <= 1.0)
        self.assertIn("groups", met["parity"])
        self.assertGreaterEqual(len(met["parity"]["groups"]), 3)

    def test_forget_by_ref_and_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "exp.jsonl"
            ce.record_experience(ce.make_experience(ok=True, hotspot="hotspot.keep", ref="run-1"), log)
            ce.record_experience(ce.make_experience(ok=True, hotspot="hotspot.drop", ref="run-2"), log)
            ce.record_experience(ce.make_experience(ok=False, hotspot="hotspot.keep", ref="run-3-secret"), log)
            self.assertEqual(ce.forget_experiences(key="hotspot:hotspot.drop", path=log), 1)
            self.assertEqual(ce.forget_experiences(ref_contains="secret", path=log), 1)
            left = ce.read_jsonl(log)
            self.assertEqual([e["ref"] for e in left], ["run-1"])
            env = dict(os.environ, CAM_EXPERIENCE_LOG=str(log))
            proc = subprocess.run([sys.executable, str(CLI), "--forget-ref", "run-1"], capture_output=True, text=True, env=env)
            self.assertEqual(json.loads(proc.stdout)["forgotten"], 1)
            self.assertEqual(ce.read_jsonl(log), [])

    def test_narrate_cli(self) -> None:
        out = subprocess.check_output([sys.executable, str(CLI), "--offline", "--no-write", "--narrate", "--hotspot", "hotspot.loop_engineering", "--pattern", "daily-triage", "--sense", "sense.loop.tick"], text=True)
        self.assertIn("%", out)
        self.assertNotIn("{", out)

    def test_ethics_gate_passes(self) -> None:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "research-ethics-check.py")], capture_output=True, text=True)
        doc = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, doc.get("errors"))
        self.assertTrue(doc["ok"])

    def test_redaction_labels_specific_kind_first(self) -> None:
        # phone is the generic shape; ssn must win the label (found by the 3B fuzz)
        _clean, kinds = ce.redact("ssn 519-83-2477 on file")
        self.assertEqual(kinds, ["ssn"])


class FuzzHarnessTests(unittest.TestCase):
    def test_beta_quantile_tail_accuracy(self) -> None:
        # bracketed Newton must invert the cdf to 1e-10 in q across the predictor's domain
        for q, a, b in ((0.05, 0.5, 300.0), (0.95, 300.0, 0.5), (0.5, 0.5, 0.5), (0.9, 35.0, 0.5), (0.02, 1.0, 1.0)):
            x = ce.beta_quantile(q, a, b)
            self.assertLess(abs(ce.beta_cdf(x, a, b) - q), 1e-9, (q, a, b, x))

    def test_resolve_scale_honours_explicit_physical_below_threshold(self) -> None:
        import trillion_scale as ts

        self.assertEqual(ts.resolve_scale(10**6), (10**6, 0, "literal_loop"))
        self.assertEqual(ts.resolve_scale(3 * 10**9, 2 * 10**8), (2 * 10**8, 28 * 10**8, "physical_capped_scaled"))
        self.assertEqual(ts.resolve_scale(3 * 10**9, 5 * 10**9), (3 * 10**9, 0, "literal_loop"))
        self.assertEqual(ts.resolve_scale(3 * 10**12, 10**7)[2], "modular_period_scaled")

    def test_predictive_fuzz_shakedown(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "predictive-cortex-billion-fuzz.py"), "--n", "6000", "--workers", "1", "--seed", "3"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout[-800:])
        txt = proc.stdout
        doc = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        self.assertTrue(doc["ok"])
        self.assertEqual(doc["failed"], 0)
        self.assertGreaterEqual(doc["full_samples"], 1)


if __name__ == "__main__":
    unittest.main()
