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
