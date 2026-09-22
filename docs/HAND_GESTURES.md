# Hand gestures → Cam

Aaron's idea (2026-09-22): Cam should recognize hand gestures, each gesture
means something different, and Cam should **remember** which signal means what
and take the action that goes with it — collapse the page, expand the page,
move Cam from one device to another (iPhone → iPad), and more. Huawei shipped
a concept along these lines; this plan borrows its patterns and builds the
capability into Cam's connectome.

Status: **planned**. This PR ships the gesture database, the resolver, and the
connectome wiring behind a **hold** switch. Nothing acts on a real camera yet.

- Vocabulary (the database): [`config/gestures/gestures.json`](../config/gestures/gestures.json)
- Actions: [`config/gestures/actions.json`](../config/gestures/actions.json)
- Resolver + memory: [`scripts/cam_gestures.py`](../scripts/cam_gestures.py) · CLI [`scripts/cam-gestures.py`](../scripts/cam-gestures.py)
- Gate: [`scripts/gesture-check.py`](../scripts/gesture-check.py) (in `ci-static-gate`)
- Policy: [`config/integrations/hand-gestures.md`](../config/integrations/hand-gestures.md) · [`hand-gestures.json`](../config/integrations/hand-gestures.json)

## 1. Research — what Huawei did

### AI Air Transfer (隔空传送) — HarmonyOS 5, Mate 70 / Mate X6 / MatePad Pro, Nov 2024

Richard Yu demoed it on Weibo the day before the Mate 70 launch: hold an open
palm at about half an arm from the phone, pause until the screen reacts, **clench
your fist to grab** the open image / video / playing track / current screenshot,
**keep the fist and move it in front of the tablet**, pause, **open your palm to
drop** it there. Both devices need HarmonyOS 5, Bluetooth + WLAN on, unlocked
screens, the Air Transfer switch on, and ≥ 40 cm between them.

Developer surface (Share Kit): a page registers a `harmonyShare.gesturesShare`
listener; when the system sees the grab it hands the page a `SharableTarget`,
and the page must call `share()` with its data within ~3 s. Discovery,
connection, and transfer are the system's job — the app only says *what* is
grabbable. The same grab also triggers Grabshot when both switches are on.

