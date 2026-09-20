# ILLA desktop — three-trillion QA suggestions

Protocol: Aaron **test** (3T → fix → suggest → 3T)

## Fixes applied

1. **Offline HTML XSS** — `offlineHtml` previously stripped `<>&"` instead of entity-escaping; injected details could break markup. Fixed via `escapeHtml` in `src/url-contract.js`.
2. **Deb maintainer** — require `author.email` + `build.linux.maintainer` in pin assert (electron-builder needs them for `.deb`).
3. **Testable contract** — extracted pure `url-contract.js` + `contract-selftest.js` + `illa-desktop-billion-fuzz.py` (3T modular scale).
4. **higgsfield-check** — empty submodule dry-run failures are soft warnings so offline Cam 3T gates stay green without `git submodule update`.
5. Synced contract hardening to `afidurko/illa-builder` (PR #3).

## Standing suggestions (add-ons)

- Bundle a real 256×256+ icon (current favicon copy is tiny) before public dist.
- Set `desktopName` / WM_CLASS once electron-builder schema for v26 documents the linux field path (build warned without it).
- Add CI job on `illa-builder`: `npm --prefix electron ci && npm --prefix electron run check:pin && npm --prefix electron run test:contract && npm --prefix electron run dist:dir`.
- Wire `ILLA_DESKTOP_URL` discovery from turbo/vite port in a small `desktop:dev` compositor script.
- Promote Cam staging `integrations/illa-desktop` to a thin mirror that pulls from fork `electron/` (avoid drift).
- Optional: signed updates (electron-updater) only after code-signing certs exist — keep publish gated.
- Init `integrations/higgsfield` submodule on build agents that need live Higgsfield doctor green (not required for ILLA packaging).
- Keep pin **exact** `26.16.1`; do not float to fork `master` (v27 alpha).

## Commands

```bash
python3 scripts/test_illa_desktop.py
python3 scripts/illa-desktop-billion-fuzz.py --n 3000000000000
python3 scripts/three-trillion-campaign.py --passes 2
```
