# VoiceStudio — local speech for Cam

Aaron’s fork: [afidurko/VoiceStudio](https://github.com/afidurko/VoiceStudio)  
Upstream: debpalash/VoiceStudio (local ElevenLabs alternative)

## Cam wiring

- Policy: `config/integrations/voicestudio.md`
- Config: `config/integrations/voicestudio.json`
- Submodule: `integrations/voicestudio`
- Coding workspace id: `voicestudio`
- Health: `python3 scripts/voicestudio-health.py`

## Role

Local TTS / ASR / clone / dub for Cam when NVIDIA RIVA studio is offline. Brain stays nullclaw. Full face presence stays LLMAvatarTalk.

## Next on Aaron’s machine

1. `git submodule update --init integrations/voicestudio`
2. Install or run VoiceStudio (Electron preferred)
3. Confirm `http://localhost:3900/health`
4. Bind a soft-airy Cam voice profile; keep analytics/cloud opt-in


## Connected (2026-09-19 cloud)

- Submodule initialized at `7ec803a`
- Dual billion QA green — see `vault/10-Mesh-Distillates/MERGE_READINESS_VOICESTUDIO.md`
- Live backend still needs Aaron host Electron + optional model consent


## Live connection (cloud 2026-09-19)

- Backend **UP** on CPU · `http://127.0.0.1:3900/health`
- MCP mounted at `/mcp` · Cam tool `voicestudio_health` OK
- OmniVoice weights **not** downloaded (await Aaron consent ~2.3GB)
- See `vault/10-Mesh-Distillates/CONNECTION_STATUS.md`
