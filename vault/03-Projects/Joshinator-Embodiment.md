# Joshinator 3D embodiment (IP-safe)

**Date:** 2026-09-19  
**Target upstream:** https://github.com/afidurko/joshinator-analyzer  
**Local mirror:** `integrations/joshinator-analyzer`  
**Upstream branch (local only):** `cursor/card-embodiment-3d-b576` (push blocked — Cursor bot 403)

## What shipped

Detect → identify → original procedural 3D spawn:

- `embodiment_catalog.py` — original archetypes only  
- `embodiment_service.py` — card_info → spawn payload  
- Socket.IO `analysis_result.embodiment`  
- REST `GET /api/embodiment/catalog`, `POST /api/embodiment/resolve`  
- `EmbodimentViewer` (Three.js primitives, no GLTF franchise assets)  
- Docs: `docs/EMBODIMENT.md`

## Copyright stance

No Pokémon / Nintendo / team-logo / manufacturer character meshes. Procedural geometry + original names only.

## Next for Aaron

1. Grant Cursor write access to `afidurko/joshinator-analyzer`  
2. Push `cursor/card-embodiment-3d-b576` from the local clone at `/workspace/joshinator-analyzer` (or re-run agent)  
3. Open upstream PR; keep this PA mirror in sync or convert to submodule
