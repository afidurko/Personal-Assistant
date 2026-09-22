#!/usr/bin/env python3
"""Unit tests for the Cam cortex (live thinking loop)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_cortex  # noqa: E402


def fake_status(
    healthy: int = 18,
    warning: int = 3,
    behind: int = 0,
    out_of_sync: int = 2,
    suggestions: int = 2,
) -> dict:
    pieces = [
        {"id": f"piece.h{i}", "status": "healthy"} for i in range(healthy)
    ] + [{"id": f"piece.w{i}", "status": "warning"} for i in range(warning)]
    items = [
        {
            "kind": "suggestion",
            "severity": "high",
            "title": f"Aaron suggestion: idea {i}",
            "suggestion": "triage",
        }
        for i in range(suggestions)
    ] + [
        {
            "kind": "connectivity",
            "severity": "medium",
            "title": "Connect coding workspace: cline",
            "detail": "npm egress blocked",
            "suggestion": "git submodule update --init integrations/cline",
        }
    ]
    return {
        "at": "2026-09-22T00:00:00Z",
        "system": {"ok": True, "data": {"overall": "WARNING", "pieces": pieces}},
        "build_plan": {"ok": True, "data": {"ok": True, "warnings": []}},
        "avatar": {"ok": True, "data": {"ok": True, "models_cached": []}},
        "auto_sync": {
            "ok": True,
            "data": {
                "home": {
                    "branch": "main",
                    "fetched": True,
                    "ahead": 0,
                    "behind": behind,
                },
                "submodules": [{"path": f"integrations/x{i}", "state": "uninitialized"} for i in range(out_of_sync)],
                "registry": {},
            },
        },
        "needs_attention": {"ok": False, "data": {"attention_items": items}},
    }


class CortexTests(unittest.TestCase):
    def test_facts_extraction(self) -> None:
        f = cam_cortex.extract_facts(fake_status())
        self.assertEqual(f["pieces_healthy"], 18)
        self.assertEqual(f["pieces_warning"], 3)
        self.assertEqual(f["submodules_out_of_sync"], 2)
        self.assertEqual(f["suggestions_queued"], 2)
        self.assertTrue(f["egress_blocked"])

    def test_health_bounds(self) -> None:
        hi = cam_cortex.health_score(
            cam_cortex.extract_facts(fake_status(healthy=21, warning=0, out_of_sync=0, suggestions=0))
        )
        lo = cam_cortex.health_score(
            cam_cortex.extract_facts(
                fake_status(healthy=0, warning=0, out_of_sync=9, suggestions=9)
            )
        )
        self.assertGreater(hi, lo)
        for v in (hi, lo):
            self.assertGreaterEqual(v, 5)
            self.assertLessEqual(v, 100)

    def test_tick_produces_full_cycle(self) -> None:
        cx = cam_cortex.Cortex()
        state = cx.tick(fake_status())
        stages = {t["stage"] for t in state["thoughts"]}
        self.assertLessEqual({"observe", "predict", "act"}, stages)
        self.assertTrue(state["predictions"])
        for p in state["predictions"]:
            self.assertGreaterEqual(p["probability"], 0.0)
            self.assertLessEqual(p["probability"], 1.0)
            self.assertIn("horizon", p)
            self.assertIn("evidence", p)
            self.assertIn("check", p)
        self.assertTrue(state["actions"])
        self.assertEqual(state["actions"][0]["rank"], 1)
        self.assertIn("priority", state["focus"])

    def test_reflection_scores_predictions(self) -> None:
        cx = cam_cortex.Cortex()
        cx.tick(fake_status(out_of_sync=2))
        state = cx.tick(fake_status(out_of_sync=2))  # drift persisted → held
        m = state["metrics"]
        self.assertIsNotNone(m["prediction_accuracy"])
        self.assertGreater(m["predictions_scored"], 0)
        stages = [t["stage"] for t in state["thoughts"]]
        self.assertIn("reflect", stages)

    def test_prediction_failure_detected(self) -> None:
        cx = cam_cortex.Cortex()
        cx.tick(fake_status(behind=3))  # predicts behind >= 1 persists
        cx.tick(fake_status(behind=0))  # drift cleared → that prediction fails
        self.assertGreater(cx.accuracy["failed"], 0)

    def test_focus_prefers_aaron_suggestions(self) -> None:
        cx = cam_cortex.Cortex()
        state = cx.tick(fake_status(suggestions=2))
        self.assertIn("P3", state["focus"]["priority"])

    def test_observe_names_actual_entities(self) -> None:
        cx = cam_cortex.Cortex()
        state = cx.tick(fake_status(warning=2, out_of_sync=2))
        blob = " ".join(t["text"] for t in state["thoughts"])
        self.assertIn("piece.w0", blob)          # actual warning piece named
        self.assertIn("integrations/x0", blob)   # actual drifting repo named
        f = state["facts"]
        self.assertEqual(f["warning_pieces"], ["piece.w0", "piece.w1"])
        self.assertEqual(f["out_of_sync_names"], ["integrations/x0", "integrations/x1"])

    def test_analyze_reports_real_deltas(self) -> None:
        cx = cam_cortex.Cortex()
        cx.tick(fake_status(warning=3, out_of_sync=3))
        recovered = fake_status(warning=3, out_of_sync=1)
        recovered["system"]["data"]["pieces"][18]["status"] = "healthy"  # piece.w0
        state = cx.tick(recovered)
        analyze = [t["text"] for t in state["thoughts"] if t["stage"] == "analyze"]
        blob = " ".join(analyze)
        self.assertTrue(analyze)
        self.assertIn("piece.w0: warning→healthy", blob)
        self.assertIn("repos drifting 3→1", blob)

    def test_analyze_steady_state(self) -> None:
        cx = cam_cortex.Cortex()
        cx.tick(fake_status())
        state = cx.tick(fake_status())
        analyze = [t["text"] for t in state["thoughts"] if t["stage"] == "analyze"]
        self.assertIn("no state change", analyze[-1])

    def test_activity_maps_thoughts_to_anatomy(self) -> None:
        cx = cam_cortex.Cortex()
        cx.tick(fake_status())
        feed = cx.activity()
        self.assertEqual(feed["source"], "cam_cortex")
        self.assertTrue(feed["firing"])
        areas = set(feed["active_areas"])
        # observe→visual/wernicke, predict→dlpfc, act→motor must be firing
        self.assertIn("area.visual", areas)
        self.assertIn("area.dlpfc", areas)
        self.assertIn("area.motor", areas)
        for f in feed["firing"]:
            self.assertGreaterEqual(f["intensity"], 0.3)
            self.assertLessEqual(f["intensity"], 1.0)
            self.assertTrue(f["reason"])
            self.assertTrue(f["tracts"])
            self.assertTrue(f["neuron"].startswith("neuron."))

    def test_speech_note_fires_broca(self) -> None:
        cx = cam_cortex.Cortex()
        cx.tick(fake_status())
        cx.note_speech("Hello Aaron")
        feed = cx.activity()
        self.assertIn("area.broca", feed["active_areas"])
        reasons = [f["reason"] for f in feed["firing"] if f["area"] == "area.broca"]
        self.assertTrue(any("Hello Aaron" in r for r in reasons))

    def test_input_note_fires_wernicke(self) -> None:
        cx = cam_cortex.Cortex()
        cx.note_input("build the jarvis bridge")
        feed = cx.activity()
        self.assertIn("area.wernicke", feed["active_areas"])

    def test_thoughts_since(self) -> None:
        cx = cam_cortex.Cortex()
        cx.tick(fake_status())
        seq = cx.state()["thoughts"][-1]["seq"]
        self.assertEqual(cx.thoughts_since(seq), [])
        cx.tick(fake_status())
        self.assertTrue(cx.thoughts_since(seq))


if __name__ == "__main__":
    unittest.main()
