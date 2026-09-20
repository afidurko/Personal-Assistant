# ILLA Builder desktop (electron-builder@26.16.1)

Aaron forked and tasked Cam (2026-09-20):

- [illa-builder @ beta](https://github.com/afidurko/illa-builder/tree/beta)
- [electron-builder fork](https://github.com/afidurko/electron-builder) (tracks upstream master / v27 alpha)
- Pin packaging to [electron-builder@26.16.1](https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.16.1)

## Status

| Piece | State |
|---|---|
| Cam staging shell | `integrations/illa-desktop` — ready to promote |
| Packager pin | exact `26.16.1` (asserted by `check:pin` + `dist:dir`) |
| Load contract | default `http://127.0.0.1:3000`; `ILLA_DESKTOP_MODE=cloud` or `ILLA_DESKTOP_URL` |
| appId | `com.afidurko.illa-builder` |
| Icons | `build/icon.png` / `icon.ico` from ILLA favicon |
| Promote script | `python3 scripts/promote-illa-desktop.py --push` → `electron/` on `cursor/desktop-electron-26-16-1` |
| Push to fork | **Blocked** — needs `ILLA_BUILDER_GITHUB_TOKEN` (Contents + PR write) or GitHub App write on the fork |

## Before / after promote

**Done (Cam):** pin, URL contract, icons/appId, offline fail page, promote script, dry-run tree.

**Aaron (unblock):** add secret `ILLA_BUILDER_GITHUB_TOKEN` or grant the cloud agent push on `afidurko/illa-builder`, then re-run:

```bash
python3 scripts/promote-illa-desktop.py --push
# open PR: beta ← cursor/desktop-electron-26-16-1
```

**After push:** Cam keeps check/chooser; shell source of truth becomes `illa-builder/electron/`.
