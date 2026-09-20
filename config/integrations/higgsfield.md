# Higgsfield integration — Cam lip-sync clips

Homepage: [higgsfield.ai](https://higgsfield.ai)  
API: [docs.higgsfield.ai](https://docs.higgsfield.ai/docs)  
Config: [`config/integrations/higgsfield.json`](higgsfield.json)

## Role

Higgsfield **Speak** turns Cam’s identity portrait + a short WAV into a photoreal talking-head clip (5 / 10 / 15 s). It is **not** the brain and **not** the live Audio2Face session.

| Piece | Owner |
|---|---|
| Think | nullclaw / Cam |
| Live face (desk) | LLMAvatarTalk + NVIDIA Audio2Face |
| Live face (browser) | Cam portrait + A2F ARKit weights |
| Cinematic clip | **Higgsfield Speak** (gated, paid) |

## When to use

| Mode | Use when |
|---|---|
| **Offline / dry-run** | Default. Status + wiring only. No upload. |
| **Live Speak** | Aaron set `HIGGSFIELD_LIVE=1` and keys, wants a rendered clip of a line |
| **Never auto** | `/api/turn` must not call Higgsfield (cost + face leaves the box) |

## Credentials (local `.env` only)

```
HIGGSFIELD_API_KEY_ID=
HIGGSFIELD_API_KEY_SECRET=
HIGGSFIELD_API_BASE=https://platform.higgsfield.ai
HIGGSFIELD_LIVE=0
```

Console: [console.higgsfield.ai](https://console.higgsfield.ai).  
Auth header: `Authorization: Key ${ID}:${SECRET}`.

Speak body (Speak v2): public `input_image` + `input_audio` URLs, `prompt`, `quality` (`mid`|`high`), `duration` (`5`|`10`|`15`).

## Commands

```bash
python3 scripts/higgsfield-check.py
python3 scripts/higgsfield.py status --json
python3 scripts/higgsfield.py speak --text "Hello Aaron" --dry-run --json
# Live (Aaron only; spends money; sends portrait + audio off-box):
# HIGGSFIELD_LIVE=1 python3 scripts/higgsfield.py speak --text "Hello Aaron" --live \
#   --image-url https://.../cam-face.jpg --audio-url https://.../line.wav
```

## Connectome

| Node | Id |
|---|---|
| Sense | `sense.higgsfield.health`, `sense.higgsfield.result` |
| Hotspots | `hotspot.higgsfield`, `hotspot.higgsfield_result` |
| Motor | `motor.higgsfield` |
| Switches | `switch.outbound` + `switch.presence` + `switch.kill` |

Cline does not spend money or upload Cam’s face. Live jobs stay Aaron-initiated.

## Privacy

- Portrait is Cam’s identity asset — treat as PII-adjacent
- Do not commit keys, WAVs, or MP4s
- Clips land in `data/higgsfield/` (gitignored)
