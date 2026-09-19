# Feature enablement — Cam sees via Pupil

**Authorized by:** Aaron · **Date:** 2026-09-19 · **Status:** ENABLED

Aaron authorized wiring Pupil into Cam so **she can see** — Pupil Core world
camera + gaze, gated by `switch.pupil_vision`.

## Effective state

```json
{
  "cam_pupil_vision_enabled": true,
  "cam_can_see": true,
  "cam_see_via": "pupil",
  "pupil_vision_mode": "standing_on",
  "switch.pupil_vision.default": "standing_on",
  "sense.vision.world": true,
  "sense.vision.gaze": true,
  "motor.pupil": true,
  "hotspot.pupil_see": true,
  "mesh_namespaces": ["mesh/vision", "mesh/gaze"],
  "continuous_eye_tracking_default": false
}
```

## Runtime

```bash
# Dry-run Cam see path (sample fixtures)
python3 scripts/pupil-see.py --dry-run

# Pack provided exports
python3 scripts/pupil-see.py \
  --gaze path/to/gaze.json \
  --world path/to/world-meta.json \
  --out-dir /tmp/cam-see

# Probe live Pupil Capture/Service (REQ port 50020)
python3 scripts/pupil-see.py --probe --dry-run
```

- Submodule: `integrations/pupil`
- Policy: `config/integrations/pupil.md`
- Converse spike: `POST /api/spike/pupil` on `scripts/cam-converse-server.py`
- Kill switch still pauses all capture

## Privacy

- Not always-on surveillance of people other than Aaron
- Mesh keeps frame refs + gaze distillates; raw eye/world video stays local
- Continuous monitoring only when Aaron tasks a monitor goal
