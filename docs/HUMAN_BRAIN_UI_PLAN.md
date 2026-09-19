# Cam Human Brain UI — Massive Visualization Update Plan

**Status:** Phase A + B implemented (anatomical GLB shell + live parcel heat on connectome 3D). Phase C partial (2D silhouette + layout anchors).  
**Goal:** Make Cam’s live brain visualization read as a **human brain** — sulci/gyri silhouette, lobular anatomy, Brodmann areas, association tracts — while live agents/tasks still light activity in real time.  
**Operator:** Aaron only · Connectome configs stay source of truth.

### Implemented now

- `visualizations/connectome/assets/cam-cortex.glb` — Cam-mapped DK cortical/subcortical shell (CC BY-SA 3.0)
- `config/connectome/anatomy-region-map.json` + `anatomy-centroids.json`
- `cortex-anatomy.js` + `cortex3d.js` — load shell, bilateral mirror, parcel heat, click-to-focus, agent fly-to
- Tracts re-anchored to FreeSurfer-like RAS centroids matching the mesh
- React `BrainMap` left-lateral silhouette + `brain-map-layout` anchors updated
- **Phase C:** React hero `CortexStage` (`src/components/CortexStage.tsx`) — full-bleed glass cortex with Glass toggle + 2D map fallback; assets under `public/cortex/`

Regenerate mesh: `bash scripts/build-cam-cortex-glb.sh` (see `assets/NOTICE.md`).

---

## 1. What we have today

Cam already has two brain UIs plus a layout helper. None yet present a convincing anatomical human brain.

| Surface | Path | Visual language | Live activity |
|---|---|---|---|
| React mesh map | `src/components/BrainMap.tsx` | Flat SVG “soft brain” silhouette + node/edge graph | WebSocket mesh store (status colors, scanning pulse) |
| Region layout | `server/core/brain-map-layout.ts` | Normalized oval anchors (`prefrontal`, `mtl`, …) | Feeds BrainMap node placement |
| Connectome 3D | `visualizations/connectome/cortex3d.js` | DTI-style RGB fiber bundles + **sphere** area markers (no cortical mesh) | Polls `vault/10-Mesh-Distillates/live-activity.json` |
| Connectome 2D | `visualizations/connectome/flat.js` | Schematic Brodmann dots on a flat map | Simulated / shared event tape |

**Gap:** `cortex3d` already speaks the right *science* (Catani AF, Yeh systems, DTI RGB, live agents) but the volume reads as a **fiber cloud with floating balls**, not a human brain. `BrainMap` reads as a **dashboard graph inside a cartoon outline**.

**Strength to keep:** Brodmann/area → column → tract mapping in `config/connectome/` is already human-cortex aligned (`docs/CONNECTOME_ARCHITECTURE.md`, vault Brodmann remap). The UI should **visualize** that architecture, not invent a second map.

---

## 2. Research summary — how to make it look human

### 2.1 Anatomical cortical surface (the “looks like a brain” layer)

Industry practice for web brains:

