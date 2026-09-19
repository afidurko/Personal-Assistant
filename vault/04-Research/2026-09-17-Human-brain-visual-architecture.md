# Research Brief — Human brain visual architecture for Cam

**Date:** 2026-09-17  
**Question:** How do we turn Cam’s live connectome UI into something that *looks and behaves* like a human brain?  
**Full plan:** `docs/HUMAN_BRAIN_UI_PLAN.md`

## Current Cam visuals

- **React `BrainMap`:** SVG cartoon silhouette + graph nodes — readable ops map, weak anatomy.
- **`cortex3d`:** Strong DTI fasciculus metaphor + live-activity feed, but areas are **spheres** inside a fiber cloud — not a cortical organ.
- **Configs already human:** Brodmann areas, columns-as-neurons, association tracts (`areas.json` / vault Brodmann remap).

## How serious web brains are built

1. **Cortical mesh** from FreeSurfer (fsaverage pial) with sulci/gyri.
2. **Parcellation** (Desikan–Killiany / Destrieux / Brodmann annot) for pickable ROIs.
3. **Bake to GLB** for Three.js (~1–2 MB with parcel merge) — see brain-for-web `freesurfer-to-glb` with custom region maps.
4. **Activity as surface heat** (Pycortex pattern): ROI/vertex intensity over time, not floating markers alone.
5. **Tracts inside translucent cortex** in one RAS coordinate frame (Fiberweb / Neurotract / threeBrain).

## Asset options

| Asset | License / notes | Fit |
|---|---|---|
| FreeSurfer → Cam-mapped GLB | Attribute FreeSurfer / Brainder | Best: pickable Cam `area.*` |
| NIH HRA brain male/female GLB | CC BY 4.0 | Fast silhouette / fallback LOD |
| Procedural gyral ellipsoid | none | Fail-soft only |

## Cam-specific mapping

Collapse DK parcels → Cam areas (DLPFC, Broca, Wernicke, MTL, …) via `anatomy-region-map.json`. Drive heat from `live-activity.json` + mesh WebSocket. Keep DTI RGB + pulse semantics already in `cortex3d.js`.

## Recommended sequence

1. Anatomical shell registered to tracts (visual win).  
2. Parcel heat + agent fly-to (live brain).  
3. Promote into React hero; SVG becomes a11y/fallback.  
4. Optional inflate / subcortical glass / real streamlines.

## Stance

Cam remains an inspectable ops connectome with Aaron as sole task-giver — not a clinical neuroimaging product. Prefer readable Cam parcels over full atlas density in the default view.

## Key links

- [FreeSurfer CorticalParcellation](https://surfer.nmr.mgh.harvard.edu/fswiki/CorticalParcellation)
- [brain-for-web](https://github.com/mpatricny/brain-for-web)
- [BrainBrowser](https://brainbrowser.cbrain.mcgill.ca/)
- [Pycortex](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2015.00023/full)
- [NIH 3D brain-male](https://3d.nih.gov/entries/3DPX-020960)
- [Fiberweb](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2017.00054/full)
