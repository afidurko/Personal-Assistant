#!/usr/bin/env python3
"""Pydantic-free embodiment catalog + catalog-only 3T fuzz."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOSH = ROOT / "integrations" / "joshinator-analyzer" / "backend"
sys.path.insert(0, str(JOSH))

from app.services.embodiment_lite import ARCHETYPE_LITE, SPORT_KEYWORDS  # noqa: E402

BANNED = ("pokemon", "pokémon", "nintendo", "pikachu", "charizard", ".glb", ".gltf", ".fbx")


class EmbodimentLiteTests(unittest.TestCase):
    def test_keywords_map_to_lite_archetypes(self) -> None:
        self.assertTrue(ARCHETYPE_LITE)
        for kid in SPORT_KEYWORDS:
            self.assertIn(kid, ARCHETYPE_LITE)
        self.assertIn("neutral_echo", ARCHETYPE_LITE)

    def test_lite_catalog_has_no_banned_ip(self) -> None:
        for arch in ARCHETYPE_LITE.values():
            blob = f"{arch.id} {arch.name} {arch.blurb}".lower()
            for banned in BANNED:
                self.assertNotIn(banned, blob)

    def test_fuzz_catalog_only_without_pydantic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fuzz.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "embodiment-billion-fuzz.py"),
                    "--n",
                    "10000",
                    "--physical",
                    "10000",
                    "--seed",
                    "7",
                    "--workers",
                    "1",
                    "--out",
                    str(out),
                ],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(report.get("ok"), report)
            self.assertEqual(report.get("failed"), 0)
            try:
                import pydantic  # noqa: F401
                self.assertTrue(report.get("full_resolve"))
            except ImportError:
                self.assertFalse(report.get("full_resolve"))
                self.assertIn("catalog_only", report.get("sampler") or "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
