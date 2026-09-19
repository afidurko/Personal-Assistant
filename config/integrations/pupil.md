# Pupil integration — open source eye tracking

Source: [afidurko/pupil](https://github.com/afidurko/pupil) (`master`)  
Upstream: [pupil-labs/pupil](https://github.com/pupil-labs/pupil) · [docs.pupil-labs.com/core](https://docs.pupil-labs.com/core/)  
Path: [`integrations/pupil`](../../integrations/pupil) (git submodule)

## Role in the team

Pupil is Cam’s **eye-tracking / gaze tool layer** — Pupil Capture, Player, and
Service for pupil detection, gaze mapping, and recording when Aaron tasks it.

It complements PaddleDetection (object/pose vision). It is **not** the brain and
**not** always-on surveillance.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw |
| Task queue / persistence | nulltickets |
| Scheduling | nullboiler |
| Human override | nullhub / Aaron kill |
| Object/pose detection on media | PaddleDetection |
| Gaze / pupil / eye-tracking streams | **Pupil** |
| Live iPhone camera | iOS companion |

The `vision` role (and subagents) may run Pupil on hardware Aaron provides or on
recordings Aaron approves. Continuous eye monitoring of anyone other than Aaron
is not authorized.

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

Prefer the network real-time API for Cam bridges when Capture/Service is already
running ([developer docs](https://docs.pupil-labs.com/core/developer/)). Full GUI
bundles are optional; keep large offline analysis human-initiated.

## Mesh bridge

Gaze summaries (not raw video) go to `mesh/gaze`:

```bash
python3 scripts/pack-gaze-result.py \
  --gaze path/to/gaze.json \
  --out /tmp/mesh-gaze.json
```

When nulltickets is up, curator/`vision` `PUT`s that document under `mesh/gaze`.

## Connectome

| Piece | Id |
|---|---|
| Sense | `sense.vision.gaze` |
| Hotspot | `hotspot.gaze` |
| Center | `center.vision` |
| Mesh | `mesh/gaze` |

## Useful entry points (upstream)

- `pupil_src/main.py capture` — live capture + pupil/gaze
- `pupil_src/main.py player` — offline recording playback
- `pupil_src/main.py service` — headless service / API host
- Network API — real-time gaze over ZMQ for app integration

## Privacy defaults

- No background eye-tracking loop unless Aaron tasks a monitor goal
- Distill gaze points + confidence + timestamps into mesh; raw recordings stay local
- Do not enroll or track non-Aaron eyes as Aaron identity
- Pair with iOS companion for phone camera; Pupil Core hardware when available