1. **FreeSurfer / fsaverage cortical mesh** — pial or inflated surface with real sulci/gyri.  
2. **Parcellation annotations** — Desikan–Killiany (`aparc`), Destrieux (`aparc.a2009s`), or Brodmann annots for clickable ROIs.  
3. **Export to web formats** — GLB/glTF (best for Three.js), GIfTI, or Wavefront OBJ.  
4. **Ready pipelines:**
   - [brain-for-web](https://github.com/mpatricny/brain-for-web) — `freesurfer-to-glb` → ~1–2 MB Desikan atlas GLB + React Three Fiber viewer (`react-brain-atlas`).
   - [BrainBrowser](https://brainbrowser.cbrain.mcgill.ca/) — Three.js surface viewer; FreeSurfer/GIfTI/MNI OBJ; vertex overlays.
   - [neuroviz](https://github.com/mayu888/neuroviz) — Three.js GIfTI/FreeSurfer/NIfTI with overlay colormaps.
   - [ReconstructionSuite](https://github.com/cronelab/ReconstructionSuite) — FreeSurfer → GLB with gyri + subcortical aseg + R3F.

**Recommended Cam path:** bake a **Cam-region-mapped GLB** (custom region map collapsing DK parcels → Cam `area.*` IDs) via `freesurfer-to-glb --region-map`, vendor under `visualizations/connectome/assets/` (~1–2 MB). License/attribute FreeSurfer / Brainder / atlas sources in README.

**Artistic alternative (faster silhouette, less science):** NIH Human Reference Atlas brain organs ([brain-male](https://3d.nih.gov/entries/3DPX-020960) / female, CC BY 4.0, Allen-based GLB). Good for presence; weaker for Brodmann parcel picking — use as shell or fallback LOD.

### 2.2 Live activity on cortex (the “thinking” layer)

fMRI-style surface mapping patterns (esp. [Pycortex](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2015.00023/full)):

| Technique | Cam mapping |
|---|---|
| Vertex / ROI heatmap intensity | `areaActivity[area.id]` from live agents |
| Temporal playback | Existing plasticity scrubber + event tape |
| Colormap | Idle cool tissue → teal/cyan for healthy fire → gold for Aaron/priority → coral for QA/kill errors |
| Inflate morph (optional later) | Folded ↔ inflated slider for pedagogy |
| Semi-transparent cortex | See tracts *inside* the shell |

**Shader plan:** custom `ShaderMaterial` (or MeshStandard + vertex colors) with:

- base albedo = anatomical / lobe tint  
- `uActivity` per-region (uniform atlas or vertex attribute from parcel ID)  
- emissive pulse + Fresnel rim when lit  
- optional noise “microcolumn glitter” driven by `neuron.*` column counts  

Do **not** paint activity only on spheres; paint the **cortical patch** that owns the area.

### 2.3 White-matter / DTI inside the shell (keep what works)

Current `cortex3d` fasciculi (arcuate, SLF, uncinate, cingulum, IFOF, ILF, forceps, CST…) are the right metaphor. Upgrade rules from Fiberweb / Neurotract / threeBrain practice:

1. **One coordinate frame** — place Cam area anchors in **RAS-like** space matching the mesh (not ad-hoc `[-2..2]` then hope).  
2. **Register tracts to mesh** — scale fiber midpoints so they sit *under* cortex; inset ~0.85 of surface AABB (Neurotract pattern).  
3. **LOD** — keep existing high/low fiber budgets; on mobile drop ambient U-fibers first.  
4. **Hybrid render** — translucent cortical shell + additive DTI lines + pulse sprites along active tracts (already implemented).  
5. Later optional: real streamline files (`.tck`/`.trk`) for showcase mode — **not** required for Cam ops UI.

### 2.4 Hemispheres, lobes, deep structures

| Layer | Visual role | Cam data |
|---|---|---|
| Left / right hemispheres | Default left-dominant language (Broca/Wernicke); mirror right for commissural / workspace sync | `tract.forceps_*`, callosal bridge |
| Lobes (frontal, parietal, temporal, occipital, limbic) | Soft color bands at rest | `areas.json` → `lobe` field |
| Subcortical (MTL, basal ganglia analogs) | Smaller inner meshes or glass volumes | `area.mtl`, switches ≈ BG |
| Cerebellum / brainstem silhouette | Completes “human brain” read; low interaction | Decorative + descending CST visual |

### 2.5 2D companion (BrainMap) should match anatomy

Replace the hand-drawn `BRAIN_PATH` with either:

- **Sagittal / lateral orthographic** render of the same GLB (one shared anatomy), or  
- High-quality SVG traced from a lateral fsaverage outline with **lobe paths** and area hit-targets at true relative positions from `REGION_ANCHORS` remapped to DK centroids.

Node kinds stay: workspaces, agents, concepts — but they **dock into anatomical regions**, not float in a graph oval.

---

## 3. Target visual architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  Cam Cortex Stage (full-bleed, brand-first)                 │
│  ┌───────────────────────────────────────┐ ┌──────────────┐ │
│  │  Anatomical brain (GLB shell)         │ │ Live agents  │ │
│  │   · sulci/gyri mesh                   │ │ Tract weights│ │
│  │   · Cam area parcels (pickable)       │ │ Time tape    │ │
│  │   · activity heat + column glitter    │ │ Kill / auto  │ │
│  │   · DTI fasciculi (RGB + pulse)       │ └──────────────┘ │
│  │   · orbit · Cor/Ax/Sag · LOD          │                  │
│  └───────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

**Composition rules (product UI):**

- First viewport = **one composition**: Cam brand + one line (“live cortex”) + the brain. No dashboard chrome in the hero.  
- Side panels are secondary; they must not compete with the organ.  
- Motion budget: (1) ambient gyral breathing / light sweep, (2) tract pulses on fire, (3) area emissive bloom on agent start/stop.  
- Avoid purple-glow / cream-terracotta AI-default looks; stay on Cam’s teal–sand–ink connectome palette (`visualizations/connectome/styles.css`).

---

## 4. Cam area → anatomy mapping (implementation table)

Use Desikan–Killiany (or Destrieux) parcels collapsed into Cam areas via a JSON region map:

| Cam `area.*` | Brodmann | Primary DK / anatomical anchors | Lobe tint |
|---|---|---|---|
| `area.dlpfc` | BA9/46 | superiorfrontal, rostralmiddlefrontal | frontal |
| `area.apfc` | BA10 | frontalpole, rostralmiddlefrontal (ant.) | frontal |
| `area.ofc` | BA11/12 | lateralorbitofrontal, medialorbitofrontal | frontal |
| `area.broca` | BA44/45 | parsopercularis, parstriangularis | frontal |
| `area.premotor` / `area.motor` | BA6 / BA4 | caudalmiddlefrontal, precentral | frontal |
| `area.parietal` | BA5/7 | superiorparietal, inferiorparietal | parietal |
| `area.wernicke` | BA22+ | bankssts, supramarginal, inferiorparietal (post.) | temporoparietal |
| `area.temporal` | BA20/21/37 | middletemporal, inferiortemporal, fusiform | temporal |
| `area.auditory` | BA41/42 | transverse temporal, superior temporal | temporal |
| `area.visual` | BA17–19 | lateraloccipital, cuneus, pericalcarine, lingual | occipital |
| `area.cingulate` | BA24/32 | caudal/rostral anterior cingulate, PCC | limbic |
| `area.mtl` | memory | hippocampus, entorhinal, parahippocampal (aseg + medial) | limbic |

**File to add:** `config/connectome/anatomy-region-map.json` — DK parcel → `area.*`, centroid RAS, hemisphere policy.

**Layout migration:** replace ad-hoc `AREAS[].p` in `cortex3d.js` and `REGION_ANCHORS` in `brain-map-layout.ts` with centroids derived from the same map (single source of truth).

---

## 5. Live activity wiring

Keep the existing feed; enrich the visual binding.

| Source | Today | Target binding |
|---|---|---|
| `live-activity.json` | Lights tracts + sphere areas | Lights **parcel materials** + tracts + column particles |
| Mesh WebSocket (`useMeshStore`) | BrainMap node statuses | Drive same activity bus when React hosts 3D |
| Agent / task list | Sidebar chips | Hover → fly-to area + highlight system fasciculi |
| Plasticity scrubber | Event replay | Replay heats cortex historically (Pycortex-style time series) |
| Health / kill | Coral errors | Surface flash + tract dim |

**Activity bus shape (proposed):**

```ts
type CortexActivity = {
  areas: Record<string, number>;      // 0..1
  tracts: Record<string, number>;     // 0..1
  neurons: Record<string, number>;    // column glitter
  systems?: string | null;            // e.g. arcuate_language
  priority?: "aaron" | "health" | "normal";
};
```

Both React and static viz subscribe; no second semantics.

---

## 6. Phased delivery (technical, not calendar)

### Phase A — Anatomical shell (biggest visual win)

- Vendor Cam-mapped cortical GLB (+ attribution).  
- Load in `cortex3d` with translucent material; hide or demote area spheres to pick proxies.  
- Re-anchor `AREAS` to mesh centroids; re-fit tracts.  
- Cor / Ax / Sag presets remain; default camera = ¾ anterolateral human portrait angle.

**Exit check:** freeze-frame screenshot is unmistakably a human brain even with fibers off.

### Phase B — Parcel interactivity + live heat

- Raycast parcels → `area.*`.  
- Activity shader / vertex colors from live feed.  
- Column glitter for `neuron.*` inside lit areas.  
- Sidebar “Live agents” click → camera fly-to + system highlight.

**Exit check:** firing `neuron.chief` visibly warms DLPFC patch and brightens SLF/arcuate as today.

### Phase C — Unify React app hero

- Embed cortex viewer in `App.tsx` hero (R3F or iframe/module of shared package).  
- Retire SVG silhouette as primary; keep flat SVG as accessibility / print fallback (`flat.html` pattern).  
- `brain-map-layout.ts` reads anatomy centroids.  
- Hero composition: **Cam** brand dominant, one headline, brain full-bleed behind/ beside — not a card grid.

**Exit check:** Personal-Assistant home and connectome viz share one organ.

### Phase D — Depth & pedagogy (optional)

- Inflate morph; lobe explode; left/right isolate.  
- Subcortical glass (MTL, switch/BG analogs).  
- Optional real DTI showcase mode.  
- Swift Guide tour steps anchored to anatomical fly-tos.

---

## 7. Tech choices (recommended stack)

| Concern | Choice | Why |
|---|---|---|
| Runtime | Keep **Three.js r160** (already in connectome); add **R3F** only if React hero needs it | Minimal churn |
| Asset | Custom GLB via FreeSurfer→GLB + Cam region map | Scientific + pickable + small |
| Fallback LOD | NIH HRA brain GLB or procedural ellipsoid with gyral noise | Offline / fail-soft |
| Materials | Translucent physical cortex + additive tracts | Hybrid DTI + anatomy |
| State | Shared `CortexActivity` from live-activity + mesh socket | One brain bus |
| Perf | Existing LOD toggle; parcel merge; max ~60fps on laptop; mobile fiber budget ≤280 ambient | Already started |
| A11y | Flat 2D map + text agent list always available | Orbit-only is not enough |

**Avoid:** shipping multi-hundred-MB FreeSurfer subjects into the repo; baking once to GLB is enough.

---

## 8. File / module impact map

| Path | Change |
|---|---|
| `visualizations/connectome/assets/cam-cortex.glb` | **New** anatomical asset |
| `config/connectome/anatomy-region-map.json` | **New** DK→Cam map + centroids |
| `visualizations/connectome/cortex3d.js` | Mesh load, shaders, re-anchor, pick |
| `visualizations/connectome/styles.css` | Full-bleed stage; thinner side chrome |
| `visualizations/connectome/index.html` | Copy: “human cortex · live agents” |
| `src/components/BrainMap.tsx` → `CortexStage.tsx` | Phase C hero replacement |
| `server/core/brain-map-layout.ts` | Centroids from anatomy map |
| `docs/CONNECTOME_ARCHITECTURE.md` | Link this plan |
| `vault/04-Research/2026-09-17-Human-brain-visual-architecture.md` | Research brief |

---

## 9. Risks & constraints

- **License / attribution** — FreeSurfer tools, Brainder meshes, NIH HRA (CC BY 4.0): keep NOTICE file next to assets.  
- **Coordinate drift** — worst failure mode is pretty mesh with tracts floating outside; lock one RAS space in Phase A.  
- **Over-medicalization** — Cam is an ops connectome, not a clinical viewer; prefer readable parcels over full Destrieux density in the default view.  
- **Perf on mobile** — shell + heat first; dense ambient fibers optional.  
- **Authority** — no outbound messaging or self-apply of Cam functionality from viz; Aaron remains sole task-giver (existing chips).

---

## 10. Decision ask (for Aaron)

Recommended default: **Phase A + B on connectome 3D first** (anatomical GLB + live parcel heat), then Phase C to promote it into the React hero.

Alternatives if Aaron prefers differently:

1. **Art-first** — NIH HRA shell only, keep sphere/tract logic (faster, less pick precision).  
2. **Science-first** — full FreeSurfer annot + Pycortex-like inflate before React integration.  
3. **2D-first** — redesign BrainMap SVG from true lateral outline before 3D mesh work.

---

## Sources

- Cam: `docs/CONNECTOME_ARCHITECTURE.md`, `config/connectome/areas.json`, `visualizations/connectome/cortex3d.js`, `src/components/BrainMap.tsx`  
- FreeSurfer cortical parcellation — [wiki](https://surfer.nmr.mgh.harvard.edu/fswiki/CorticalParcellation)  
- brain-for-web / freesurfer-to-glb — [GitHub](https://github.com/mpatricny/brain-for-web)  
- BrainBrowser — [McGill](https://brainbrowser.cbrain.mcgill.ca/)  
- Pycortex surface viz — [Frontiers 2015](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2015.00023/full)  
- NIH HRA brain GLB (CC BY 4.0) — [3DPX-020960](https://3d.nih.gov/entries/3DPX-020960) · [humanatlas.io](https://humanatlas.io/3d-reference-library)  
- Fiberweb / browser DTI — [Frontiers 2017](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2017.00054/full)  
- Neurotract hybrid mesh+streamlines — [GitHub](https://github.com/sailwalpranjal/Neurotract)
