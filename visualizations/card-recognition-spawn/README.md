# AR card battle + pupil control

Phone-AR card battle (desk camera look) with **iris / pupil gaze** control.

## Controls

1. **Enable pupil tracking** — webcam + MediaPipe Face Landmarker (iris landmarks 468 / 473)
2. Calibrate by looking at 5 dots (dwell or Space / click)
3. **Dwell ~0.9s** on `+` or a move to select

If the camera is blocked, use **pointer as gaze** (same dwell UX).

## Run

```bash
npx --yes serve -l 5179 visualizations/card-recognition-spawn
```

Open http://localhost:5179/ — allow camera — calibrate — dwell on **+** twice — dwell on a move.

## Stack

| Layer | Role |
|---|---|
| `pupil-gaze.js` | Iris UV → calibrated screen point → dwell click |
| `ar-battle.js` | Detect → spawn → battle |
| MediaPipe Face Landmarker | On-device pupil/iris tracking |

Gaze targets use `data-gaze-target` on `#scan-btn`, `#zone-active`, and move buttons.
