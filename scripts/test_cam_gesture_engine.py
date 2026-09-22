#!/usr/bin/env python3
"""Unit tests for the merged hand-gesture engine — landmarks in, resolver intents out."""

from __future__ import annotations

import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_gesture_engine as ge  # noqa: E402
import cam_gestures as cg  # noqa: E402

SHARED = ge.GestureEngine()  # loads the Kazuhito00 CSV heads once for the whole module
REPO_MODELS = bool(SHARED.keypoint_knn and SHARED.keypoint_knn.ready)


def engine() -> ge.GestureEngine:
    return ge.GestureEngine(keypoint_knn=SHARED.keypoint_knn, history_knn=SHARED.history_knn,
                            prototypes=ge.PrototypeStore(Path(tempfile.mkdtemp()) / "protos.json"), load_repo_models=False)


def run(script: list[dict], *, context: str = "home", fps: int = 30, identity: bool = True, act: bool = True, **kw):
    sess = ge.GestureSession(engine=engine(), context=context, identity_ok=identity, switch_act=act)
    for obs in ge.synth_sequence(script, fps=fps, **kw):
        sess.feed(obs)
    sess.flush()
    return sess


def seg_ids(sess: ge.GestureSession) -> list[str]:
    return [f"{s.pose}:{s.motion}" for s in sess.segments]


def fired(sess: ge.GestureSession) -> list[str]:
    return [i.gesture for i in sess.intents if i.fired]


class PoseRuleTests(unittest.TestCase):
    POSES = ["open_palm", "back_of_hand", "closed_fist", "pointing_up", "thumb_up", "thumb_down", "victory",
             "three", "four", "i_love_you", "ok_sign", "pinch"]

    def test_every_rule_pose_both_hands(self) -> None:
        fusion = engine().pose_fusion
        for pose in self.POSES:
            for hand in ("Right", "Left"):
                h = ge.synth_hand(pose, handedness=hand, facing="back" if pose == "back_of_hand" else "palm", jitter=0.03)
                got, conf, _ = fusion.classify(h, 960, 540)
                self.assertEqual(got, pose, f"{pose}/{hand} -> {got}")
                self.assertGreaterEqual(conf, 0.7, f"{pose}/{hand} conf {conf}")

    def test_pointing_away_uses_depth(self) -> None:
        got, _, _ = engine().pose_fusion.classify(ge.synth_hand("pointing_away"), 960, 540)
        self.assertEqual(got, "pointing_away")

    def test_two_hand_l_shapes_are_take_picture(self) -> None:
        a = ge.synth_hand("take_picture", (0.43, 0.55), 0.09, "Left")
        b = ge.synth_hand("take_picture", (0.57, 0.55), 0.09, "Right")
        self.assertEqual(ge.TwoHandRuleHead().classify(a, b), ("take_picture", 0.8))

    def test_external_labels_join_the_vote(self) -> None:
        h = ge.synth_hand("pointing_up")
        h.labels = {"hagrid": ("mute", 0.9)}
        got, conf, detail = engine().pose_fusion.classify(h, 960, 540)
        # HaGRID 'mute' is the same family as the rule's pointing_up; the rule pose keeps the fine label.
        self.assertEqual(got, "pointing_up")
        self.assertGreaterEqual(conf, 0.8)
        h2 = ge.synth_hand("closed_fist")
        h2.labels = {"mediapipe": ("Closed_Fist", 0.95)}
        got2, conf2, _ = engine().pose_fusion.classify(h2, 960, 540)
        self.assertEqual(got2, "closed_fist")
        self.assertGreater(conf2, 0.9)

    def test_prototype_teaches_a_custom_pose(self) -> None:
        e = engine()
        h = ge.synth_hand("pointing_up")
        with self.assertRaises(PermissionError):
            e.teach_prototype(h, "mute", by="someone else", write=False)
        e.teach_prototype(h, "mute", write=False)
        got, _, detail = e.pose_fusion.classify(ge.synth_hand("pointing_up", jitter=0.01), 960, 540)
        self.assertEqual(detail.get("prototype", [None])[0], "mute")
        self.assertEqual(got, "mute")


class KeyFrameTests(unittest.TestCase):
    def test_endpoints_and_extrema(self) -> None:
        sig = [0, 1, 0, 2, 0, 3, 0, 1, 0]
        kf = ge.key_frames(sig, max_frames=5)
        self.assertEqual(kf[0], 0)
        self.assertEqual(kf[-1], len(sig) - 1)
        self.assertIn(5, kf)  # most prominent peak
        self.assertLessEqual(len(kf), 5)

    def test_short_signal_is_all_frames(self) -> None:
        self.assertEqual(ge.key_frames([1, 2, 3]), [0, 1, 2])


