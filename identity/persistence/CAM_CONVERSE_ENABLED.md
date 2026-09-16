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
  "converse_port": 8787
}
```

## Runtime
- Server: `scripts/cam-converse-server.py`
- UI: `companions/web/` → http://127.0.0.1:8787
- Docs: `docs/CAM_CONVERSE.md`
- Kill switch: Aaron can still pause-all anytime

## Note
Cloud Agent hosts have no physical mic; enablement is on for Cam’s stack. Aaron opens the companion on his Mac/iPhone to speak.
