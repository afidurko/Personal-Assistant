# ILLA Desktop (Electron)

Electron shell for [afidurko/illa-builder](https://github.com/afidurko/illa-builder/tree/beta).

| Contract | Value |
|---|---|
| Packager | **`electron-builder@26.16.1`** (exact) |
| Release | https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.16.1 |
| Default URL | `http://127.0.0.1:3000` (Vite `apps/builder` / `turbo run dev`) |
| Cloud mode | `ILLA_DESKTOP_MODE=cloud` → `https://cloud.illacloud.com` |
| Override | `ILLA_DESKTOP_URL=https://…` |
| appId | `com.afidurko.illa-builder` |
| Promote target | `illa-builder` repo path **`electron/`** on branch `cursor/desktop-electron-26-16-1` |

## Dev

```bash
# terminal A — ILLA web (from illa-builder checkout)
pnpm install && pnpm dev   # builder on :3000

# terminal B — this shell
export ILLA_DESKTOP_URL=http://127.0.0.1:3000
npm install
npm run check:pin
npm run dev
```

## Package

```bash
npm run dist:dir   # electron-builder@26.16.1 --dir
```

## Promote into illa-builder

From Personal-Assistant:

```bash
python3 scripts/promote-illa-desktop.py --dry-run
# needs write: ILLA_BUILDER_GITHUB_TOKEN or gh auth with push
python3 scripts/promote-illa-desktop.py --push
```

That copies this tree to `electron/`, adds root scripts `desktop` / `desktop:dist`, and opens a PR off `beta`.
