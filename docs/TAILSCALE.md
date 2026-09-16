# Tailscale — Cam companion network

**Status:** ENABLED · Aaron’s tailnet · **iPhone + iPad** (no Mac)

## Topology (current → later)

```text
NOW:
  aaron-iphone  ←──tailnet──►  aaron-ipad
         │                         │
         └─ Safari Cam PWA         ├─ Safari Cam PWA
                                   └─ optional a-Shell host

LATER (slot open):
  aaron-mac  ── preferred Cam host + optional Xcode / RIVA
```

Default Cam host **now:** `aaron-ipad`  
Reserved for later: `aaron-mac` (`mac_slot_open: true` — not required yet)

## Setup
1. Tailscale app on iPhone + iPad — both online  
2. Rename devices in Tailscale admin to match config (or edit JSON to your real names)  
3. Use on-device Cam in Safari first (`docs/IOS_DEVICES.md`)  
4. Optional: run server on iPad; open `http://aaron-ipad:8787` on iPhone  

## Config
- `config/network/tailscale.json`
- `config/network/ios-devices.json`
- URL helper: `python3 scripts/cam-tailscale-url.py`

## Security
- No public port-forward of `:8787`
- Aaron devices only
- Kill switch still pauses Cam motors
