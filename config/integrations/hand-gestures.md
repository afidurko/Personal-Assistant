# Hand gestures — Cam reads Aaron's hands

Plan: [`docs/HAND_GESTURES.md`](../../docs/HAND_GESTURES.md)  
Vocabulary: [`config/gestures/gestures.json`](../gestures/gestures.json) · Actions: [`config/gestures/actions.json`](../gestures/actions.json)  
Status: **dry run** (Aaron, 2026-09-22) — engine + companion eyes built; `switch.gesture_control` is **hold** until the first live session

## Role in the team

Hand gestures are a **second input channel** next to voice. Aaron holds a hand
to the companion camera; the on-device recognizer names the pose + motion;
Cam looks the signal up in its vocabulary (defaults + what Aaron taught), checks
the gates, and fires the bound action — collapse or expand the page, scroll,
move Cam from iPhone to iPad, stop talking, yes / no.

| Concern | Owner |
|---|---|
| Frames → hand landmarks → pose label | companion PWA (MediaPipe, on-device) |
| Landmark motion → segments (`pose:motion:duration`) | companion PWA segmenter |
| Segments → gesture → meaning → action | `scripts/cam_gestures.py` (`motor.gesture`) |
| Remembering what Aaron taught | `data/gestures/learned.json` → `mesh/gestures` + MemoryBear |
| Whose hand may command | `switch.identity` (Aaron face / voice match) |
| Whether gestures may act at all | `switch.gesture_control` (Aaron) · `switch.kill` |
| Cross-device carry state | `cam-converse-server.py` (Tailscale, `config/network/ios-devices.json`) |

## Connectome

| Piece | Id |
|---|---|
| Sense | `sense.vision.gesture` |
| Switch | `switch.gesture_control` (default **hold**) |
| Hotspot | `hotspot.gesture` — `sense.vision.gesture → switch.gesture_control → area.visual → area.premotor → switch.identity → area.mtl → switch.autonomy → motor.gesture` |
| Motor | `motor.gesture` (Sentinel class `write_local`) |
| Mesh | `mesh/gestures` |
| Policies | `gesture_requires_gesture_switch` · `gesture_requires_aaron_identity` · `gesture_never_outbound` |

```bash
python3 scripts/cam-gestures.py list --context reading
python3 scripts/cam-gestures.py resolve --context home --identity \
  --segments "open_palm:hold:300,closed_fist:hold:200,closed_fist:translate_out:400,closed_fist:hold:400,open_palm:hold:250"
python3 scripts/gesture-check.py
python3 scripts/connectome-route.py --sense sense.vision.gesture --goal "collapse page"
```

## Privacy and control defaults

- Frames never leave the device; 21 landmarks per hand (no pixels) cross the tailnet to Cam's converse server, which runs the engine (`scripts/cam_gesture_engine.py`) and answers with segments + intents; recordings (`cam-gesture-see.py --record`) are landmarks only.
- Other people's hands are logged, never obeyed (`switch.identity`).
- No gesture reaches egress, spend, self-modify, `switch.kill`, or Sentinel approval — those stay voice + CLI + Aaron.
- Every held or unbound gesture lands in `mesh/gestures` as `system.log_only` so Aaron can teach it later.
- Only Aaron teaches or forgets (`cam-gestures.py teach --by Aaron`).
- Kill switch pauses `motor.gesture`.

## Aaron's repos

Three submodules, mapped in `config/gestures/gestures.json → repos` (details in `docs/HAND_GESTURES.md`):

| Path | Upstream | License | Job |
| --- | --- | --- | --- |
| `integrations/hagrid` | hukenovs/hagrid (HaGRIDv2) | see `license/en_us.pdf` | dataset + labels for every `support: custom` pose; pretrained detectors for the Mac |
| `integrations/hand-gesture-mediapipe` | Kazuhito00/hand-gesture-recognition-using-mediapipe | Apache-2.0 | segmenter reference (keypoint MLP + fingertip point-history MLP); teach-mode pipeline |
| `integrations/hand-gesture-recognition` | Ha0Tang/HandGestureRecognition | CC BY-NC-SA 4.0 | dynamic-gesture patterns (key-frame extraction); class lists only, no code shipped |

Rules: every repo label is either in a `*_map` or in `ignore`; `gesture-check` fails otherwise and also
diffs the live label files inside the submodules against the vocabulary. The vocabulary stays the
source of truth; repos supply recognizers, models, or datasets. Next repo:

```bash
git submodule add -b <branch> <url> integrations/<gesture-repo>
# add repos.<id> with labels + pose_map / motion_map / ignore in config/gestures/gestures.json
# register in config/workspaces/registry.json (integrations + coding_workspaces + chooser signal)
python3 scripts/gesture-check.py
```
