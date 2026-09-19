# VoiceStudio integration — local speech engine for Cam

Source: [afidurko/VoiceStudio](https://github.com/afidurko/VoiceStudio) (fork of [debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio))  
Path: [`integrations/voicestudio`](../../integrations/voicestudio) (git submodule)  
Config: [`config/integrations/voicestudio.json`](voicestudio.json)

## Role in the team

VoiceStudio is Cam’s **fully-local** voice cloning / TTS / ASR / dubbing engine — an open-source ElevenLabs alternative. It does **not** replace nullclaw as the brain.

| Piece | Role |
|---|---|
| Think | **nullclaw / Cam** (always) |
| Speak (local) | VoiceStudio TTS / cloned Cam voice via REST or MCP |
| Hear (local) | VoiceStudio transcription (646 languages) when RIVA is offline |
| Face motion | Still **LLMAvatarTalk** + Audio2Face when full presence is on |
| Agents | Mounted MCP at `/mcp` so Cam/Cline can call `generate_speech`, `transcribe`, `clone_voice` |

## When to use which voice path

| Mode | Use when | Stack |
|---|---|---|
| **Simple local** | Everyday speak without NVIDIA studio | VoiceStudio backend (`localhost:3900`) + Cam portrait |
| **Full Cam presence** | Desk avatar / call presence | LLMAvatarTalk + RIVA + Audio2Face (+ UE optional) |
| **Studio / clone / dub** | Design Cam’s voice, audiobooks, dubbing | VoiceStudio Electron app + models |

Prefer VoiceStudio for local-first TTS when RIVA/GPU studio is unavailable. Prefer full presence when Aaron starts an avatar session.

## Prerequisites (Aaron’s machine)

- Checkout: `git submodule update --init integrations/voicestudio`
- Backend default: `http://localhost:3900` (`GET /health`, `GET /openapi.json`)
- MCP: `http://localhost:3900/mcp` (stdio shim: `python -m backend.mcp_shim` from the checkout)
- Prefer Electron installer or `bun install && bun run dev` per upstream docs
- Model downloads are **opt-in** (large); ask Aaron before first OmniVoice download (~2.3 GB)
- Cloud services and analytics stay opt-in

## Cam-specific config

Mirror Cam prefs before binding a voice:

- Style: soft airy calm fluent English; Argentine origin — `config/persona/voice.json`
- Bind agents with `X-VoiceStudio-Client-Id: cam` (or per-role ids)
- Prefer `OMNIVOICE_MCP_OUTPUT_MODE=files` + a shared base path so WAV bytes stay out of LLM context
- Never commit reference audio, cloned profiles, or API tokens

```bash
git submodule update --init --recursive
cd integrations/voicestudio
# Prefer installed Electron app; or from source:
# bun install && bun run dev
python3 ../../scripts/voicestudio-health.py
```

## Connectome / motors

| Node | Id |
|---|---|
| Sense | `sense.voicestudio.health`, `sense.voicestudio.result` |
| Hotspot | `hotspot.voicestudio` |
| Motors | `motor.speak` (channel `voicestudio_local_tts`), `motor.voicestudio` |
| Switch | `switch.presence` + `switch.outbound` for audible output |

Coding work on the fork routes via `motor.cline` → workspace id `voicestudio`.

## Mesh / persistence

- Health + job distillates → `mesh/voice` / `mesh/runs`
- Do not store raw WAV/clones in git; distill “spoke with Aaron via VoiceStudio …” notes
- Secrets and model caches stay local under VoiceStudio’s data dir

## Privacy / gates

- Aaron-only tasking and approval
- Clone only voices Aaron authorizes
- Outbound speak still requires `switch.presence` / `switch.outbound`; kill switch wins
- Mark synthetic audio per upstream `mark_synthetic` rules — never present cloned speech as a live human
