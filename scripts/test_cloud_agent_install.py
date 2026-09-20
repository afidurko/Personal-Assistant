#!/usr/bin/env python3
"""Cloud Agent install script must exist, be executable, and terminate successfully."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts/cloud-agent-install.sh"
ENV_JSON = ROOT / ".cursor/environment.json"


class CloudAgentInstallTests(unittest.TestCase):
    def test_environment_json_points_at_install_script(self) -> None:
        cfg = json.loads(ENV_JSON.read_text(encoding="utf-8"))
        self.assertEqual(cfg.get("install"), "./scripts/cloud-agent-install.sh")
        self.assertNotIn("start", cfg)
        self.assertNotEqual(cfg.get("install"), "build")
        self.assertTrue(INSTALL.is_file())
        self.assertTrue(INSTALL.stat().st_mode & 0o111)

    def test_install_script_succeeds_twice(self) -> None:
        for _ in range(2):
            p = subprocess.run(
                [str(INSTALL)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("cam-system:", p.stdout)


if __name__ == "__main__":
    unittest.main()
