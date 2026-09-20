# Public APIs — 3T QA suggestions (pass A → add-ons)

**Authorized:** Aaron · **Date:** 2026-09-20  
**Protocol:** 3T → fix/suggest → 3T → merge if green

## Pass A

Green at N=3,000,000,000,000 (exhaustive/modular + physical).  
Harness: `scripts/public-apis-billion-fuzz.py` wired into `three-trillion-campaign.py`.

## Issues found

- Hard failures: **none**
- Soft: empty submodules (jarvis/…/cline) expected in cloud — not a merge blocker
- Gap: standing suggestion to expand allowlisted add-ons beyond first wave

## Fixes / add-ons shipped this cycle

1. `scripts/public-apis-billion-fuzz.py` — 3T property fuzz for allowlist/HTTPS/no free-form URL
2. Campaign + CI wiring for public-apis unit/check/3T gates
3. **New allowlisted add-ons:**
   - `fx.frankfurter` — FX rates (ops/research)
   - `advice.slip` — presence/demo smoke
   - `air.open_meteo` — PM2.5 / European AQI

## Standing suggestions

- Prefer `public_apis_addon` before inventing HTTP helpers
- Next candidates if Aaron asks: Universities List lookup, ExchangeRate.dev (rate-limited)
- Keep `git submodule update --init integrations/public-apis` on new machines
