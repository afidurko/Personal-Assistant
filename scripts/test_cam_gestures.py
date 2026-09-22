#!/usr/bin/env python3
"""Unit tests for Cam hand gestures — vocabulary, resolver grammar, Aaron-only memory."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_gestures as cg  # noqa: E402


def segs(*specs: str, gap_ms: int = 50) -> list[cg.Segment]:
    t = 0
    out = []
    for s in specs:
        seg = cg.Segment.parse(s, t_ms=t)
        out.append(seg)
        t = seg.end_ms + gap_ms
    return out


def actions(intents: list[cg.Intent]) -> list[str]:
    return [i.action for i in intents]


class VocabularyTests(unittest.TestCase):
    def test_database_is_sound(self) -> None:
        self.assertEqual(cg.validate(), [])

    def test_aaron_use_cases_present(self) -> None:
        bound = {g["action"] for g in cg.load_vocabulary()["gestures"]}
        for must in ("ui.collapse", "ui.expand", "device.handoff_grab", "device.handoff_release"):
            self.assertIn(must, bound)

    def test_huawei_parity_documented(self) -> None:
        huawei = [g for g in cg.load_vocabulary()["gestures"] if g["source"] == "huawei"]
        self.assertGreaterEqual(len(huawei), 6)
        self.assertTrue(all(g.get("huawei_equivalent") for g in huawei))

    def test_no_gesture_binds_high_risk_action(self) -> None:
        acts = {a["id"]: a for a in cg.load_actions()["actions"]}
        for g in cg.load_vocabulary()["gestures"]:
            self.assertIn(acts[g["action"]]["sentinel_class"], ("read", "write_local"))

    def test_validate_catches_bad_action(self) -> None:
        vocab = cg.load_vocabulary()
        vocab["gestures"][0]["action"] = "motor.text"
        self.assertTrue(any(e.startswith("gesture_unknown_action") for e in cg.validate(vocab)))

    def test_validate_catches_ambiguous_binding(self) -> None:
        vocab = cg.load_vocabulary()
        dup = dict(vocab["gestures"][1], id="gesture.dup")
        vocab["gestures"].append(dup)
        self.assertTrue(any(e.startswith("ambiguous_binding") for e in cg.validate(vocab)))


class ResolverGrammarTests(unittest.TestCase):
    def test_grab_and_let_go_collapses(self) -> None:
        r = cg.GestureResolver(context="home")
        got = actions(r.feed_many(segs("open_palm:hold:300", "closed_fist:hold:200", "open_palm:hold:150")))
        self.assertEqual(got, ["system.engage", "ui.collapse"])

    def test_fist_burst_expands(self) -> None:
        r = cg.GestureResolver(context="reading")
        self.assertEqual(actions(r.feed_many(segs("closed_fist:hold:300", "open_palm:push_in:300"))), ["ui.expand"])

    def test_grab_held_is_screenshot_for_aaron(self) -> None:
        r = cg.GestureResolver(context="home", identity_ok=True)
        got = r.feed_many(segs("open_palm:hold:300", "closed_fist:hold:1300"))
        self.assertEqual(actions(got), ["system.engage", "ui.screenshot"])

    def test_grab_held_without_aaron_is_logged(self) -> None:
        r = cg.GestureResolver(context="home", identity_ok=False)
        got = r.feed_many(segs("open_palm:hold:300", "closed_fist:hold:1300"))
        self.assertEqual(actions(got), ["system.engage", "system.log_only"])
        self.assertFalse(got[1].fired)
        self.assertEqual(got[1].requested_action, "ui.screenshot")
        self.assertIn("aaron_identity_required", got[1].hold_reason)

    def test_handoff_iphone_to_ipad(self) -> None:
        r = cg.GestureResolver(context="home", identity_ok=True)
        grab = segs("open_palm:hold:300", "closed_fist:hold:200", "closed_fist:translate_out:400")
        for s in grab:
            s.device = "aaron-iphone"
        got = r.feed_many(grab)
        self.assertEqual(actions(got), ["system.engage", "device.handoff_grab"])
        self.assertEqual(r.context, "carrying")
        release = segs("closed_fist:hold:400", "open_palm:hold:250")
        for s in release:
            s.t_ms += grab[-1].end_ms + 2000
            s.device = "aaron-ipad"
        got = r.feed_many(release)
        self.assertEqual(actions(got), ["device.handoff_release"])
        self.assertEqual(got[0].device, "aaron-ipad")
        self.assertEqual(r.context, "home")

    def test_carry_times_out(self) -> None:
        r = cg.GestureResolver(context="home", identity_ok=True)
        r.feed_many(segs("open_palm:hold:300", "closed_fist:hold:200", "closed_fist:translate_out:400"))
        self.assertEqual(r.context, "carrying")
        late = cg.Segment("thumb_up", "hold", 600, t_ms=30_000)
        got = r.feed(late)
        self.assertEqual(actions(got)[0], "device.handoff_cancel")
        self.assertEqual(got[0].source, "timeout")
        self.assertEqual(r.context, "home")

    def test_wave_cancels_only_while_carrying(self) -> None:
        r = cg.GestureResolver(context="home", identity_ok=True)
        self.assertEqual(actions(r.feed_many(segs("open_palm:wave:800"))), ["converse.attention"])
        r.feed_many(segs("open_palm:hold:300", "closed_fist:hold:200", "closed_fist:translate_out:400"))
        wave = cg.Segment("open_palm", "wave", 800, t_ms=5000)
        self.assertEqual(actions(r.feed(wave)), ["device.handoff_cancel"])

    def test_context_changes_meaning_of_same_pose(self) -> None:
        self.assertEqual(actions(cg.GestureResolver(context="home").feed_many(segs("thumb_up:hold:600"))), ["converse.thanks"])
        self.assertEqual(
            actions(cg.GestureResolver(context="prompt", identity_ok=True).feed_many(segs("thumb_up:hold:600"))),
            ["converse.confirm"],
        )
        self.assertEqual(actions(cg.GestureResolver(context="speaking").feed_many(segs("open_palm:hold:1000"))), ["converse.stop"])
        got = cg.GestureResolver(context="choice").feed_many(segs("victory:hold:700"))
        self.assertEqual(actions(got), ["nav.choose_option"])
        self.assertEqual(got[0].action_params, {"n": 2})

    def test_flick_needs_engagement(self) -> None:
        r = cg.GestureResolver(context="reading")
        got = r.feed_many(segs("open_palm:flick_down:200"))
        self.assertEqual(actions(got), ["system.log_only"])
        self.assertIn("not engaged", got[0].hold_reason)
        r = cg.GestureResolver(context="reading")
        got = r.feed_many(segs("open_palm:hold:400", "open_palm:flick_down:200"))
        self.assertEqual(actions(got), ["system.engage", "ui.scroll_up"])

    def test_switch_hold_logs_everything(self) -> None:
        r = cg.GestureResolver(context="home", identity_ok=True, switch_act=False)
        got = r.feed_many(segs("open_palm:hold:300", "closed_fist:hold:200", "open_palm:hold:150"))
        self.assertTrue(all(i.action == "system.log_only" and not i.fired for i in got))
        self.assertEqual([i.requested_action for i in got], ["system.engage", "ui.collapse"])

    def test_two_hands_hold_all(self) -> None:
        r = cg.GestureResolver(context="home", identity_ok=True)
        self.assertEqual(actions(r.feed_many(segs("open_palm:hold:1200:0.95:2"))), ["presence.hold_all"])

    def test_low_confidence_does_not_fire(self) -> None:
        r = cg.GestureResolver(context="home")
        self.assertEqual(r.feed_many(segs("thumb_down:hold:600:0.4")), [])

    def test_cooldown_holds_repeat(self) -> None:
        r = cg.GestureResolver(context="home")
        got = r.feed_many(segs("thumb_down:hold:600", "thumb_down:hold:600", gap_ms=10))
        self.assertEqual(actions(got), ["converse.reject", "system.log_only"])
        self.assertIn("cooldown", got[1].hold_reason)

    def test_pack_intent_has_no_frames(self) -> None:
        r = cg.GestureResolver(context="home")
        intent = r.feed_many(segs("thumb_down:hold:600"))[0]
        packed = cg.pack_intent(intent)
        self.assertEqual(packed["ns"], "mesh/gestures")
        self.assertEqual(packed["action"], "converse.reject")
        for forbidden in ("frame", "landmarks", "image"):
            self.assertNotIn(forbidden, packed)


class MemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "learned.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_only_aaron_may_teach(self) -> None:
        with self.assertRaises(PermissionError):
            cg.teach(name="x", meaning="m", action="ui.collapse", by="Cline", learned_path=self.path,
                     steps=[{"pose": "closed_fist", "motion": "raise", "min_ms": 300}])
        self.assertFalse(self.path.exists())

    def test_teach_refuses_conflict_without_replace(self) -> None:
        with self.assertRaises(ValueError):
            cg.teach(name="x", meaning="m", action="ui.collapse", by="Aaron", learned_path=self.path,
                     like="gesture.thumb_up_thanks", contexts=["*"])
        cg.teach(name="x", meaning="m", action="ui.collapse", by="Aaron", learned_path=self.path,
                 like="gesture.thumb_up_thanks", contexts=["*"], replace=True)
        learned = cg.load_learned(self.path)
        self.assertEqual(learned["bindings"][0]["replaced"], ["gesture.thumb_up_thanks"])

    def test_learned_binding_wins_and_is_remembered(self) -> None:
        cg.teach(name="fist pump", meaning="next song", action="nav.page_next", by="Aaron",
                 learned_path=self.path, contexts=["gallery"],
                 steps=[{"pose": "closed_fist", "motion": "raise", "min_ms": 300}])
        cg.teach(name="thumb means collapse", meaning="fold it", action="ui.collapse", by="Aaron",
                 learned_path=self.path, contexts=["reading"], like="gesture.thumb_up_thanks")
        learned = cg.load_learned(self.path)
        self.assertEqual(len(learned["bindings"]), 2)
        self.assertTrue(all(b["taught_by"] == "Aaron" for b in learned["bindings"]))

        got = cg.GestureResolver(context="gallery", learned=learned).feed_many(segs("closed_fist:raise:350"))
        self.assertEqual([(i.gesture, i.action, i.source) for i in got], [("learned.fist_pump", "nav.page_next", "learned")])
        got = cg.GestureResolver(context="reading", learned=learned).feed_many(segs("thumb_up:hold:600"))
        self.assertEqual(actions(got), ["ui.collapse"])
        got = cg.GestureResolver(context="home", learned=learned).feed_many(segs("thumb_up:hold:600"))
        self.assertEqual(actions(got), ["converse.thanks"])
        self.assertEqual(cg.validate(learned=learned), [])

    def test_forget_and_feedback(self) -> None:
        b = cg.teach(name="fist pump", meaning="next song", action="nav.page_next", by="Aaron",
                     learned_path=self.path, contexts=["gallery"],
                     steps=[{"pose": "closed_fist", "motion": "raise", "min_ms": 300}])
        for _ in range(20):
            cg.feedback(b["id"], confirmed=False, learned_path=self.path)
        self.assertEqual(cg.recalibration_flags(cg.load_learned(self.path)), [b["id"]])
        with self.assertRaises(PermissionError):
            cg.forget(b["id"], by="Cline", learned_path=self.path)
        cg.forget(b["id"], by="Aaron", learned_path=self.path)
        self.assertEqual(cg.load_learned(self.path)["bindings"], [])

    def test_teach_rejects_unknown_action_or_context(self) -> None:
        with self.assertRaises(ValueError):
            cg.teach(name="x", meaning="m", action="motor.text", by="Aaron", learned_path=self.path,
                     steps=[{"pose": "closed_fist", "motion": "raise", "min_ms": 300}])
        with self.assertRaises(ValueError):
            cg.teach(name="x", meaning="m", action="ui.collapse", by="Aaron", learned_path=self.path,
                     contexts=["kitchen"], steps=[{"pose": "closed_fist", "motion": "raise", "min_ms": 300}])


class ScriptTests(unittest.TestCase):
    def run_script(self, name: str, *argv: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / name), *argv],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )

    def test_gesture_check_passes(self) -> None:
        p = self.run_script("gesture-check.py", "--json")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        report = json.loads(p.stdout)
        self.assertTrue(report["ok"])
        self.assertTrue(all(d["ok"] for d in report["demos"]))

    def test_cli_resolve_json(self) -> None:
        p = self.run_script(
            "cam-gestures.py", "resolve", "--json", "--context", "home", "--identity", "--device", "aaron-iphone",
            "--segments", "open_palm:hold:300,closed_fist:hold:200,closed_fist:translate_out:400",
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        report = json.loads(p.stdout)
        self.assertEqual(report["context_out"], "carrying")
        self.assertEqual([i["action"] for i in report["intents"]], ["system.engage", "device.handoff_grab"])
        self.assertEqual(report["mesh"][1]["device"], "aaron-iphone")

    def test_route_holds_gesture_motor_while_switch_is_hold(self) -> None:
        p = self.run_script("connectome-route.py", "--sense", "sense.vision.gesture", "--goal", "collapse page")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        doc = json.loads(p.stdout)
        self.assertEqual(doc["hotspot_id"], "hotspot.gesture")
        self.assertEqual(doc["switch_state"]["switch.gesture_control"], "hold")
        self.assertNotIn("motor.gesture", doc["motor_plan"])
        self.assertIn("motor.mesh", doc["motor_plan"])


if __name__ == "__main__":
    unittest.main()
