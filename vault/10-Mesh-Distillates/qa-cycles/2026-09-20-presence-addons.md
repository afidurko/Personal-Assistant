# Suggestions and add-ons — 2026-09-20 3T

After pass-1 green, these issues were still real:

1. `switch.presence` still acted `motor.higgsfield` after Aaron rejected Speak clips.
2. Higgsfield hotspots still routed through presence.
3. No home-face gate in 3T / CI / merge-prep.

## Fixes

- Remove `motor.higgsfield` from `switch.presence`
- Higgsfield hotspots: outbound only (unused / rejected)
- Policy `higgsfield_rejected_for_cam_face` strips Speak clips from speak plans
- `motor.higgsfield` no longer requires `switch.presence`

## Add-ons

| Add-on | Entry |
|---|---|
| Presence check | `python3 scripts/presence-check.py` |
| MCP | `presence_check` |
| Tool | `tool.presence.check` |
| Piece | `piece.presence_portrait` |
| 3T / CI / merge-prep | presence-check + higgsfield-check |

## Standing

- Cam’s face is `identity/persona/cam-face.jpg` + Audio2Face
- Do not overlay Higgsfield Speak clips
- Raise `--physical 1000000000` only when you want a full 1B physical stress
- Desk studio: LLMAvatarTalk / A2F when the GPU is up
