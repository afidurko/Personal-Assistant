# ILLA Builder desktop (electron-builder@26.16.1)

Aaron forked and tasked Cam (2026-09-20):

- [illa-builder @ beta](https://github.com/afidurko/illa-builder/tree/beta)
- [electron-builder fork](https://github.com/afidurko/electron-builder) (tracks upstream master / v27 alpha)
- Pin packaging to [electron-builder@26.16.1](https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.16.1)

## Status

| Piece | State |
|---|---|
| Cam configs | `config/integrations/illa-builder.*` + `electron-builder.*` |
| Desktop shell | `integrations/illa-desktop` (pin exact `26.16.1`) |
| Check | `python3 scripts/illa-electron-check.py` |
| Push to forks | Blocked for cloud agent (`cursor[bot]` 403) — promote shell into ILLA fork when write lands |

## Next (Aaron)

1. Grant write on the two forks **or** apply the desktop tree as a PR from a machine with access
2. Self-host ILLA (`ILLA_DESKTOP_URL`) and run `npm run dist:dir` in `integrations/illa-desktop`
3. Optionally bump VoiceStudio from `^26.15.3` → `26.16.1` on the same pin
