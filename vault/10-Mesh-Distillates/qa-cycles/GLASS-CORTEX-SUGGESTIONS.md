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

## Still suggested (not blocking merge)

- Embed glass cortex into React `App` hero (Phase C of HUMAN_BRAIN_UI_PLAN)  
- Optional inflate morph / subcortical explode for pedagogy  
- Compress `cam-cortex.glb` with Draco if asset budget tightens  
- Nightly: `qa-loop.py --n 1000000000 --cycles 1`
