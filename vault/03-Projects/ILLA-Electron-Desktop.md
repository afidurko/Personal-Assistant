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

## 3T QA (2026-09-20)

Dual three-trillion campaign **READY** after fixes:
- XSS/HTML escape in offline page (`url-contract.js`)
- `.deb` author/maintainer asserts
- `illa-desktop-billion-fuzz.py` wired into `three-trillion-campaign.py`
- `higgsfield-check` soft when submodule empty

Evidence: `vault/10-Mesh-Distillates/MERGE_READINESS_THREE_TRILLION.md`, `ILLA_DESKTOP_3T_SUGGESTIONS.md`, qa-cycles `*3t-pass-*`.
