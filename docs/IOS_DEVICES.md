# iPhone + iPad now · Mac open for later

Aaron’s gear **now:** iPhone + iPad + Tailscale.  
**Mac:** allowed / configured as a slot — **not required** until Aaron can get to it.

## Active now

| Path | Status | How |
|---|---|---|
| On-device Cam in Safari | **Primary** | Mic/camera/TTS on device; Cam replies on-device if no server |
| Tailscale iPhone ↔ iPad | **On** | Same tailnet |
| Shared server on iPad | Optional | a-Shell + `cam-converse-server.py` |
| Mac as Cam host | **Open for later** | Reserved MagicDNS `aaron-mac` — flip when ready |
| Native Xcode app | Later (needs Mac) | Scaffold only |

## Do this on iPhone / iPad (today)

1. Tailscale on — both devices online  
2. Safari → open `companions/web/` → **Add to Home Screen**  
3. Open **Cam** → **Enable mic & talk**

## Mac later (when you have it)

No rush — slot stays open:

1. Join Tailscale as `aaron-mac` (or edit MagicDNS in config)  
2. Set `config/network/tailscale.json` → `hosts.mac_available: true` and `preferred_cam_host: "aaron-mac"`  
3. Run:

```bash
python3 scripts/cam-converse-server.py --host 0.0.0.0 --port 8787
```

4. iPhone/iPad open `http://aaron-mac:8787`  
5. Optional: Xcode native companion + RIVA studio

## Config
- `config/network/ios-devices.json` — `mac.status: open_for_later`  
- `config/network/tailscale.json` — `mac_slot_open: true`  
- Companion: `companions/web/`
