"""Tests for IP-safe embodiment resolve (detect → archetype → procedural mesh)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.embodiment_catalog import ARCHETYPES  # noqa: E402
from app.services.embodiment_service import (  # noqa: E402
    classify_sport,
    embodiment_service,
)


class EmbodimentServiceTests(unittest.TestCase):
    def test_catalog_has_original_archetypes_only(self):
        self.assertIn("diamond_arc", ARCHETYPES)
        self.assertIn("neutral_echo", ARCHETYPES)
        for archetype in ARCHETYPES.values():
            self.assertTrue(archetype.id)
            self.assertTrue(archetype.mesh_defaults.primary_hex.startswith("#"))
            # No external asset paths — procedural recipes only
            dumped = archetype.model_dump()
            blob = str(dumped).lower()
            for banned in ("pokemon", "nintendo", "glb", "gltf", "fbx", "obj/", "http://", "https://"):
                self.assertNotIn(banned, blob)

    def test_classify_baseball_from_set_cues(self):
        self.assertEqual(
            classify_sport({"set_name": "Topps Chrome", "player_name": "Alex Rivera"}),
            "diamond_arc",
        )

    def test_classify_basketball_from_sport_field(self):
        self.assertEqual(
            classify_sport({"sport": "Basketball", "player_name": "Jordan Lee"}),
            "court_pulse",
        )

    def test_resolve_requires_player_name(self):
        self.assertIsNone(embodiment_service.resolve({"set_name": "Topps"}))

    def test_resolve_emits_procedural_spawn_payload(self):
        emb = embodiment_service.resolve(
            {
                "player_name": "Alex Rivera",
                "year": "2019",
                "set_name": "Topps Chrome",
                "card_number": "101",
                "grade": "PSA 10",
                "rookie": True,
                "sport": "Baseball",
            },
            confidence=0.91,
        )
        self.assertIsNotNone(emb)
        assert emb is not None
        self.assertEqual(emb.display_name, "Alex Rivera")
        self.assertEqual(emb.archetype_id, "diamond_arc")
        self.assertTrue(emb.entity_id.startswith("embody.diamond_arc."))
        self.assertIn("lane_dash", emb.actions)
        self.assertIn("idle", emb.anim_map)
        self.assertEqual(emb.source, "joshinator-original-catalog")
        self.assertIn("No third-party character IP", emb.license_note)
        self.assertGreaterEqual(emb.hp["max"], emb.hp["current"])
        self.assertGreaterEqual(emb.hp["max"], 60)
        self.assertRegex(emb.mesh.primary_hex, r"^#[0-9A-F]{6}$")

    def test_stable_colors_for_same_card(self):
        card = {
            "player_name": "Casey Quinn",
            "year": "2020",
            "set_name": "Prizm",
            "sport": "Basketball",
            "grade": "PSA 9",
        }
        a = embodiment_service.resolve(card)
        b = embodiment_service.resolve(card)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        assert a is not None and b is not None
        self.assertEqual(a.mesh.primary_hex, b.mesh.primary_hex)
        self.assertEqual(a.entity_id, b.entity_id)
        self.assertEqual(a.archetype_id, "court_pulse")

    def test_unknown_sport_falls_back_to_neutral(self):
        emb = embodiment_service.resolve(
            {"player_name": "Mystery Athlete", "set_name": "Custom Proto Set"}
        )
        self.assertIsNotNone(emb)
        assert emb is not None
        self.assertEqual(emb.archetype_id, "neutral_echo")


if __name__ == "__main__":
    unittest.main()
