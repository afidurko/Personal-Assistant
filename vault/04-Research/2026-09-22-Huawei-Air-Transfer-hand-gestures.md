# Huawei AI Air Transfer + air gestures → Cam hand gestures

Research for Aaron's idea (2026-09-22): Cam recognizes hand gestures, each one means
something, Cam remembers and acts. Applied in `docs/HAND_GESTURES.md` and
`config/gestures/`. Project note: [[Cam-Hand-Gestures]].

## The Huawei concept

**AI Air Transfer (隔空传送)** — HarmonyOS 5 / HarmonyOS NEXT, launched with the Mate 70
series, Mate X6 and MatePad Pro (Nov 2024; Richard Yu teaser video the day before).

- Open palm at about half an arm's length from the screen → pause → screen reacts
- **Clench fist** → grabs the open image / video, the track playing in Huawei Music, or a screenshot of the current page
- Keep the fist, **move to the receiving phone or tablet**, pause until it reacts
- **Open the palm** → content lands on the other device
- Requirements: both devices on HarmonyOS 5, Bluetooth + WLAN on, unlocked, Air Transfer switch on (Settings › System › Quick start & gestures), ≥ 40 cm between devices
- Store demo report: recognition accurate, transfer slower than expected

**Developer model (Share Kit):** a page subscribes to `harmonyShare.gesturesShare`; on a grab the
system passes a `SharableTarget`; the app builds `SharedData` (UTD type, content URI, title,
thumbnail) and calls `share()` within ~3 s. Discovery, pairing, transport are all system-owned.
No extra permission except `READ_MEDIA` for files outside the sandbox. If both Grabshot and Air
Transfer switches are on, one grab triggers both (first time asks whether to save the screenshot).

**Older air gestures (Smart Sensing, Mate 30 Pro →):** Air scroll up / down / left / right
(palm or back of hand 20–40 cm, wrist flick), Grabshot (palm then clench), Air press (palm
approaches to ~5 cm: answer call, pause / resume). A hand icon appears at the top of the screen
when the hand is registered — the engagement cue.

Sources: harmonyos.cool `/docs/full-scene/air-transfer` · GSMArena 2024-11-25 · Android Authority
"grab-drop transfer files" · Huawei Central "AI Airdrop gesture" · Huawei support en-us15974017 ·
CSDN HarmonyOS dev community notes on `gesturesShare`.

## Recognizer options

- **MediaPipe Gesture Recognizer** (Google AI Edge): 21 landmarks / hand, 2 hands, canned
  `None, Closed_Fist, Open_Palm, Pointing_Up, Thumb_Down, Thumb_Up, Victory, ILoveYou`,
  custom classifier via Model Maker (folder per label + `none`), runs in Safari via WASM →
  fits the on-device companion PWA and the "frames never leave the device" rule.
- Motion (flick / swipe / push / wave / circle / carry) is **not** in the canned model — Cam
  adds a landmark motion segmenter and expresses every gesture as pose + motion + duration.
- Aaron's starter repo: link pending; slot reserved in `config/integrations/hand-gestures.json`.

## What carried into Cam

| Huawei | Cam |
|---|---|
| Palm → hand icon → motion | `gesture.engage` → glyph → command window (2.5 s) |
| Grab → carry → release between devices | `device.handoff_grab` → context `carrying` (10 s TTL) → `device.handoff_release` on the device whose camera sees the palm open |
| Page declares what is shareable | PWA declares the carry payload (session snapshot), server holds it |
| Grabshot + Transfer both fire | resolve by follow-up: reopen = collapse, hold = screenshot, move = carry |
| Feature switch in Settings | `switch.gesture_control` (Aaron), plus `switch.identity` so only Aaron's hand commands |
| Huawei ID device fabric | Aaron's Tailscale tailnet + `cam-converse-server.py` |

## Open questions

- Repo link from Aaron; which device pair first (assumed iPhone → iPad)
- Whether a verified thumbs-up should ever count toward a Sentinel approval (kept out of v1)
