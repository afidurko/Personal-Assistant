# Connection status — 2026-09-19 cloud agent

**Goal:** Connect what you can (VoiceStudio + Cam stack)

## Live now

| Service | Status | Endpoint |
|---|---|---|
| VoiceStudio backend | **UP** (CPU, v0.5.4) | `http://127.0.0.1:3900/health` → `{"status":"ok","device":"cpu"}` |
| VoiceStudio MCP | **mounted** | `http://127.0.0.1:3900/mcp` (client id `cam`) |
| VoiceStudio OpenAPI | **UP** | 270 paths · speech/voices ready |
| Cam converse | **UP** | `http://127.0.0.1:8787/api/health` |
| Cam MCP `voicestudio_health` | **OK** | reports backend healthy |
| Submodules | **6/7 populated** | cline, jarvis, llmavatartalk, smart-second-brain, swiftguide, voicestudio |
| Cline rules | **installed** | across populated workspaces |

## Connected with limits

| Item | Status | Why |
|---|---|---|
| OmniVoice TTS model | not downloaded | ~2.3 GB — needs Aaron consent before first generate |
| ASR / AudioSeal | not cached | same opt-in download policy |
| Google Scholar live | dry-run only | `SERPAPI_API_KEY` not in this environment |
| Slack MCP | auth timed out | needs Aaron interactive OAuth |
| PaddleDetection | empty | skipped (large); init on demand |
| Tailscale reach | idle | cloud VM is not Aaron’s Tailscale host |
| Full RIVA / Audio2Face | not here | NVIDIA studio on Aaron desk only |

## How to use (this VM while processes run)

```bash
# Health
python3 scripts/voicestudio-health.py

# Speak dry-run (no model)
python3 scripts/voicestudio-speak.py --text "Hello Aaron" --dry-run

# After Aaron approves model download:
# python3 scripts/voicestudio-speak.py --text "Hello Aaron"

# Converse UI
open http://127.0.0.1:8787

# Cam MCP
python3 scripts/cam-mcp-server.py   # stdio; tool voicestudio_health
```

## Process notes

- VoiceStudio API started via `uv sync` + `bun run dev:api` in tmux `voicestudio-api`
- Converse in tmux `cam-converse`
- MCP output mode preferred: `OMNIVOICE_MCP_OUTPUT_MODE=files` · base `/workspace/data/voicestudio`
