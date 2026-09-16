# Tailscale — Cam companion network

**Status:** ENABLED as default path · Aaron already has Tailscale set up (2026-09-16)

## Why
Reach Cam’s live mic/camera converse from iPhone ↔ Mac without public ports or brittle LAN IPs.

## Default topology

```text
aaron-iphone  ──tailnet──►  cam-host (Mac)
                              │
                              ├─ cam-converse-server.py :8787
                              ├─ nullclaw / mesh (later)
                              └─ RIVA studio (optional)
```

## Setup (Aaron’s machines)

1. Confirm both devices are on the same tailnet (`tailscale status`)
2. Prefer MagicDNS names, e.g. `cam-host` / `aaron-iphone`
3. On Cam host Mac:

```bash
python3 scripts/cam-converse-server.py --host 0.0.0.0 --port 8787
# or: ./scripts/serve-cam-converse.sh
```

4. On iPhone Safari (or companion):

```text
http://<cam-host-magicdns>:8787
```

Example: `http://cam-mac:8787` or `http://100.x.y.z:8787`

5. Allow Microphone (+ Camera if testing face path)

## Config
Edit `config/network/tailscale.json` with your real MagicDNS / Tailscale IPs.

Mesh prefs:
- `tailscale_enabled: true`
- `cam_converse_via: "tailscale"`
- `cam_converse_url` derived from host + port

## Security
- Keep converse bound to Tailscale / local only — do **not** port-forward `:8787` to the public internet
- Aaron-only tasking still enforced in Cam
- Kill switch still pauses motors

## Cloud Agent note
Cursor Cloud Agent VMs are usually **not** on Aaron’s tailnet. Live mic tests run on Aaron’s Mac + iPhone over Tailscale; the agent develops/pushes code.
