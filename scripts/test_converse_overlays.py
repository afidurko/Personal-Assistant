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

    def test_words_matcher_is_whole_word(self) -> None:
        self.assertEqual(co.match_overlay("spin the cortex")["id"], "cortex")
        self.assertEqual(co.match_overlay("what tasks are running")["id"], "agents")
        # "mesh" only as a whole word — "meshuggah" must not light the cortex
        self.assertIsNone(co.match_overlay("play some meshuggah"))

    def test_classify_intents_matches_cam_reason(self) -> None:
        import cam_reason as cr

        cfg = co.load_overlays()
        for intent, probe in (cfg.get("intent_probes") or {}).items():
            self.assertIn(intent, co.classify_intents(probe, cfg), probe)
            self.assertIn(intent, cr.classify_intent(probe)["intents"], probe)
        self.assertEqual(co.classify_intents("implement a refactor", cfg), [])

    def test_explain_reply_kinds(self) -> None:
        fast = {"classification": {"intents": ["general"]}, "path": "fast"}
        self.assertEqual(co.explain_reply("", {})["kind"], "empty")
        cam = co.explain_reply("can you see me", fast)
        self.assertEqual((cam["kind"], cam["id"]), ("overlay", "camera"))
        hi = co.explain_reply("hi cam", {"classification": {"intents": ["greeting"]}})
        self.assertEqual((hi["kind"], hi["id"]), ("intent", "greeting"))
        # No classification in the trace → config intent rules take over
        hi2 = co.explain_reply("hi cam", {})
        self.assertEqual(hi2["id"], "greeting")
        slow = co.explain_reply(
            "implement a refactor",
            {"path": "slow", "hotspot_id": "hotspot.coding", "motor_plan": ["motor.cline"]},
        )
        self.assertEqual((slow["kind"], slow["id"]), ("slow_plan", "hotspot.coding"))
        self.assertEqual(co.explain_reply("ping", fast)["kind"], "echo")

    def test_echo_repeat_from_both_history_shapes(self) -> None:
        fast = {"classification": {"intents": ["general"]}, "path": "fast"}
        py_hist = [{"aaron": "Ping", "cam": "x"}]
        ts_hist = [{"role": "aaron", "text": "ping"}, {"role": "cam", "text": "y"}]
        a = co.explain_reply("ping", fast, py_hist)
        b = co.explain_reply("ping", fast, ts_hist)
        self.assertEqual(a["kind"], "echo_repeat")
        self.assertEqual(a["text"], b["text"])
        self.assertIn("ping", a["text"])
        # A different previous line is a plain echo again
        self.assertEqual(co.explain_reply("ping", fast, [{"aaron": "pong"}])["kind"], "echo")

    def test_speak_params(self) -> None:
        speak = co.speak_params()
        self.assertEqual(speak["lang"], "en-US")
        self.assertAlmostEqual(speak["rate"], 0.95)
        self.assertAlmostEqual(speak["pitch"], 1.05)

    def test_parity_corpus_covers_every_branch(self) -> None:
        kinds = {co.run_parity_case(c)["kind"] for c in co.parity_corpus()}
        self.assertEqual(
            kinds, {"empty", "overlay", "intent", "slow_plan", "echo", "echo_repeat"}
        )

    def test_parity_across_mirrors(self) -> None:
        import importlib.util
        import shutil

        spec = importlib.util.spec_from_file_location(
            "converse_parity_check", ROOT / "scripts" / "converse-parity-check.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        report = mod.run_parity()
        self.assertTrue(report["ok"], report.get("mismatches") or report.get("skipped"))
        if shutil.which("node"):
            self.assertEqual(report["mirrors"], ["python", "ts", "js"])
            self.assertEqual(report["mismatches"], [])

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
        status = mod.converse_overlays_status()
        self.assertTrue(status["ok"], status["check"])
        self.assertEqual(status["host"], "python")
        self.assertIn("camera", status["overlay_ids"])
        decided = mod.converse_turn("can you see me")
        self.assertEqual(decided["overlay"], {"kind": "overlay", "id": "camera"})
        self.assertEqual(decided["speak"]["lang"], "en-US")


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
