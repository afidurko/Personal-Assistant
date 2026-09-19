# Suggestive implementations — glass cortex QA cycle

**After:** merge-prep dual 1B (seeds 601/701)  
**Date:** 2026-09-19

## Applied (round 1)

1. **`scripts/connectome-anatomy-check.py`** — Brodmann map + GLB gate  
2. **CI wire** — `ci-connectome.sh` runs anatomy check  
3. **Unit tests** — `AnatomyCortexTests`  
4. **Centroid sync** — `cortex3d.js` boots from `anatomy-centroids.json`

## Applied (round 2)

5. **`scripts/merge-prep-billion.sh`** — one-shot static gates + 2×1B + combined evidence + `MERGE_READINESS_BILLION.md`  
6. **`serve-connectome-viz.sh`** — explicit repo-root URLs for GLB + live-activity  
7. **Lobe color sync** — `anatomy-centroids.json` `lobe_colors` passed into glass materials at boot  
8. **Tests** — merge-prep script + serve-viz contract coverage (21 unit tests)

## Applied (round 3 — Phase C)

9. **React hero `CortexStage`** — full-bleed glass cortex in `App.tsx` with Glass toggle + 2D map fallback  
10. **`src/lib/cortexGlass.ts`** — shared Three.js glass loader + hero tracts  
11. **`public/cortex/`** — Vite-served GLB / centroids / live-activity mirror; anatomy check enforces mirror  
12. **Brand-first hero** — Cam name as primary signal over the organ

## Still suggested (not blocking merge)

- Optional inflate morph / subcortical explode for pedagogy  
- Compress `cam-cortex.glb` with Draco if asset budget tightens  
- Nightly: `qa-loop.py --n 1000000000 --cycles 1`  
- Wire live-activity.json copy into standing scan so React hero stays fresh without manual cp
