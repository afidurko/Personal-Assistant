#!/usr/bin/env python3
"""Unit tests for Higgsfield Cam wiring (dry-run / pack / gate)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "scripts" / "higgsfield-run.py"
PACK = ROOT / "scripts" / "pack-higgsfield-result.py"
CHECK = ROOT / "scripts" / "higgsfield-check.py"
SAMPLE = ROOT / "scripts" / "testdata" / "sample-higgsfield-experiment.py"


class HiggsfieldTests(unittest.TestCase):
    def test_check(self) -> None:
        out = subprocess.check_output([sys.executable, str(CHECK)], text=True)
        payload = json.loads(out)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("integration"), "higgsfield")

    def test_dry_run_sample(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(RUN), "--experiment", str(SAMPLE.relative_to(ROOT))],
            text=True,
            cwd=str(ROOT),
        )
        payload = json.loads(out)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "dry_run")
        self.assertFalse(payload.get("spend", {}).get("ssh"))
        names = [e["experiment"] for e in payload.get("experiments") or []]
        self.assertIn("cam_alpaca_smoke", names)
        self.assertEqual(payload.get("litserve_handoff", {}).get("target"), "integrations/litserve")

    def test_doctor(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(RUN), "--doctor"], text=True, cwd=str(ROOT)
        )
        payload = json.loads(out)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "dry_run")

    def test_live_refused_without_env(self) -> None:
        env = {**os.environ}
        env.pop("CAM_HIGGSFIELD_LIVE", None)
        proc = subprocess.run(
            [
                sys.executable,
                str(RUN),
                "--experiment",
                str(SAMPLE.relative_to(ROOT)),
                "--enhance",
                "--live",
            ],
            text=True,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload.get("ok"))
        self.assertFalse(payload.get("live_allowed"))

    def test_live_intent_when_armed(self) -> None:
        env = {**os.environ, "CAM_HIGGSFIELD_LIVE": "1"}
        out = subprocess.check_output(
            [
                sys.executable,
                str(RUN),
                "--experiment",
                str(SAMPLE.relative_to(ROOT)),
                "--enhance",
                "--live",
            ],
            text=True,
            cwd=str(ROOT),
            env=env,
        )
        payload = json.loads(out)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("mode"), "live_intent")
        self.assertFalse(payload.get("spend", {}).get("remote_exec"))

    def test_pack(self) -> None:
        plan = subprocess.check_output(
            [sys.executable, str(RUN), "--doctor"], text=True, cwd=str(ROOT)
        )
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "plan.json"
            dst = Path(td) / "mesh.json"
            src.write_text(plan, encoding="utf-8")
            subprocess.check_call(
                [
                    sys.executable,
                    str(PACK),
                    "--results",
                    str(src),
                    "--goal",
                    "smoke",
                    "--out",
                    str(dst),
                ]
            )
            doc = json.loads(dst.read_text(encoding="utf-8"))
            self.assertEqual(doc.get("namespace"), "mesh/runs")
            self.assertEqual(doc.get("kind"), "higgsfield_train_plan")
            self.assertEqual(doc.get("primary_experiment"), "cam_alpaca_smoke")
            self.assertIn("litserve_handoff", doc)


if __name__ == "__main__":
    unittest.main()