@unittest.skipUnless(REPO_MODELS, "integrations/hand-gesture-mediapipe not populated")
class RepoHeadTests(unittest.TestCase):
    def test_keypoint_knn_holdout(self) -> None:
        rows = ge._read_csv(ge.KEYPOINT_CSV)
        labels = ge._read_labels(ge.KEYPOINT_LABELS)
        random.Random(1).shuffle(rows)
        knn = ge.KNN().fit(rows[:-300], labels, stride=4)
        acc = sum(knn.predict(v)[0] == labels[l] for l, v in rows[-300:]) / 300
        self.assertGreater(acc, 0.9, acc)

    def test_point_history_knn_holdout(self) -> None:
        rows = ge._read_csv(ge.HISTORY_CSV)
        labels = ge._read_labels(ge.HISTORY_LABELS)
        random.Random(1).shuffle(rows)
        knn = ge.KNN().fit(rows[:-300], labels, stride=4)
        acc = sum(knn.predict(v)[0] == labels[l] for l, v in rows[-300:]) / 300
        self.assertGreater(acc, 0.9, acc)

    def test_repo_labels_map_onto_vocabulary(self) -> None:
        repo = cg.load_vocabulary()["repos"]["hand-gesture-mediapipe"]
        self.assertEqual(set(ge._read_labels(ge.KEYPOINT_LABELS)), set(repo["keypoint_labels"]))
        self.assertEqual(set(ge._read_labels(ge.HISTORY_LABELS)), set(repo["point_history_labels"]))


class SegmenterTests(unittest.TestCase):
    def test_engage_then_grab_collapse(self) -> None:
        sess = run(ge.DEMO_SCRIPTS["engage_grab_collapse"])
        self.assertEqual(seg_ids(sess), ["open_palm:hold", "closed_fist:hold", "open_palm:hold"])
        self.assertEqual(fired(sess), ["gesture.engage", "gesture.grab_collapse"])

    def test_engagement_palm_emits_at_dwell_not_at_release(self) -> None:
        obs = ge.synth_sequence([{"pose": "open_palm", "ms": 1500}])
        e = engine()
        first = None
        for o in obs:
            for s in e.feed(o):
                first = first or (o.t_ms, s)
        self.assertIsNotNone(first)
        t_emitted, seg = first
        self.assertLess(t_emitted, 500)
        self.assertGreaterEqual(seg.duration_ms, 300)

    def test_swipe_left_in_gallery(self) -> None:
        sess = run(ge.DEMO_SCRIPTS["swipe_left"], context="gallery")
        self.assertIn("open_palm:swipe_left", seg_ids(sess))
        self.assertIn("gesture.swipe_left", fired(sess))

    def test_left_hand_swipe_is_screen_relative(self) -> None:
        sess = run(ge.DEMO_SCRIPTS["swipe_left"], context="gallery", handedness="Left")
        self.assertIn("open_palm:swipe_left", seg_ids(sess))

    def test_flick_scroll_needs_engagement(self) -> None:
        sess = run(ge.DEMO_SCRIPTS["air_scroll_up"], context="reading")
        self.assertIn("open_palm:flick_down", seg_ids(sess))
        self.assertIn("gesture.air_scroll_up", fired(sess))

    def test_push_in_family(self) -> None:
        self.assertIn("gesture.spread_expand", fired(run(ge.DEMO_SCRIPTS["spread_expand"])))
        press = run([{"pose": "open_palm", "ms": 500, "size": 0.07},
                     {"pose": "open_palm", "ms": 400, "motion": "push_in", "size": 0.07, "size_end": 0.13}])
        self.assertIn("gesture.air_press", fired(press))

    def test_wave_circle_and_thumb(self) -> None:
        self.assertIn("gesture.wave_hello", fired(run([{"pose": "open_palm", "ms": 900, "motion": "wave"}])))
        self.assertIn("gesture.circle_repeat", fired(run(ge.DEMO_SCRIPTS["circle_repeat"])))
        self.assertEqual(fired(run(ge.DEMO_SCRIPTS["thumb_up"])), ["gesture.thumb_up_thanks"])

    def test_handoff_grab_ends_when_hand_leaves_frame(self) -> None:
        sess = run(ge.DEMO_SCRIPTS["handoff_grab"])
        self.assertIn("closed_fist:translate_out", seg_ids(sess))
        self.assertIn("gesture.handoff_grab", fired(sess))

    def test_handoff_needs_aaron_identity(self) -> None:
        sess = run(ge.DEMO_SCRIPTS["handoff_grab"], identity=False)
        held = [i for i in sess.intents if i.gesture == "gesture.handoff_grab"]
        self.assertTrue(held and not held[0].fired)
        self.assertIn("identity", held[0].hold_reason or "")

    def test_two_palms_pair_segment(self) -> None:
        sess = run(ge.DEMO_SCRIPTS["two_palms_hold"])
        self.assertEqual(seg_ids(sess), ["open_palm:hold"])
        self.assertEqual(sess.segments[0].hands, 2)
        self.assertEqual(fired(sess), ["gesture.two_palms_hold"])

    def test_zoom_in_two_hands_spread(self) -> None:
        sess = run([{"pose": "open_palm", "ms": 500},
                    {"pose": "open_palm", "ms": 500, "hands": 2, "hand_gap": 0.2, "hand_gap_end": 0.45}], context="reading")
        self.assertIn("open_palm:spread_apart", seg_ids(sess))
        self.assertIn("gesture.zoom_in", fired(sess))

    def test_double_open_home_is_not_a_beckon(self) -> None:
        sess = run([{"pose": "closed_fist", "ms": 300}, {"pose": "open_palm", "ms": 300},
                    {"pose": "closed_fist", "ms": 300}, {"pose": "open_palm", "ms": 300}], context="reading")
        self.assertNotIn("beckon", " ".join(seg_ids(sess)))
        self.assertIn("gesture.double_open_home", fired(sess))

    def test_flick_pause_flick_forgets(self) -> None:
        sess = run([{"pose": "back_of_hand", "ms": 300, "facing": "back", "motion": "flick_right"},
                    {"pose": "back_of_hand", "ms": 400, "facing": "back"},
                    {"pose": "back_of_hand", "ms": 300, "facing": "back", "motion": "flick_right"}])
        self.assertIn("gesture.flick_away_forget", fired(sess))

    def test_switch_hold_logs_only(self) -> None:
        sess = run(ge.DEMO_SCRIPTS["engage_grab_collapse"], act=False)
        self.assertEqual(fired(sess), [])
        self.assertEqual([i.requested_action for i in sess.intents], ["system.engage", "ui.collapse"])

    def test_no_hand_no_segments(self) -> None:
        sess = run([{"gap": 1500}])
        self.assertEqual(sess.segments, [])
        self.assertEqual(sess.intents, [])


