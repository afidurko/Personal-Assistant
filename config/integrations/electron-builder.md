# electron-builder — Cam packaging pin

Fork: [afidurko/electron-builder](https://github.com/afidurko/electron-builder)  
Upstream: [electron-userland/electron-builder](https://github.com/electron-userland/electron-builder)  
**Packaging pin:** [`electron-builder@26.16.1`](https://github.com/electron-userland/electron-builder/releases/tag/electron-builder%4026.16.1)

## Why this pin

Aaron’s fork `master` is identical to upstream `master` (currently **v27.0.0-alpha** — Node ≥22.12, native ESM, breaking changes). ILLA desktop packaging stays on the **v26** line until a deliberate v27 migration.

| Surface | Use |
|---|---|
| npm `electron-builder@26.16.1` | **Default** for `integrations/illa-desktop` dist |
| Tag `electron-builder@26.16.1` / commit `7d3b30f` | Source checkout when building from the fork |
| Fork `master` | Upstream tracking / v27 experiments only |

## 26.16.1 highlights

- squirrel: elevate.exe `appOutDir` race fix
- mac: keychain password for `set-key-partition-list`; keep Electron/Chromium license files
- win: only log signtool when signing actually runs
- fix: prevent infinite recursion when a package depends on itself

## Cam wiring

- Config: [`electron-builder.json`](electron-builder.json)
- Consumer shell: `integrations/illa-desktop`
- Check: `python3 scripts/illa-electron-check.py`
- Coding workspace id: `electron-builder`

## Boundaries

- Do not bump ILLA desktop to `^27` / fork `master` without an explicit Aaron migrate task.
- VoiceStudio currently uses `electron-builder ^26.15.3` — prefer aligning to **26.16.1** on the next VoiceStudio packaging pass.
- Cline may edit packaging configs; live publish/signing stays Aaron-gated.
