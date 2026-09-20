# ILLA Builder — Cam low-code + desktop shell

Fork: [afidurko/illa-builder](https://github.com/afidurko/illa-builder/tree/beta) (`beta`)  
Upstream: [illacloud/illa-builder](https://github.com/illacloud/illa-builder)  
Desktop packager: **electron-builder@26.16.1** ([release](https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.16.1)) via [`electron-builder.md`](electron-builder.md)

## Role

ILLA is the **open-source Retool-class** builder (dashboards, CRUD, admin, CRM). Cam uses it as:

1. A **coding workspace** (`illa-builder`) for fork work on `beta`
2. A **desktop shell** (`integrations/illa-desktop`) that wraps the running builder UI in Electron and packages with the pinned builder

Brain stays nullclaw/Cam. ILLA is a tool surface, not an orchestrator.

## Layout

| Piece | Where |
|---|---|
| Web monorepo (fork) | `github.com/afidurko/illa-builder` @ `beta` |
| Electron shell + dist config | `integrations/illa-desktop` (this repo) |
| Packager pin | `electron-builder@26.16.1` |
| Check | `python3 scripts/illa-electron-check.py` |
| Vault | `vault/03-Projects/ILLA-Electron-Desktop.md` |

## Desktop bring-up

```bash
# 1) Run ILLA (Docker / CLI / local turbo) so the UI is reachable
# 2) Point the shell at it
export ILLA_DESKTOP_URL=http://127.0.0.1:48080

cd integrations/illa-desktop
npm install
npm run dev          # electron window
npm run dist:dir     # unpackaged build via electron-builder@26.16.1
```

Default URL is `http://127.0.0.1:48080`. Override with `ILLA_DESKTOP_URL` (or cloud: `https://cloud.illacloud.com`).

## Boundaries

- Cloud agent token **cannot push** to `afidurko/illa-builder` / `afidurko/electron-builder` yet — packaging kit stays in Personal-Assistant until Aaron grants write or applies a patch PR manually.
- Do not package against electron-builder fork `master` (v27 alpha).
- No outbound ILLA Cloud account automation from Cline.

## Chooser signals

`illa`, `illa-builder`, `illa desktop`, `electron-builder`, `26.16.1`
