#!/usr/bin/env python3
"""cam-gesture-see — Cam watches hands through a camera and resolves gestures.

Sources
  --camera N        webcam via OpenCV + MediaPipe Hands (Aaron's Mac; needs `pip install mediapipe opencv-python`)
  --replay FILE     recorded observations (JSONL, one Observation per line — what --record writes)
  --demo [NAME]     synthetic hands from cam_gesture_engine.DEMO_SCRIPTS (no camera needed)

Sinks
  stdout            segments + intents as they resolve (default)
  --post URL        also POST landmark frames to the converse server (/api/spike/hand) — same engine there
  --record FILE     save observations (landmarks only, never pixels) for replay / teaching
  --teach-pose ID   add every observed hand as an Aaron prototype for pose ID (data/gestures/prototypes.json)

Gates
  switch.gesture_control is read from config/connectome/switches.json (hold → every gesture is log-only);
  --act simulates Aaron flipping it for a dry run. --identity marks the hand as Aaron's (device.* actions).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cam_gesture_engine as ge  # noqa: E402
import cam_gestures as cg  # noqa: E402


def fmt_seg(s: cg.Segment) -> str:
    return f"{s.pose}:{s.motion}:{s.duration_ms}:{s.confidence}:{s.hands} @{s.t_ms}"


def fmt_intent(i: cg.Intent) -> str:
    mark = "FIRE" if i.fired else "HOLD"
    extra = f" ({i.hold_reason})" if i.hold_reason else ""
    return f"{mark} {i.gesture} → {i.action}{extra}\n       means: {i.meaning}"


class Sink:
    def __init__(self, args: argparse.Namespace, session: ge.GestureSession) -> None:
        self.args = args
        self.session = session
        self.record = open(args.record, "a", encoding="utf-8") if args.record else None
        self.batch: list[dict] = []
        self.quiet = args.quiet

    def observation(self, obs: ge.Observation) -> None:
        if self.record:
            self.record.write(json.dumps(obs.to_dict()) + "\n")
        if self.args.teach_pose and obs.hands:
            for h in obs.hands:
                self.session.engine.teach_prototype(h, self.args.teach_pose, obs.width, obs.height, by=self.args.by)
        segs, intents = self.session.feed(obs)
        self.emit(segs, intents)
        if self.args.post:
            self.batch.append(obs.to_dict())
            if len(self.batch) >= self.args.post_batch:
                self.flush_post()

    def emit(self, segs, intents) -> None:
        if self.quiet:
            return
        for s in segs:
            print(f"  seg  {fmt_seg(s)}")
        for i in intents:
            print(f"  {fmt_intent(i)}")

    def flush_post(self) -> None:
        if not self.batch:
            return
        payload = {
            "frames": self.batch,
            "device": self.args.device,
            "context": self.args.context,
            "aaron_identity": self.args.identity,
        }
        self.batch = []
        try:
            req = urllib.request.Request(
                self.args.post.rstrip("/") + "/api/spike/hand",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                body = json.loads(r.read().decode("utf-8") or "{}")
            for i in body.get("intents") or []:
                if not self.quiet:
                    print(f"  server: {'FIRE' if i.get('fired') else 'HOLD'} {i.get('gesture')} → {i.get('action')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  post failed: {exc}", file=sys.stderr)

    def close(self) -> None:
        segs, intents = self.session.flush()
        self.emit(segs, intents)
        if self.args.post:
            # One empty frame closes any open run on the server too.
            self.batch.append(
                ge.Observation(self.session.engine.last_t_ms + 700, [], self.args.width, self.args.height, self.args.device).to_dict()
            )
            self.flush_post()
        if self.record:
            self.record.close()


def iter_replay(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield ge.Observation.from_dict(json.loads(line))


def iter_camera(index: int, width: int, height: int, max_hands: int = 2, mirror: bool = True, show: bool = False):
    try:
        import cv2  # type: ignore
        import mediapipe as mp  # type: ignore
    except ImportError as exc:
        sys.exit(
            f"camera mode needs opencv-python + mediapipe ({exc}). On the Mac: pip install mediapipe opencv-python\n"
            "Cloud / headless: use --demo or --replay."
        )
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    hands = mp.solutions.hands.Hands(max_num_hands=max_hands, min_detection_confidence=0.6, min_tracking_confidence=0.5)
    t0 = time.monotonic()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = hands.process(rgb)
            t_ms = int((time.monotonic() - t0) * 1000)
            out_hands = []
            if res.multi_hand_landmarks:
                for lm, hd in zip(res.multi_hand_landmarks, res.multi_handedness or []):
                    label = hd.classification[0].label if hd and hd.classification else "Right"
                    score = float(hd.classification[0].score) if hd and hd.classification else 0.8
                    out_hands.append(
                        {"handedness": label, "score": score, "landmarks": [[p.x, p.y, p.z] for p in lm.landmark]}
                    )
            # MediaPipe assumes a mirrored selfie frame for handedness; the engine
            # flips x into screen space when mirror=True.
            yield ge.Observation.from_dict(
                {"t_ms": t_ms, "w": frame.shape[1], "h": frame.shape[0], "mirror": mirror, "hands": out_hands}
            )
            if show:
                view = cv2.flip(frame, 1) if mirror else frame
                cv2.imshow("cam-gesture-see", view)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
    finally:
        cap.release()
        hands.close()
        if show:
            cv2.destroyAllWindows()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--camera", type=int, help="webcam index (OpenCV + MediaPipe)")
    src.add_argument("--replay", type=Path, help="observations JSONL to replay")
    src.add_argument("--demo", nargs="?", const="all", help="synthetic script name or 'all'")
    ap.add_argument("--list-demos", action="store_true")
    ap.add_argument("--fps", type=int, default=30, help="synthetic frame rate for --demo")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    ap.add_argument("--no-mirror", action="store_true", help="camera frame is already in screen space")
    ap.add_argument("--show", action="store_true", help="camera preview window")
    ap.add_argument("--context", default="home")
    ap.add_argument("--device", default=None)
    ap.add_argument("--identity", action="store_true", help="treat the hand as Aaron's (switch.identity act)")
    ap.add_argument("--act", action="store_true", help="simulate switch.gesture_control = act for this run")
    ap.add_argument("--post", help="converse server base URL, e.g. http://127.0.0.1:8766")
    ap.add_argument("--post-batch", type=int, default=6)
    ap.add_argument("--record", type=Path)
    ap.add_argument("--teach-pose", help="pose id to add prototypes for (Aaron only)")
    ap.add_argument("--by", default="Aaron")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--json", action="store_true", help="print a JSON summary at the end")
    args = ap.parse_args()

    if args.list_demos:
        for name, script in ge.DEMO_SCRIPTS.items():
            print(f"{name:26} {' → '.join(s.get('pose', 'gap') + '/' + s.get('motion', 'hold') for s in script)}")
        return 0

    switch_act = args.act or ge.switch_is_act()
    if not switch_act and not args.quiet:
        print("switch.gesture_control is hold — every gesture resolves to system.log_only (use --act for a dry run)")

    engine = ge.GestureEngine()
    if not args.quiet:
        print(f"engine models: {engine.models}")

    summary: dict = {"runs": []}
    if args.demo:
        names = list(ge.DEMO_SCRIPTS) if args.demo == "all" else [args.demo]
        for name in names:
            if name not in ge.DEMO_SCRIPTS:
                sys.exit(f"unknown demo {name!r}; --list-demos")
            ctx = "gallery" if name.startswith("swipe") else args.context
            session = ge.GestureSession(
                engine=ge.GestureEngine(keypoint_knn=engine.keypoint_knn, history_knn=engine.history_knn),
                context=ctx, identity_ok=args.identity, switch_act=switch_act,
            )
            sink = Sink(args, session)
            if not args.quiet:
                print(f"\n== demo {name} (context {ctx}, {args.fps} fps)")
            for obs in ge.synth_sequence(ge.DEMO_SCRIPTS[name], fps=args.fps, device=args.device or "synthetic",
                                         width=args.width, height=args.height):
                sink.observation(obs)
            sink.close()
            summary["runs"].append({
                "demo": name,
                "segments": [fmt_seg(s) for s in session.segments],
                "intents": [{"gesture": i.gesture, "action": i.action, "fired": i.fired, "hold_reason": i.hold_reason} for i in session.intents],
            })
    else:
        session = ge.GestureSession(engine=engine, context=args.context, identity_ok=args.identity, switch_act=switch_act)
        sink = Sink(args, session)
        if args.replay:
            source = iter_replay(args.replay)
        elif args.camera is not None:
            source = iter_camera(args.camera, args.width, args.height, mirror=not args.no_mirror, show=args.show)
        else:
            ap.error("choose --camera N, --replay FILE, or --demo [NAME]")
        try:
            for obs in source:
                sink.observation(obs)
        except KeyboardInterrupt:
            pass
        sink.close()
        summary["runs"].append({
            "source": "camera" if args.camera is not None else str(args.replay),
            "status": session.status(),
            "segments": [fmt_seg(s) for s in session.segments],
            "intents": [{"gesture": i.gesture, "action": i.action, "fired": i.fired, "hold_reason": i.hold_reason} for i in session.intents],
        })
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
