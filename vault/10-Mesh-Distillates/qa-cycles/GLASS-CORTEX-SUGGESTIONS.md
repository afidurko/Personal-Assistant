# Suggestive implementations — glass cortex QA cycle

**After:** 1B pass1 (`connectome-sim-1b-glass-pass1.json`) — 1e9 / 0 failed  
**Date:** 2026-09-19

## Applied

1. **`scripts/connectome-anatomy-check.py`** — gate that every Brodmann `area.*` is mapped, centroids exist, and `cam-cortex.glb` + NOTICE ship with the repo.
2. **CI wire** — `ci-connectome.sh` runs anatomy check before unit tests.
3. **Unit tests** — `AnatomyCortexTests` in `test_cline_workspaces.py` (map coverage, glass modules, anatomy check script).
4. **Centroid sync** — `cortex3d.js` boots from `anatomy-centroids.json` before shell load so tracts stay registered when the map changes.

## Still suggested (not blocking merge)

- Embed glass cortex into React `App` hero (Phase C of HUMAN_BRAIN_UI_PLAN).
- Optional inflate morph / subcortical explode for pedagogy.
- Compress `cam-cortex.glb` with Draco if asset budget tightens.
- Nightly: `qa-loop.py --n 1000000000 --cycles 1` remains the standing watch.