Sources: [harmonyos.cool air-transfer](https://harmonyos.cool/docs/full-scene/air-transfer) ·
[GSMArena demo](https://www.gsmarena.com/huawei_demoes_gestureoperated__file_transfer_between_devices-news-65475.php) ·
[Android Authority](https://www.androidauthority.com/huawei-grab-drop-transfer-files-3503116/) ·
[Huawei Central](https://www.huaweicentral.com/huawei-mate-70-series-to-feature-iphone-like-ai-airdrop-gesture/)

### Air gestures (Smart Sensing) — Mate 30 Pro onward

| Huawei gesture | How | Effect |
|---|---|---|
| Air scroll up | palm to screen, fingers up, flick wrist **down** | scroll up (volume in Video) |
| Air scroll down | back of hand, fingers down, flick wrist **up** | scroll down |
| Air scroll left / right | palm / back of hand, fingers sideways, flick | Gallery / e-book pages |
| Grabshot | palm 20–40 cm, wait for the hand icon, clench fist | screenshot |
| Air press | palm from 30–40 cm to ~5 cm | answer call, pause / resume playback |

Common thread: an **engagement** step (hold the palm until a hand icon appears
at the top of the screen), then one motion, then a visible confirmation.
Source: [Huawei support — air gestures](https://consumer.huawei.com/en/support/content/en-us15974017/).

### What Cam keeps and what it skips

| Keep | Skip |
|---|---|
| Engage → gesture → confirm grammar with an on-screen glyph | Dedicated ToF / gesture sensor (Cam uses the camera it already has) |
| Grab → carry → release as the cross-device verb | Huawei ID / HarmonyOS device fabric — Cam's devices are already one Tailscale tailnet |
| "Page declares what is grabbable" (`SharableTarget`) → Cam's carry payload is a session snapshot the PWA declares | File copy as the payload — Cam moves the *session*, not a file |
| Disambiguate grab by what follows | Firing Grabshot and Transfer at once |
| Same switch discipline (feature off until enabled) | Vendor-locked receiving devices |

### Recognizer — MediaPipe Gesture Recognizer

Runs on-device in Safari via WASM (`@mediapipe/tasks-vision`), 21 landmarks per
hand, up to 2 hands, canned classes `None, Closed_Fist, Open_Palm, Pointing_Up,
Thumb_Down, Thumb_Up, Victory, ILoveYou`, plus a custom classifier trained with
Model Maker from a folder-per-label dataset (must include a `none` class);
custom wins over canned when both fire. Cam adds a **landmark motion segmenter**
on top (flick / swipe / push / wave / circle / translate) because the canned
model is pose-only. Sources: [web guide](https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer/web_js) ·
[customization](https://developers.google.com/edge/mediapipe/solutions/customization/gesture_recognizer).

### Aaron's repos — mounted and mapped

Three repos arrived; each is a submodule under `integrations/` and is mapped
onto the vocabulary's `primitives.poses` / `primitives.motions` in
`gestures.json → repos`. The vocabulary stays the source of truth; repos supply
data, models, and patterns. `gesture-check` fails if a repo label is neither
mapped nor explicitly ignored, and reads the live label files out of the
submodules so drift is caught.

| Repo (fork → upstream) | What it is | Job in Cam | Mapping |
| --- | --- | --- | --- |
| [`integrations/hagrid`](https://github.com/afidurko/hagrid) → hukenovs/hagrid | **HaGRIDv2**: 1,086,158 FullHD images, 33 static classes + `no_gesture`, 65,977 people at 0.5–4 m; pretrained YOLOv10 / ResNet gesture + hand detectors; sibling `dynamic_gestures` algorithm trained only on the static set | **Training data for every `support: custom` pose.** Model Maker wants folder-per-label; HaGRID already is one, and it is the dataset Google's own customization guide uses. Also the desktop detector when the Mac slot opens | `pose_map`: 25 labels → 13 poses (`palm/stop → open_palm`, `stop_inverted → back_of_hand`, `fist/grabbing → closed_fist`, `grip → pinch`, `one → pointing_up`, `point → pointing_away`, `like/dislike → thumb_up/down`, `peace/two_up(_inverted) → victory`, `ok`, `three/three2/three3 → three`, `four`, `mute`, `take_picture`, `timeout`, `hand_heart(2)`, `no_gesture → none`). 9 ignored: `call rock holy xsign thumb_index(2) three_gun` reserved for Aaron to teach; `middle_finger little_finger` never bound |
| [`integrations/hand-gesture-mediapipe`](https://github.com/afidurko/hand-gesture-recognition-using-mediapipe) → Kazuhito00 (Apache-2.0) | MediaPipe Hands (Python) + two tiny MLPs: **keypoint classifier** on 21 normalized landmarks (`Open / Close / Pointer`) and **point-history classifier** on 16 frames of index-fingertip trajectory (`Stop / Clockwise / Counter Clockwise / Move`); press `k` / `h` to log samples, notebooks retrain to TFLite | **The segmenter reference.** Cam's motion primitives are trained the point-history way (fingertip trajectory window → class) and its `landmark_rule` poses follow the keypoint MLP. The log-samples → retrain → swap-model loop *is* teach mode (P4) | `keypoint_map`: `Open → open_palm`, `Close → closed_fist`, `Pointer → pointing_up`. `motion_map`: `Stop → hold`, `Clockwise → circle_cw`, `Counter Clockwise → circle_ccw`, `Move → translate` (refined by direction into flick / swipe / raise / lower / push / pull / translate_out) |
| [`integrations/hand-gesture-recognition`](https://github.com/afidurko/HandGestureRecognition) → Ha0Tang (CC BY-NC-SA 4.0) | *Fast and Robust Dynamic Hand Gesture Recognition via Key Frames Extraction and Feature Fusion* (Tang, Liu, Xiao, Sebe — Neurocomputing 2019), MATLAB; datasets Cambridge (flat / spread / V-shape × left / right / contract), Northwestern, HandGesture (`0–9 NO OK`), Action3D (`box, high wave, horizontal wave, curl, circle, hand up`) | **Dynamic-gesture patterns.** Key-frame extraction = pick the frames of a motion that carry the gesture and drop the rest — exactly what Cam's segmenter must do before a `swipe` or `circle` is one segment. Academic license → patterns and class lists only, no code shipped | `motion_map`: `*_leftward → swipe_left`, `*_rightward → swipe_right`, `*_contract → pull_out`, `high/horizontal_wave → wave`, `curl → beckon`, `circle → circle_cw`, `hand_up → raise`. `pose_map`: `1–5 → pointing_up / victory / three / four / open_palm`, `OK → ok_sign` |

What the repos added to the vocabulary beyond mappings: four HaGRID-only poses
and the gestures they make unambiguous — `mute` (finger over lips →
`converse.mute_toggle`, new action), `take_picture` (two-hand viewfinder →
`ui.screenshot`, never collides with the one-hand grab family), `timeout`
(referee T → `presence.hold_all`), `hand_heart` (→ `converse.thanks`). Vocabulary
now: 44 gestures, 34 actions. The next repo goes in `aaron_repos.next_slot`.

Runtime split: on the iPhone / iPad the PWA keeps MediaPipe tasks-vision in
WASM (custom `.task` trained from HaGRID folders + Aaron's samples); on the Mac
the HaGRID YOLOv10 detector or Kazuhito00's `app.py` can be the recognizer, both
posting the same `pose:motion:ms:conf:hands` segments to `/api/spike/gesture`.

## 2. The idea in Cam terms

```text
Aaron's hand
   │  camera frames (never leave the device)
   ▼
Companion PWA recognizer  → MediaPipe pose label + landmark motion → segments
   │  pose:motion:duration_ms:confidence:hands      POST /api/spike/gesture
   ▼
sense.vision.gesture ─► switch.gesture_control ─► area.visual ─► area.premotor
                                                                    │  vocabulary + learned bindings
                                                                    ▼
                                                               switch.identity  (Aaron's hand?)
                                                                    │
                                                                    ▼
                                                                area.mtl  (remember: mesh/gestures)
                                                                    │
                                                                    ▼
                                                             switch.autonomy ─► motor.gesture
                                                                                    │
                    ┌──────────────────────┬─────────────────────┬──────────────────┤
                    ▼                      ▼                     ▼                  ▼
             companion PWA          converse server       device bridge          mesh
        collapse/expand/scroll   stop/yes/no/repeat    handoff iPhone→iPad   log-only / teach
```

Gates in order (both in `connectome-route.py` and in the resolver):

1. `switch.kill` — everything stops.
2. `switch.gesture_control` — **hold** by default; on hold every recognized gesture becomes `system.log_only` into `mesh/gestures`.
3. Context binding — the same pose can mean different things in `home`, `reading`, `gallery`, `choice`, `prompt`, `speaking`, `carrying`, `teach`.
4. Engagement — most commands need the palm-to-screen engage first (Huawei glyph); `wave`, `stop`, and `two palms hold` are always-on.
5. Confidence + cooldown.
6. `switch.identity` — actions marked `aaron_identity_required` (screenshot, every `device.*`, confirm, hold-all, memory) need Aaron's face / voice match; other hands are logged, never obeyed.
7. Sentinel — `motor.gesture` is class `write_local`; trajectory policy `gesture_never_outbound` strips text / call / facetime / inkbox / jobs / higgsfield / enhance from any gesture plan. A gesture is **never** a Sentinel approval.

## 3. The gesture database

`config/gestures/gestures.json` has five parts:

| Part | What it holds |
|---|---|
| `recognizer` | engine, canned labels, custom model path, engagement distance, frame rate, segmenter / dataset references |
| `repos` | Aaron's repos (`hagrid`, `hand-gesture-mediapipe`, `hand-gesture-recognition`): path, upstream, license, label lists, `pose_map` / `keypoint_map` / `motion_map` onto the primitives, explicit `ignore` lists |
| `primitives.poses` / `primitives.motions` | the alphabet — 20 poses (8 canned, 5 landmark rules, 7 custom trained from HaGRID) and 19 motions |
| `contexts` | where a binding applies |
| `grammar` | engagement, one-intent-per-window, sequence timeout, carry TTL, tie-break order, handedness mirror, grab disambiguation |
| `gestures` | 44 bindings: `steps` (pose + motion + duration window) → `meaning` → `action` in `contexts`, with confidence, cooldown, priority, support, source |
| `learning` | who may teach, the teach flow, precedence, conflicts, feedback, forgetting, custom-model retrain |

`config/gestures/actions.json` is the catalog of 34 actions the gestures may
bind to — each with `target` (PWA / converse server / device bridge / mesh /
vision), `motor`, `sentinel_class`, `reversible`, `confirm`, and
`aaron_identity_required`.

### Vocabulary (defaults)

| Gesture | How | Means | Action | Contexts | Aaron-only |
|---|---|---|---|---|---|
| `gesture.engage` | open_palm/hold≥300ms | I am about to give you a hand command — watch my hand. | `system.engage` | * |  |
| `gesture.grab_collapse` | open_palm/hold≥300ms → closed_fist/hold≥150ms → open_palm/hold≥100ms | Collapse the page — fold what I'm looking at down to its compact state. | `ui.collapse` | * |  |
| `gesture.spread_expand` | closed_fist/hold≥300ms → open_palm/push_in≥100ms | Expand the page — open what I'm looking at to its full state. | `ui.expand` | * |  |
| `gesture.air_scroll_up` | open_palm/flick_down≥80ms | Scroll up (or raise volume in media). | `ui.scroll_up` | reading, home, * |  |
| `gesture.air_scroll_down` | back_of_hand/flick_up≥80ms | Scroll down (or lower volume in media). | `ui.scroll_down` | reading, home, * |  |
| `gesture.air_scroll_left` | open_palm/flick_left≥80ms | Go to the previous page / card. | `nav.page_prev` | gallery, reading, * |  |
| `gesture.air_scroll_right` | back_of_hand/flick_right≥80ms | Go to the next page / card. | `nav.page_next` | gallery, reading, * |  |
| `gesture.swipe_left` | open_palm/swipe_left≥150ms | Next (page moves left, like a touch swipe). | `nav.page_next` | gallery |  |
| `gesture.swipe_right` | open_palm/swipe_right≥150ms | Previous (page moves right, like a touch swipe). | `nav.page_prev` | gallery |  |
| `gesture.grabshot` | open_palm/hold≥300ms → closed_fist/hold≥1200ms | Capture what's on screen right now. | `ui.screenshot` | * | yes |
| `gesture.handoff_grab` | open_palm/hold≥300ms → closed_fist/hold≥200ms → closed_fist/translate_out≥100ms | Pick this up — I'm taking Cam (this page / this session) to another device. | `device.handoff_grab` | * | yes |
| `gesture.handoff_release` | closed_fist/hold≥300ms → open_palm/hold≥200ms | Put it down here — continue Cam on this device. | `device.handoff_release` | carrying | yes |
| `gesture.handoff_cancel` | open_palm/wave≥600ms | Never mind — keep Cam where it was. | `device.handoff_cancel` | carrying |  |
| `gesture.beckon_follow` | palm_up/beckon≥600ms | Come here — move Cam's live session to the device I'm beckoning at. | `device.follow_me` | * | yes |
| `gesture.wave_hello` | open_palm/wave≥600ms | Cam, I'm here — pay attention to me on this device. | `converse.attention` | * |  |
| `gesture.stop_hand` | open_palm/hold≥900ms | Stop talking / stop what you're doing on screen. | `converse.stop` | speaking |  |
| `gesture.air_press` | open_palm/push_in≥150ms | Pause / resume Cam's presence (face + voice). | `presence.pause_resume` | home, speaking, * |  |
| `gesture.thumb_up_yes` | thumb_up/hold≥500ms | Yes / go ahead with the low-risk thing you just asked. | `converse.confirm` | prompt, teach | yes |
| `gesture.thumb_up_thanks` | thumb_up/hold≥500ms | That was helpful — remember to do it like that. | `converse.thanks` | * |  |
| `gesture.thumb_down_no` | thumb_down/hold≥500ms | No / dismiss that. | `converse.reject` | * |  |
| `gesture.ily_thanks` | i_love_you/hold≥500ms | Thanks — strong positive feedback on the last turn. | `converse.thanks` | * |  |
| `gesture.point_tap` | pointing_up/hold≥250ms → pointing_up/push_in≥100ms | Select the thing I'm pointing at. | `ui.select` | home, gallery, reading |  |
| `gesture.one` … `gesture.five` | 1–5 fingers held ≥600ms | Option N. | `nav.choose_option` | choice |  |
| `gesture.victory_camera` | victory/hold≥800ms | Show / hide the camera preview. | `ui.toggle_camera_preview` | home |  |
| `gesture.ok_done` | ok_sign/hold≥500ms | OK, that's done / I accept this. | `converse.confirm` | prompt, teach | yes |
| `gesture.circle_repeat` | pointing_up/circle_cw≥500ms | Say that again. | `converse.repeat` | * |  |
| `gesture.circle_undo` | pointing_up/circle_ccw≥500ms | Undo that last screen change. | `ui.undo` | * |  |
| `gesture.palm_raise` | palm_up/raise≥200ms | Louder. | `converse.volume_up` | * |  |
| `gesture.palm_lower` | palm_down/lower≥200ms | Quieter (mute at the floor). | `converse.volume_down` | * |  |
| `gesture.zoom_in` | two hands open_palm/spread_apart≥200ms | Bigger — zoom in. | `ui.zoom_in` | reading, gallery |  |
| `gesture.zoom_out` | two hands open_palm/bring_together≥200ms | Smaller — zoom out. | `ui.zoom_out` | reading, gallery |  |
| `gesture.double_open_home` | fist → palm → fist → palm | Take me home. | `nav.home` | * |  |
| `gesture.pinch_remember` | pinch/hold≥1000ms | Remember this moment. | `memory.remember_this` | * | yes |
| `gesture.flick_away_forget` | back_of_hand/flick_right ×2 | Never mind — forget what I just had you remember. | `memory.forget_last` | * | yes |
| `gesture.point_identify` | pointing_away/hold≥800ms | Look at what I'm pointing at and tell me what it is. | `vision.identify` | * |  |
| `gesture.two_palms_hold` | two hands open_palm/hold≥1000ms | Everything on hold — pause all motors for this session. | `presence.hold_all` | * | yes |
| `gesture.shh_mute` | mute/hold≥700ms (HaGRID) | Quiet — mute Cam's voice for now (same sign again unmutes). | `converse.mute_toggle` | * | no |
| `gesture.frame_shot` | two hands take_picture/hold≥800ms (HaGRID) | Capture what's on screen — the unambiguous version of Grabshot. | `ui.screenshot` | * | yes |
| `gesture.timeout_hold` | two hands timeout/hold≥800ms (HaGRID) | Time out — everything on hold for this session. | `presence.hold_all` | * | yes |
| `gesture.hand_heart_thanks` | two hands hand_heart/hold≥500ms (HaGRID) | Loved that — strongest positive feedback on the last turn. | `converse.thanks` | * | no |

`python3 scripts/cam-gestures.py list` prints this from the JSON; the JSON wins if they drift.

### The grab family — one primitive, three meanings

Huawei uses palm → fist for both Grabshot and Air Transfer. Cam keeps one grab
and resolves by what follows (`grammar.grab_disambiguation`):

| After the fist… | Cam reads | Action |
|---|---|---|
| reopen in place within 800 ms | grab-and-let-go | `ui.collapse` |
| hold still ≥ 1200 ms | grab-and-hold | `ui.screenshot` |
| hold and move out of frame / pull away | grab-and-carry | `device.handoff_grab` → context `carrying` |

Expand starts from a **fist** (fist → palm bursting toward the screen) so the
collapse / expand pair never collides.

## 4. Remembering — how Cam knows what a signal means

Two layers, one resolver:

| Layer | Where | Who writes | Wins |
|---|---|---|---|
| Defaults | `config/gestures/gestures.json` (git) | this repo, reviewed | last |
| Learned | `data/gestures/learned.json` (local, gitignored) → distilled to `mesh/gestures` + MemoryBear | **Aaron only** via `cam-gestures.py teach --by Aaron` | first |

Precedence: learned + context › learned + `*` › default + context › default + `*`.

Teach flow (`learning.teach_flow`):

1. Aaron says "Cam, learn this gesture" (or runs the CLI) → context `teach`.
2. Aaron performs it 3–5×; only landmark sequences are kept (`data/gestures/samples/`), never frames.
3. Aaron states the meaning and picks an action from the catalog (or `system.log_only`).
4. Cam replays: "When you do *X* while *reading*, I will *collapse the page*." Thumb up confirms, thumb down discards.
5. Binding is written with provenance `{taught_by: Aaron, taught_at, samples, context, replaced}` and mirrored to `mesh/gestures`.

Rules: rebinding something that already has a meaning in the same context needs
`--replace` (Cam reports the existing meaning otherwise); thumb up / down within
5 s of a gesture action is reinforcement; reject rate > 30 % over 20 uses flags
the gesture in `gesture-check`; bindings unused 90 days are flagged stale, never
auto-deleted; ≥ 30 samples of a custom pose triggers an offline Model Maker
retrain, and shipping the new `.task` goes through `switch.cam_enhance`.

```bash
python3 scripts/cam-gestures.py teach --by Aaron --name "fist pump" \
  --meaning "next song" --action nav.page_next --context gallery --steps "closed_fist:raise:300"
python3 scripts/cam-gestures.py teach --by Aaron --name "thumb means collapse" \
  --meaning "fold it" --action ui.collapse --context reading --like gesture.thumb_up_thanks
python3 scripts/cam-gestures.py forget learned.fist_pump --by Aaron
```

Every fired or held intent packs to `mesh/gestures` as
`{gesture, meaning, action, requested_action, fired, hold_reason, context, device, confidence}` —
no frames, no landmarks — so MemoryBear can answer "what did that fist thing do
last week at the desk?".

## 5. Moving Cam between devices (iPhone → iPad)

Cam's devices already share one Tailscale tailnet and one converse server
(`config/network/ios-devices.json`: `aaron-iphone`, `aaron-ipad`, `aaron-mac`
later). Handoff is therefore **session state on the server**, not a file copy:

```text
iPhone PWA                     cam-converse-server                    iPad PWA
──────────                     ───────────────────                    ────────
palm → fist → move out   ─►   POST /api/spike/gesture
                               resolver: device.handoff_grab
                               carry = {payload: session snapshot,
                                        origin: aaron-iphone,
                                        deadline: now + 10 s}
                               context → carrying (all devices)
                                                          ◄─   fist → palm  POST /api/spike/gesture
                               resolver: device.handoff_release (from aaron-ipad)
                               iPad claims carry; origin shows "moved to iPad"
                               context → previous
```

- Payload = what the origin page declared grabbable (Huawei's `SharableTarget` idea): session id + transcript position + open page / card + media ref, or a grabshot.
- Only the device whose camera sees the release claims it; TTL 10 s (`grammar.carry_ttl_ms`), then `device.handoff_cancel` fires by timeout.
- Wave while carrying cancels; `device.follow_me` (beckon) is the shortcut when Aaron is already at the target.
- Every `device.*` action is Aaron-only (`switch.identity`), class `write_local` — the payload never leaves the tailnet.

## 6. Build plan

| Phase | Deliverable | Pieces touched | Gate |
|---|---|---|---|
| **P0 — this PR** | Gesture database, action catalog, resolver + Aaron-only teach memory, connectome wiring (`sense.vision.gesture`, `switch.gesture_control`, `hotspot.gesture`, `motor.gesture`), Sentinel class, 3 trajectory policies, `gesture-check` in CI, docs, vault notes | `config/gestures`, `config/connectome`, `scripts/cam_gestures.py`, `scripts/gesture-check.py` | `ci-static-gate` green; switch **hold** |
| **P1 — see hands, log only** | `companions/web/gestures.js`: MediaPipe `GestureRecognizer` (LIVE_STREAM) + landmark segmenter (point-history window per `integrations/hand-gesture-mediapipe`, key-frame pruning per `integrations/hand-gesture-recognition`) → `POST /api/spike/gesture`; server appends to `spikes` log, runs the resolver, emits activity for the live cortex; on-screen engaged glyph | PWA, `cam-converse-server.py` | still hold — Aaron watches `mesh/gestures` fill with correctly named gestures |
| **P2 — first live session** | Aaron flips `switch.gesture_control` → `standing_on`; PWA action bus implements `ui.collapse / ui.expand / ui.scroll_* / nav.page_* / converse.stop / thumb yes-no` | PWA action bus | Aaron confirms; `enabled_at` recorded in `switches.json` |
| **P3 — handoff** | Carry state on the converse server, device claim, origin banner; iPhone → iPad first, iPad → Mac when the Mac slot opens | `cam-converse-server.py`, PWA | `device.*` behind `switch.identity` |
| **P4 — teach mode** | Voice-triggered `teach` context, landmark sample capture, replay confirm, Model Maker retrain job for custom poses seeded from HaGRID folders (`integrations/hagrid` → `ok_sign three four mute take_picture timeout hand_heart`) plus Aaron's samples | PWA, `scripts/cam-gestures.py`, `data/gestures/` | new `.task` ships via `switch.cam_enhance` |
| **P5 — more eyes** | Pupil world camera and the Mac (HaGRID YOLOv10 detector or Kazuhito00 `app.py`) as further `sense.vision.gesture` sources posting the same segments | `integrations/pupil`, `integrations/hagrid`, `integrations/hand-gesture-mediapipe` | `switch.pupil_vision` |

P1 needs `@mediapipe/tasks-vision` from `registry.npmjs.org` (or a vendored
WASM bundle under `public/`) — not installable in the cloud environment until
the domain is allowlisted, so P1 lands from Aaron's machine.

## 7. Verification

- `python3 scripts/gesture-check.py` — database integrity, connectome / Sentinel / registry wiring, eight canonical resolver demos (collapse, expand, iPhone → iPad handoff, identity hold, switch hold, stop-while-speaking, yes-in-prompt, two-palms hold), and Aaron's repos: submodule declared + registered, every repo label mapped or ignored, live label files (`hagrid/constants.py`, Kazuhito00 CSVs) match the vocabulary.
- `python3 scripts/test_cam_gestures.py` — unit tests for the grammar, context precedence, learned-over-default, Aaron-only teach / forget, carry timeout, mesh packing.
- `python3 scripts/connectome-route.py --sense sense.vision.gesture --goal "collapse page"` — with the switch on hold the plan is `motor.mesh` only (log-only).
- `python3 scripts/ci-static-gate.py` — everything above plus the existing gates.

## 8. Risks and open questions for Aaron

- **Repo licenses** — `hand-gesture-recognition` is CC BY-NC-SA (academic): patterns and class lists only, never its code in a shipped Cam. HaGRID's license is a PDF in `integrations/hagrid/license/` — read before shipping a `.task` trained on it beyond personal use.
- **Approximate mappings** — HaGRID `grabbing → closed_fist` and `two_up / *_inverted → victory` are approximations flagged in `repos.hagrid.approximate`; retire them if P1 logs show confusion.
- **First device pair** — plan assumes iPhone → iPad (both active in `ios-devices.json`); Mac joins when its slot opens.
- **Thumbs-up as approval** — kept *out* of Sentinel in v1 (a false positive could approve egress). Revisit only as a two-factor: verified face + gesture + voice "yes".
- **False engages** — a palm held to the camera while talking will open the engage window; the 2.5 s window and the context-bound `stop` keep it cheap. Tune `dwell_ms` after P1 logs.
- **Handedness** — flick directions are mirrored to screen-relative; verify with Aaron's dominant hand in P1.
- **Lighting / distance** — MediaPipe degrades past ~1 m and in backlight; engage distance is 20–60 cm by design.