class ObservationTests(unittest.TestCase):
    def test_round_trip_and_mirror(self) -> None:
        obs = ge.synth_sequence([{"pose": "open_palm", "ms": 100}])[0]
        d = obs.to_dict()
        back = ge.Observation.from_dict(d)
        self.assertEqual(len(back.hands), 1)
        self.assertAlmostEqual(back.hands[0].landmarks[0][0], obs.hands[0].landmarks[0][0], places=3)
        d["mirror"] = True
        flipped = ge.Observation.from_dict(d)
        self.assertAlmostEqual(flipped.hands[0].landmarks[0][0], 1 - obs.hands[0].landmarks[0][0], places=3)

    def test_labels_forms(self) -> None:
        h = ge.HandFrame.from_dict({"landmarks": [[0.5, 0.5, 0]] * 21, "labels": {"mediapipe": ["Open_Palm", 0.9], "hagrid": {"label": "palm", "score": 0.7}, "keypoint": "Open"}})
        self.assertEqual(h.labels["mediapipe"], ("Open_Palm", 0.9))
        self.assertEqual(h.labels["hagrid"], ("palm", 0.7))
        self.assertEqual(h.labels["keypoint"], ("Open", 0.8))

    def test_session_status_shape(self) -> None:
        sess = run(ge.DEMO_SCRIPTS["thumb_up"])
        st = sess.status()
        for key in ("frames", "segments", "intents", "engaged", "models", "last_intents"):
            self.assertIn(key, st)


class CliTests(unittest.TestCase):
    def test_demo_json(self) -> None:
        out = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "cam-gesture-see.py"), "--demo", "engage_grab_collapse", "--identity", "--act", "--quiet", "--json"],
            capture_output=True, text=True, check=True,
        ).stdout
        doc = json.loads(out[out.index("{"):])
        intents = [i["gesture"] for i in doc["runs"][0]["intents"] if i["fired"]]
        self.assertEqual(intents, ["gesture.engage", "gesture.grab_collapse"])

    def test_record_then_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rec = Path(tmp) / "obs.jsonl"
            subprocess.run([sys.executable, str(ROOT / "scripts" / "cam-gesture-see.py"), "--demo", "thumb_up", "--quiet", "--record", str(rec)], check=True)
            self.assertGreater(len(rec.read_text().splitlines()), 10)
            out = subprocess.run([sys.executable, str(ROOT / "scripts" / "cam-gesture-see.py"), "--replay", str(rec), "--act", "--quiet", "--json"], capture_output=True, text=True, check=True).stdout
            doc = json.loads(out[out.index("{"):])
            self.assertEqual([i["gesture"] for i in doc["runs"][0]["intents"]], ["gesture.thumb_up_thanks"])


if __name__ == "__main__":
    unittest.main()
