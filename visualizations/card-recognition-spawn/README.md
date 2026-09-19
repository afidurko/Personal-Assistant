# AR card battle + pupil control

Phone-AR card battle with gaze control wired for Cam’s Pupil stack (`sense.vision.gaze` / `motor.pupil`).

## Controls

1. **Cam Pupil gaze** — `python3 scripts/pupil-gaze-bridge.py` then choose this in the gate  
2. **Webcam iris (MediaPipe)** — on-device iris landmarks when no Pupil Capture  
3. **Pointer as gaze** — dwell demo without camera  

Look / point to aim. **Dwell ~0.75s** on `+` or a move to select.

## Run

```bash
# terminal A — Pupil gaze bridge (fixture by default)
python3 scripts/pupil-gaze-bridge.py

# terminal B — viz
npx --yes serve -l 5179 visualizations/card-recognition-spawn
```

Open http://localhost:5179/ → **Use Cam Pupil gaze** → calibrate → dwell on **+** twice → dwell on a move.

Live Capture export file:

```bash
python3 scripts/pupil-gaze-bridge.py --file /path/to/gaze.json
```

## Stack

| Layer | Role |
|---|---|
| `scripts/pupil-gaze-bridge.py` | Serves `GET /gaze` from Pupil fixture/file for the browser |
| `pupil-gaze.js` | norm_pos / iris → calibrated screen point → dwell click |
| `ar-battle.js` | Detect → spawn → battle |
| `integrations/pupil` + `scripts/pupil-see.py` | Cam see mesh bridge (`mesh/gaze`) |

See `config/integrations/pupil.md` and `identity/persistence/CAM_PUPIL_VISION_ENABLED.md`.
