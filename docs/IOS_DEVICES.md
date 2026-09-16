# iPhone + iPad setup (no Mac)

Aaron’s current gear: **iPhone + iPad**, Tailscale already on. No Mac.

## What works now

| Path | Works without Mac? | How |
|---|---|---|
| On-device Cam in Safari | **Yes** | Open the web companion; mic/camera/TTS run on the device; Cam replies on-device if no server |
| Tailscale mesh between iPhone ↔ iPad | **Yes** | Both on same tailnet |
| Shared Cam server | Needs a host | Prefer **iPad** as host later (a-Shell) or any always-on Linux box on Tailscale |
| Native Xcode iOS app | Needs Mac | Scaffold only until a Mac/Xcode is available |

## Do this on iPhone / iPad

1. Install / open **Tailscale** — confirm both devices online  
2. On **either device**, open the Cam companion in **Safari**  
3. Tap **Share → Add to Home Screen** (PWA)  
4. Open **Cam** from home screen → **Enable mic & talk** → allow Microphone  
5. Optional: **Enable camera**

On-device mode talks to Cam even when `cam-converse-server.py` is not running.

## Optional: iPad as Cam host (shared session)

When you want iPhone to hit the same server over Tailscale:

1. On iPad install **a-Shell** (or similar)  
2. Clone/pull this repo, run:

```bash
python3 scripts/cam-converse-server.py --host 0.0.0.0 --port 8787
```

3. On iPhone Safari: `http://aaron-ipad:8787` (set real MagicDNS in `config/network/tailscale.json`)

## Config files
- Devices: `config/network/ios-devices.json`
- Tailscale: `config/network/tailscale.json` (cam host default = `aaron-ipad`)
- Companion: `companions/web/`
- Converse docs: `docs/CAM_CONVERSE.md`

## Limits (honest)
- Cloud Agent cannot press Allow on your mic permission sheet  
- Safari blocks mic on insecure remote `http://` unless host is localhost — on-device / Home Screen mode avoids that  
- Full RIVA / Audio2Face presence still needs a stronger host later
