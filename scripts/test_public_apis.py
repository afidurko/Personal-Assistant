#!/usr/bin/env python3
"""Unit tests for public-apis catalog parser/search."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEARCH = ROOT / "scripts" / "public-apis-search.py"
PACK = ROOT / "scripts" / "pack-public-apis-result.py"


class PublicApisSearchTests(unittest.TestCase):
    def test_offline_weather_search(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(SEARCH), "--query", "weather", "--offline", "--num", "5"],
            text=True,
        )
        payload = json.loads(out)
        self.assertTrue(payload.get("offline"))
        self.assertGreaterEqual(payload.get("returned", 0), 1)
        names = " ".join(r.get("name", "") for r in payload["results"]).lower()
        self.assertIn("meteo", names + " weather")

    def test_list_categories_offline(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(SEARCH), "--list-categories", "--offline"],
            text=True,
        )
        payload = json.loads(out)
        self.assertIn("Animals", payload.get("categories") or [])
        self.assertIn("Weather", payload.get("categories") or [])

    def test_category_filter(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(SEARCH), "--category", "Animals", "--offline", "--num", "10"],
            text=True,
        )
        payload = json.loads(out)
        self.assertGreaterEqual(payload.get("returned", 0), 1)
        for r in payload["results"]:
            self.assertIn("animal", r.get("category", "").lower())

    def test_doctor(self) -> None:
        out = subprocess.check_output(
            [sys.executable, str(SEARCH), "--doctor"],
            text=True,
        )
        payload = json.loads(out)
        self.assertTrue(payload.get("ok"))

    def test_pack(self) -> None:
        search = subprocess.check_output(
            [sys.executable, str(SEARCH), "--query", "cat", "--offline", "--num", "2"],
            text=True,
        )
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "results.json"
            dst = Path(td) / "mesh.json"
            src.write_text(search, encoding="utf-8")
            subprocess.check_call(
                [sys.executable, str(PACK), "--results", str(src), "--out", str(dst)]
            )
            doc = json.loads(dst.read_text(encoding="utf-8"))
            self.assertEqual(doc.get("namespace"), "mesh/tools")
            self.assertEqual(doc.get("kind"), "public_apis_catalog_hit")
            self.assertGreaterEqual(len(doc.get("apis") or []), 1)


if __name__ == "__main__":
    unittest.main()
