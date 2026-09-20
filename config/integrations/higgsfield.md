# Higgsfield integration — Cam lip-sync clips

Homepage: [higgsfield.ai](https://higgsfield.ai)  
API: [docs.higgsfield.ai](https://docs.higgsfield.ai/docs)  
Uploads: [file uploads](https://docs.higgsfield.ai/docs/concepts/file-uploads)  
Config: [`config/integrations/higgsfield.json`](higgsfield.json)

## Role

Higgsfield **Speak** turns Cam’s identity portrait + a short WAV into a photoreal talking-head clip (5 / 10 / 15 s). It is **not** the brain and **not** the live Audio2Face session.

| Piece | Owner |
|---|---|
| Think | nullclaw / Cam |
| Live face (desk) | LLMAvatarTalk + NVIDIA Audio2Face |
| Live face (browser) | Cam portrait + A2F ARKit weights |
| Cinematic clip | **Higgsfield Speak** (gated, paid) |

## Why the first wiring failed in real life

Speak v2 does **not** accept a local JPEG or a text prompt as the talking input.

1. **Public URLs were required, and Aaron does not have them.** The CLI refused `--live` without `--image-url` and `--audio-url`. Official docs: upload local files with `POST https://api.higgsfield.ai/files/generate-upload-url`, PUT the bytes to the presigned URL, then pass the returned `public_url`. That path was missing.
2. **`--text` never became a WAV.** Speak lip-syncs audio, not a prompt. There was no `--audio` file and no local TTS.
3. **Official credential names were ignored.** Console/docs use `HF_API_KEY_ID` / `HF_API_KEY_SECRET` / `HF_CREDENTIALS` / `HF_KEY`. Only `HIGGSFIELD_*` was read, so real keys looked “missing.”
4. **Home UI never submitted a job.** It only `GET` a previous clip (none existed). The overlay video was `muted`, shown only while browser TTS was speaking, and looped.
5. **Upload host ≠ Speak host.** Files: `https://api.higgsfield.ai`. Speak: `https://platform.higgsfield.ai`.

The current client uses the local portrait, synthesizes a WAV, uploads both, then Speak.

## When to use

| Mode | Use when |
|---|---|
| **Offline / dry-run** | Default. Resolves local files + planned upload. No upload. |
| **Live Speak** | Aaron set `HIGGSFIELD_LIVE=1` and keys, wants a rendered clip of a line |
| **Never auto** | `/api/turn` must not call Higgsfield (cost + face leaves the box) |

## Credentials (local `.env` only)

Any of these work:

```
# Official Higgsfield names
HF_API_KEY_ID=
HF_API_KEY_SECRET=
# or
HF_CREDENTIALS=KEY_ID:KEY_SECRET

# Cam aliases
HIGGSFIELD_API_KEY_ID=
HIGGSFIELD_API_KEY_SECRET=
HIGGSFIELD_API_BASE=https://platform.higgsfield.ai
HIGGSFIELD_FILES_BASE=https://api.higgsfield.ai
HIGGSFIELD_LIVE=0
```

Console: [console.higgsfield.ai](https://console.higgsfield.ai).  
Auth header: `Authorization: Key ${ID}:${SECRET}`.

Speak body (Speak v2): `input_image` + `input_audio` URLs (from the upload ticket), `prompt`, `quality` (`mid`|`high`), `duration` (`5`|`10`|`15`). Audio must be WAV.

## Commands

```bash
python3 scripts/higgsfield-check.py
python3 scripts/higgsfield.py status --json
python3 scripts/higgsfield.py speak --text "Hello Aaron" --dry-run
# Live (Aaron only; spends money; sends portrait + audio off-box):
# HIGGSFIELD_LIVE=1 python3 scripts/higgsfield.py speak --text "Hello Aaron" --live
# Optional: --audio path.wav  --image identity/persona/cam-face.jpg
```

Home UI: **Preview Speak request** (dry-run) or **Render Speak clip** when live is on. Play the MP4 with sound; do not mute it under browser TTS.

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
