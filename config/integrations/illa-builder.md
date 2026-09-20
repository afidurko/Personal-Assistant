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
# 1) ILLA web (illa-builder checkout): pnpm install && pnpm dev  → :3000
# 2) Shell
export ILLA_DESKTOP_URL=http://127.0.0.1:3000   # or ILLA_DESKTOP_MODE=cloud
cd integrations/illa-desktop
npm install && npm run check:pin && npm run dev
npm run dist:dir
```

## Promote into the fork

```bash
export ILLA_BUILDER_GITHUB_TOKEN=...   # Contents + PR write on afidurko/illa-builder
python3 scripts/promote-illa-desktop.py --push
```

Manual fallback: [`patches/illa-builder-desktop/`](../../patches/illa-builder-desktop/README.md)

## Boundaries

- Promotion push is blocked until `ILLA_BUILDER_GITHUB_TOKEN` or GitHub App write on the fork.
- Do not package against electron-builder fork `master` (v27 alpha).
- No outbound ILLA Cloud account automation from Cline.

## Chooser signals

`illa`, `illa-builder`, `illa desktop`, `electron-builder`, `26.16.1`
