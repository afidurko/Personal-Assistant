# FunASR integration — Aaron-only hearing for Cam

Source fork: [afidurko/FunASR](https://github.com/afidurko/FunASR) (upstream [modelscope/FunASR](https://github.com/modelscope/FunASR))

## Role

FunASR supplies **speaker embeddings** (CAM++) and optional ASR.
Cam owns **enrollment + match + gate** so only Aaron’s voice becomes a converse turn — surrounding talkers are dropped.

```text
mic mix (noisy room)
  → VAD segments
  → CAM++ embed per segment
  → cosine vs Aaron templates (threshold 0.85)
  → keep Aaron segments only → transcript / /api/turn
  → sense.aaron.voice score → switch.identity
```

**Not this:** anonymous `spk=0/1` diarization labels are not Aaron identity.
**Not this:** FunASR does not replace RIVA TTS / Audio2Face for full presence.

## Config

- Gate policy: [`config/identity/aaron-voice.json`](../identity/aaron-voice.json)
- Persona STT: [`config/persona/voice.json`](../persona/voice.json)
- Local store (gitignored): `identity/aaron/local/voice/embeddings.json`
- Samples (gitignored): `identity/aaron/local/voice/samples/*.wav`

## Enroll (on Aaron’s machine)

Record several clean clips of **only Aaron** (quiet room, 2–5s each, en + optional es):

```bash
pip install torch torchaudio funasr
# Prefer GPU torch wheels from pytorch.org when available

python3 scripts/aaron-voice-enroll.py \
  identity/aaron/local/voice/samples/aaron-01.wav \
  identity/aaron/local/voice/samples/aaron-02.wav
```

Status:

```bash
python3 scripts/aaron-voice-enroll.py --status
python3 scripts/aaron-voice-verify.py path/to/probe.wav --json
```

Dry-run without FunASR (tests / bring-up only — **not** production identity):

```bash
AARON_VOICE_ALLOW_DEV_BACKEND=1 python3 scripts/aaron-voice-enroll.py --backend hash_dev --synth-demo
```

## Converse wiring

`scripts/cam-converse-server.py`:

| Endpoint | Behavior |
|---|---|
| `GET /api/voice/status` | Enrollment + threshold |
| `POST /api/voice/gate` | WAV (`audio_wav_b64`) → accept/reject |
| `POST /api/spike/aaron.voice` | Identity spike |
| `POST /api/turn` (mic) | **403** unless Aaron gate passes |

Web companion sends a rolling ~4s WAV with each mic final transcript.

Text turns bypass the voice gate (device already in Aaron’s hands).

## Privacy

- Embeddings + samples stay under `identity/aaron/local/` (gitignored)
- `enroll-index.json` stores refs only (no vectors)
- Fail closed when not enrolled or backend missing
- Never enroll non-Aaron speakers as Aaron

## Docs

- Design: [`docs/AARON_VOICE_GATE.md`](../../docs/AARON_VOICE_GATE.md)
- iOS identity: [`docs/IOS_IDENTITY.md`](../../docs/IOS_IDENTITY.md)
