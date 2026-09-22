# Cam hand gestures

Aaron, 2026-09-22: "Have Cam recognize certain hand gestures and each different hand
gesture means something different … collapse the page, expand the page, move from one
device to another such as iPhone to iPad … have Cam recognize and remember what hand
signals mean what and the action needed."

Research: [[2026-09-22-Huawei-Air-Transfer-hand-gestures]] · Plan: `docs/HAND_GESTURES.md`

## Where it lives

| Piece | Path |
|---|---|
| Vocabulary (the database) | `config/gestures/gestures.json` — 40 gestures, 16 poses, 18 motions, 10 contexts |
| Action catalog | `config/gestures/actions.json` — 33 actions (ui / nav / device / converse / presence / memory / vision / system) |
| Resolver + memory | `scripts/cam_gestures.py` · CLI `scripts/cam-gestures.py` |
| Learned bindings (Aaron only) | `data/gestures/learned.json` → `mesh/gestures` + MemoryBear |
| Connectome | `sense.vision.gesture` → `switch.gesture_control` → `area.visual` → `area.premotor` → `switch.identity` → `area.mtl` → `switch.autonomy` → `motor.gesture` |
| Gate | `scripts/gesture-check.py` (in `ci-static-gate`) · `scripts/test_cam_gestures.py` |

## Aaron's first three use cases

| Signal | Cam does |
|---|---|
| Palm → fist → let go | `ui.collapse` — fold the page |
| Fist → palm bursting toward the screen | `ui.expand` — open the page |
| Palm → fist → carry to the iPad → open palm | `device.handoff_grab` → `device.handoff_release` — Cam continues on the iPad |

## State

- [x] P0 — database, resolver, wiring, gates (this PR) — `switch.gesture_control` **hold**
- [ ] P1 — PWA recognizer (MediaPipe) + segmenter + `/api/spike/gesture`, log-only
- [ ] P2 — Aaron's first live session → flip switch; collapse / expand / scroll live
- [ ] P3 — handoff iPhone → iPad via converse-server carry state
- [ ] P4 — teach mode + custom pose model (`three`, `four`, `ok_sign`)
- [ ] P5 — Pupil world camera as second source; Aaron's repos mapped onto primitives

## Waiting on Aaron

- Starter repo link (slot: `integrations/<gesture-repo>`)
- Confirm iPhone → iPad as the first pair
