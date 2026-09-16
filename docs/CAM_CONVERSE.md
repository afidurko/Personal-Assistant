# Cam live converse (mic + camera + speak)

## Status
**ENABLED** by Aaron (2026-09-16).  
**Devices:** iPhone + iPad (**no Mac**) — `docs/IOS_DEVICES.md`.  
**Network:** Tailscale — `docs/TAILSCALE.md`.

## What this adds

| Piece | Path | Role |
|---|---|---|
| Web / PWA companion | `companions/web/` | Safari mic + camera + speech + soft TTS; **on-device Cam fallback** |
| Converse server | `scripts/cam-converse-server.py` | Optional shared backend (iPad a-Shell / future host) |
| Tailscale | `config/network/tailscale.json` | iPhone ↔ iPad private mesh (`aaron-ipad` preferred host) |
| Device map | `config/network/ios-devices.json` | Roles for aaron-iphone / aaron-ipad |

## Run on iPhone / iPad (no Mac)

1. Open `companions/web/` in **Safari** (Files / repo / host URL)
2. **Share → Add to Home Screen**
3. Open **Cam** → **Enable mic & talk**

On-device mode talks to Cam even when no Python server is running.

### Optional shared session (iPad hosts, iPhone joins)
On iPad (a-Shell): `python3 scripts/cam-converse-server.py --host 0.0.0.0`  
On iPhone: `http://aaron-ipad:8787` (edit MagicDNS in `config/network/tailscale.json` to match Tailscale app).

## API (when server is up)
- `GET /api/health` (includes Tailscale URL hints)
- `POST /api/turn` `{ "text"|"transcript", "source": "mic"|"text" }`
- `POST /api/spike/mic` · `POST /api/spike/camera`
- `GET /api/session`

## Connectome
Mic → `sense.ios.mic` · Camera → `sense.ios.camera` · Chat fallback → `sense.chat.aaron`

## Logs
`vault/10-Mesh-Distillates/converse/*.jsonl` (server mode only)
