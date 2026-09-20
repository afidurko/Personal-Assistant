# ILLA Desktop (Cam)

Electron shell that loads Aaron’s [ILLA Builder](https://github.com/afidurko/illa-builder/tree/beta) UI and packages with **`electron-builder@26.16.1`** exactly.

| Pin | Value |
|---|---|
| npm | `electron-builder@26.16.1` |
| Release | https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.16.1 |
| Source commit | `7d3b30f3b15950d19f7c5ff882cf2d161cd3ba2c` |
| Fork (tracking) | https://github.com/afidurko/electron-builder (master = v27 alpha — not for dist) |

## Quick start

```bash
# ILLA UI must already be reachable (self-host or cloud)
export ILLA_DESKTOP_URL="${ILLA_DESKTOP_URL:-http://127.0.0.1:48080}"

npm install
npm run check:pin
npm run dev
npm run dist:dir   # electron-builder --dir
```

## Why the shell lives here

The cloud agent can commit to Personal-Assistant but **cannot push** to `afidurko/illa-builder` yet. When write access lands, promote this `electron/` tree into the ILLA fork (VoiceStudio-style) and keep the same 26.16.1 pin.
