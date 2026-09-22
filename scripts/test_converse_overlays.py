#!/usr/bin/env python3
"""Units for converse overlays config + in-process catalog helpers."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))
import activity_emit  # noqa: E402
import cam_inproc  # noqa: E402
import converse_overlays as co  # noqa: E402


class ConverseOverlayTests(unittest.TestCase):
    def test_check_passes(self) -> None:
        report = co.check_overlays()
        self.assertTrue(report["ok"], report.get("errors"))

    def test_see_me_is_camera(self) -> None:
        hit = co.match_overlay("can you see me")
        self.assertEqual(hit["id"], "camera")
        reply = co.speak_from_trace(
            "can you see me", {"classification": {"intents": ["general"]}, "path": "fast"}
        )
        self.assertIn("Camera", reply)

    def test_pupil_line(self) -> None:
        reply = co.speak_from_trace(
            "what do you see on pupil",
            {"classification": {"intents": ["general"]}, "path": "fast"},
        )
        self.assertIn("Pupil", reply)

    def test_greeting_intent(self) -> None:
        reply = co.speak_from_trace(
            "hi cam",
            {"classification": {"intents": ["greeting"]}, "path": "fast"},
        )
        self.assertIn("Aaron", reply)

    def test_empty(self) -> None:
        reply = co.speak_from_trace("", {})
        self.assertIn("Aaron", reply)

    def test_server_delegates(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "cam_converse_server", ROOT / "scripts" / "cam-converse-server.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(
            mod.speak_from_trace("thanks", {"classification": {"intents": ["ack"]}}),
            "Of course. I'm right here.",
        )


class CatalogInprocTests(unittest.TestCase):
    def test_public_apis_offline(self) -> None:
        hit = cam_inproc.public_apis_search(query="weather", offline=True, num=3)
        self.assertTrue(hit.get("offline"))
        self.assertGreaterEqual(hit.get("returned", 0), 1)
        self.assertEqual(hit.get("sense"), "sense.catalog.public_apis")

    def test_google_trends_offline(self) -> None:
        hit = cam_inproc.google_trends_search(query="election", offline=True, num=3)
        self.assertTrue(hit.get("offline"))
        self.assertGreaterEqual(hit.get("returned", 0), 1)

    def test_catalog_sense_smoke(self) -> None:
        smoke = cam_inproc.catalog_sense_smoke()
        self.assertIn("motor.public_apis", (smoke["route"].get("motor_plan") or []))


class DualStreamCacheTests(unittest.TestCase):
    def test_invalidate_reloads(self) -> None:
        first = activity_emit.dual_stream("speak")
        self.assertEqual(first.get("winner"), "dorsal")
        activity_emit.invalidate_dual_stream_cache()
        self.assertIsNone(activity_emit._DUAL_CACHE)
        again = activity_emit.dual_stream("speak")
        self.assertEqual(again.get("winner"), "dorsal")
        self.assertIsNotNone(activity_emit._DUAL_CACHE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
