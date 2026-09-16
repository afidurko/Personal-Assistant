## Status
**ENABLED** by Aaron (2026-09-16). See `identity/persistence/CAM_CONVERSE_ENABLED.md`.  
**Network:** Tailscale is the default companion path — `docs/TAILSCALE.md`.

## What this adds
Cam can hold a **voice conversation** through a companion:

| Piece | Path | Role |
|---|---|---|
| Web companion | `companions/web/` | Browser mic + camera (`getUserMedia`) + speech recognition + Cam TTS |
| Converse server | `scripts/cam-converse-server.py` | Accepts turns / spikes; replies as Cam; logs to vault |
| Launch | `scripts/serve-cam-converse.sh` | Starts server on `:8787` |
| Tailscale | `config/network/tailscale.json` | iPhone ↔ Cam host private mesh |
| iOS native | `companions/ios/` | Same capabilities — Xcode app still to be generated |

## Run on Aaron’s Mac + iPhone (Tailscale)

```bash
# on Cam Mac (already on tailnet)
python3 scripts/cam-converse-server.py --host 0.0.0.0
python3 scripts/cam-tailscale-url.py   # prints the URL to open on iPhone
```

1. Set `cam_host_magicdns` in `config/network/tailscale.json` to your Mac’s MagicDNS name (`tailscale status`)
2. On iPhone: open that URL (e.g. `http://cam-host:8787`)
3. Tap **Enable mic & talk** → allow Microphone  
4. Optionally **Enable camera** → allow Camera  

Same LAN `http://127.0.0.1:8787` still works on the Mac itself.

## API
- `GET /api/health`
- `POST /api/turn` `{ "text"|"transcript", "source": "mic"|"text" }`
- `POST /api/spike/mic` · `POST /api/spike/camera`
- `GET /api/session`

## Connectome
Mic → `sense.ios.mic` · Camera → `sense.ios.camera` · Chat fallback → `sense.chat.aaron`

## Logs
`vault/10-Mesh-Distillates/converse/*.jsonl`
