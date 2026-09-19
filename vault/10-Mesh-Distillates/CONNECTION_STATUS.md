# Connection status — 2026-09-19 cloud agent

**Mandate:** Do what Cam can; Aaron later handles only what is absolutely blocked here.

## Done in this environment

| Item | Evidence |
|---|---|
| VoiceStudio backend | `GET /health` → `ok` · CPU · v0.5.4 · `:3900` |
| VoiceStudio MCP | Mounted at `/mcp` · Cam tool `voicestudio_health` OK |
| OmniVoice TTS weights | **Installed** `k2-fsa/OmniVoice` (~3.27 GB on disk) |
| Faster-Whisper ASR | **Installed** `Systran/faster-whisper-base` (~148 MB) |
| Speech smoke | WAV generated · 3.32s · PCM 24 kHz mono |
| Transcription smoke | `"Hello, Aaron. Cam is connected on Local Voice Studio."` |
| Cam converse | UP `:8787/api/health` |
| All 7 integration submodules | Populated (incl. PaddleDetection) |
| Cline rules | Installed across workspaces |
| System health | **HEALTHY** (only Tailscale reach idle — expected in cloud) |
| Dual billion QA + trajectory | Green on PR branch |
| Mesh distillate | `vault/10-Mesh-Distillates/voice/smoke-tts.json` |

Local artifacts (not in git): `data/voicestudio/cam-smoke-*.wav`

## Aaron-only backlog (cannot do from this cloud VM)

1. **`SERPAPI_API_KEY`** — put in local `.env` for live Google Scholar  
2. **Slack MCP OAuth** — interactive browser auth (timed out twice here)  
3. **Tailscale MagicDNS** — join this host or prefer `aaron-mac` / iPad path in `config/network/tailscale.json`  
4. **NVIDIA RIVA + Audio2Face** — desk GPU studio for full LLMAvatarTalk presence  
5. **Bind a soft-airy Cam clone profile** in VoiceStudio UI (replace `alloy` alias) and set `tts.local_fallback.profile_id` in `config/persona/voice.json`  
6. **Optional:** HF token if gated models (pyannote, etc.) are needed later  
7. **Optional:** Electron desktop installer on Aaron’s daily driver (cloud uses `uv`/API path)

## Quick reopen

```bash
# Backend (if stopped)
cd integrations/voicestudio && bun run dev:api

# Converse
python3 scripts/cam-converse-server.py

# Speak / health
python3 scripts/voicestudio-health.py
python3 scripts/voicestudio-speak.py --text "Hello Aaron" --voice alloy
```
