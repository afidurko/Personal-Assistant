# ILLA Builder desktop (electron-builder@26.16.1)

## Status: promoted

Desktop shell lives in the fork:

- Branch: `cursor/desktop-electron-26-16-1`
- Path: `electron/`
- Base: `beta`
- Compare: https://github.com/afidurko/illa-builder/compare/beta...cursor/desktop-electron-26-16-1?expand=1
- Pin: **electron-builder@26.16.1**

Cam still keeps `integrations/illa-desktop` as a mirror/staging copy + check/promote scripts.

### Verify on the fork

```bash
pnpm dev
npm --prefix electron install
npm --prefix electron run check:pin
npm --prefix electron run dist:dir
```

### Security

Any PAT pasted into chat must be **revoked** immediately at https://github.com/settings/personal-access-tokens
