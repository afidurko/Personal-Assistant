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


if __name__ == "__main__":
    unittest.main()
