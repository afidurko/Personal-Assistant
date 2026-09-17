# Feature enablement — Cam live mic/camera converse

**Authorized by:** Aaron · **Date:** 2026-09-16 · **Status:** ENABLED

Aaron explicitly allowed Cam to **enable** live microphone + camera conversation.

## Effective state

```json
{
  "cam_live_converse_enabled": true,
  "cam_live_mic_enabled": true,
  "cam_live_camera_enabled": true,
  "ios_capture_mode": "standing_on",
  "switch.ios_capture.default": "standing_on",
  "auto_start_converse_server": true,
  "converse_port": 8787,
  "tailscale_enabled": true,
  "cam_converse_via": "tailscale"
}
```

## Runtime
- Server: `scripts/cam-converse-server.py`
- UI: `companions/web/` → Tailscale URL from `python3 scripts/cam-tailscale-url.py`
- Network: `docs/TAILSCALE.md` · `config/network/tailscale.json`
- Docs: `docs/CAM_CONVERSE.md`
- Kill switch: Aaron can still pause-all anytime

## Note
Set `cam_host_magicdns` to your Mac’s name from `tailscale status`. Cloud Agent is usually off-tailnet; live mic tests are on Aaron’s Mac + iPhone.