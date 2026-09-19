# Suggestive implementations — Joshinator embodiment dual-billion QA

**Authorized:** Aaron · **Date:** 2026-09-19  
**After:** connectome 1B pass A green (`20260919T194709Z-cycle-01`)

## Shipped this cycle

1. **Vision traffic weight** — `sense.vision.detection` = 2.0 (+ `sense.ios.camera` 1.2) so card-analyze → embodiment shows up in fuzz mix.
2. **Health pulse** — `system-health-scan.py` expects vendored `integrations/joshinator-analyzer` + config policy.
3. **Suggestive kind `card-embodiment`** — mesh suggestions push IP-safe procedural spawn + embodiment fuzz (`shared/types.ts` + `server/core/suggestions.ts`).
4. **CI gate** — `ci-connectome.sh` runs embodiment unit tests + 1M `embodiment-billion-fuzz.py`.
5. **`scripts/embodiment-billion-fuzz.py`** — billion-scale IP/stability invariants for resolve payloads.
6. **QA standing suggestions** — dual-billion + never load franchise GLTF packs.

## Still standing (not blockers)

- Empty git submodules in cloud checkout (soft warning) — expected.
- Upstream push to `afidurko/joshinator-analyzer` blocked (Cursor bot 403) — grant write access.
- Live Null stack ticket binding for Cline runs.
