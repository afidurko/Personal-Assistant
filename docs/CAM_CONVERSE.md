# Cam live converse (mic + camera + speak)

## Status
**ENABLED** by Aaron (2026-09-16).  
**Devices:** iPhone + iPad **now**; Mac host **open for later** (not required) — `docs/IOS_DEVICES.md`.  
**Network:** Tailscale — `docs/TAILSCALE.md`.

## What this adds

| Piece | Path | Role |
|---|---|---|
| Web / PWA companion | `companions/web/` | Safari mic + camera + speech + soft TTS; **Aaron-only voice gate** |
| Home presence | `src/hooks/useCamVoice.ts` | React mic with enroll + noisy-room filter |
| Voice gate config | `config/identity/aaron-voice-gate.json` | Thresholds · Aaron-only · reject surrounding ASR |
| Converse server | `scripts/cam-converse-server.py` | Optional shared backend (iPad a-Shell / future host) |
| Tailscale | `config/network/tailscale.json` | iPhone ↔ iPad private mesh (`aaron-ipad` preferred host) |
| Device map | `config/network/ios-devices.json` | Roles for aaron-iphone / aaron-ipad |

## Aaron-only voice

1. Tap **Enroll my voice (10s)** in a quiet moment (or first mic enable auto-starts enroll)
2. Enable mic — Cam scores each utterance against your print
3. Other people talking nearby are **ignored** (no reply)
4. Typing always works

## Run on iPhone / iPad (no Mac)

1. Open `companions/web/` in **Safari** (Files / repo / host URL)
2. **Share → Add to Home Screen**
3. Open **Cam** → **Enable mic & talk**

On-device mode talks to Cam even when no Python server is running.

### Optional shared session (iPad hosts, iPhone joins)
On iPad (a-Shell): `python3 scripts/cam-converse-server.py --host 0.0.0.0`  
On iPhone: `http://aaron-ipad:8787` (edit MagicDNS in `config/network/tailscale.json` to match Tailscale app).

## API (when server is up)
- `GET /api/health` (includes Tailscale URL hints + `voice_gate`)
- `POST /api/turn` `{ "text"|"transcript", "source": "mic"|"text", "aaron_voice_score", "enrolled", "multi_speaker_hint" }`
- `POST /api/spike/mic` · `POST /api/spike/camera` · `POST /api/spike/aaron.voice`
- `GET /api/session`

## Connectome
Mic → `sense.ios.mic` · Camera → `sense.ios.camera` · Chat fallback → `sense.chat.aaron`  
Aaron voice → `sense.aaron.voice` → `switch.identity` → `hotspot.aaron_voice_noise` (spectral browser gate rejects non-Aaron in noise)  
Aaron-only hearing (server) → FunASR CAM++ gate (`docs/AARON_VOICE_GATE.md`) — complementary to the on-device spectral add-ons

## Aaron-only mic (server mode)

Mic turns require a passing voice gate when enrollment exists:

1. Browser: enroll ~10s quiet speech in the companion (spectral voiceprint / adaptive noise add-ons)
2. Host: `python3 scripts/aaron-voice-enroll.py identity/aaron/local/voice/samples/*.wav` (FunASR CAM++)
3. Companion sends score and/or ~4s WAV (`audio_wav_b64`) with each final transcript
4. Non-Aaron / surrounding speech → HTTP 403, no Cam reply

`GET /api/voice/status` · `POST /api/voice/gate` · `POST /api/voice/gate/reject` · `POST /api/spike/aaron.voice`

## Logs
`vault/10-Mesh-Distillates/converse/*.jsonl` (server mode only)
