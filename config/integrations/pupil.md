# Pupil integration — Cam’s eyes (open source eye tracking)

Source: [afidurko/pupil](https://github.com/afidurko/pupil) (`master`)  
Upstream: [pupil-labs/pupil](https://github.com/pupil-labs/pupil) · [docs.pupil-labs.com/core](https://docs.pupil-labs.com/core/)  
Path: [`integrations/pupil`](../../integrations/pupil) (git submodule)  
Enablement: [`identity/persistence/CAM_PUPIL_VISION_ENABLED.md`](../../identity/persistence/CAM_PUPIL_VISION_ENABLED.md) — **ENABLED** so Cam can see

## Role in the team

Pupil is Cam’s **eye-tracking / gaze + world-camera** layer — Pupil Capture,
Player, and Service. The **world camera** is how Cam sees the room; eye cameras
supply gaze overlays.

It complements PaddleDetection (object/pose on stills/video) and the iOS
companion camera (Aaron converse). It is **not** the brain and **not** always-on
surveillance.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw |
| Task queue / persistence | nulltickets |
| Scheduling | nullboiler |
| Human override | nullhub / Aaron kill |
| Object/pose detection on media | PaddleDetection |
| Live see (world + gaze) | **Pupil** (`motor.pupil`) |
| Live iPhone camera converse | iOS companion |

## Connectome (Cam can see)

| Piece | Id |
|---|---|
| Switch | `switch.pupil_vision` (standing_on — Aaron 2026-09-19) |
| Sense (world) | `sense.vision.world` |
| Sense (gaze) | `sense.vision.gaze` |
| Hotspot | `hotspot.pupil_see` / `hotspot.gaze` |
| Motor | `motor.pupil` |
| Mesh | `mesh/vision` + `mesh/gaze` |
| Bridge | `scripts/pupil-see.py` |

```bash
python3 scripts/pupil-see.py --dry-run
python3 scripts/connectome-route.py --sense sense.vision.world --goal "see"
```

## Install (on Aaron’s machine — heavy)

```bash
git submodule update --init --recursive
cd integrations/pupil
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Linux USB camera access — see upstream README udev rules
```

Run from source:

```bash
cd integrations/pupil/pupil_src
python main.py capture   # or player / service
```

Prefer the network real-time API when Capture/Service is already running
([developer docs](https://docs.pupil-labs.com/core/developer/)).

## Mesh bridge

```bash
# Combined Cam-see ingest (world + gaze)
python3 scripts/pupil-see.py \
  --gaze path/to/gaze.json \
  --world path/to/world-meta.json \
  --out-dir /tmp/cam-see

# Gaze-only packer
python3 scripts/pack-gaze-result.py \
  --gaze path/to/gaze.json \
  --out /tmp/mesh-gaze.json
```

Converse / companion spike: `POST /api/spike/pupil` on `cam-converse-server.py`.

## Useful entry points (upstream)

- `pupil_src/main.py capture` — live capture + pupil/gaze + world
- `pupil_src/main.py player` — offline recording playback
- `pupil_src/main.py service` — headless service / API host
- Network API — real-time gaze over ZMQ for app integration

## Privacy defaults

- Enabled for Cam to see when tasked / converse spikes fire
- No background continuous eye-tracking of others unless Aaron tasks a monitor goal
- Distill frame refs + gaze + confidence into mesh; raw recordings stay local
- Kill switch pauses `motor.pupil`
