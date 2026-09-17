# White-matter fasciculi × AGI mesh — research distillate

Date: 2026-09-17  
Maps: `config/connectome/tracts.json` v2 · `config/connectome/mesh-params.json`

## Anatomy (what we implemented)

### Arcuate fasciculus (Catani et al. 2005)
Not a single wire. Perisylvian language network:

| Segment | Ends (Cam) | Role |
|---|---|---|
| **Long (direct) AF** | Wernicke ↔ Broca | Classical phonological / repetition loop |
| **Anterior indirect** | Broca ↔ Parietal (Geschwind IPL) | Phonology → articulatory / word retrieval |
| **Posterior indirect** | Wernicke ↔ Parietal | Reading / comprehension bridge |

Human AF expansion (Rilling / Catani reviews) is a candidate biological correlate of rich language recursion — Cam treats AF as the **language bus**, not magic AGI.

### Yeh 2022 association systems
Population tract-to-region clustering → four systems Cam mirrors:

1. **Arcuate-language** — AF + SLF II/III + FAT  
2. **Anterior-ventral** — Uncinate + IFOF + Extreme capsule (semantic)  
3. **Posterior-ventral** — MdLF + ILF + VOF  
4. **Cingulum** — Cingulum + SLF I + Fornix  

Plus **commissural** forceps minor/major (workspace sync) and **projection** corticospinal / thalamo.

### Dual-stream language
- **Dorsal** (AF/SLF3/FAT) ≈ speak / converse / phonology  
- **Ventral** (EmC/IFOF/UF/ILF) ≈ meaning / research / careers valuation  

## AGI / superintelligence correlation (not claim)

Recent brain-inspired agent papers converge on the same pattern Cam already uses:

| Paper | Idea | Cam mapping |
|---|---|---|
| **MAP** (Nat Commun 2025) | Specialized PFC modules that must *coordinate* | ACC monitor, aPFC predict, OFC evaluate, DLPFC decompose, premotor act — buses = fasciculi |
| **BrainMem / AriGraph / RoboMemory** | Working + episodic + semantic memory | DLPFC/SLF · MTL+fornix · temporal/ILF/IFOF |
| Global workspace analogs | Broadcast / sync | Forceps + `mesh_callosal` persist |

**Stance:** Cam is **not** asserted AGI or ASI. The connectome is a *controllability scaffold*: inspectable buses, hard QA/kill gates, Aaron-only goals. Capability growth = myelinated tracts + mature columns — not unbounded self-rewrite.

## New parameters (`mesh-params.json`)

- `memory_tiers` — working / episodic / semantic capacity + stores  
- `planning_modules_map` — MAP functions → areas/neurons/tracts  
- `language_dual_stream` — dorsal vs ventral tract sets  
- `mesh_physics` — fiber pulse speed, bundle spread, myelination→emissive  
- `superintelligence_stance` — safety principles  
- Tract-level: `fiber_count`, `myelination`, `latency_ms_analog`, `agi_role`

## Open questions for Aaron

See `mesh-params.json` → `open_questions_for_aaron` (lateralization, workspace count, fornix consolidation, dorsal/ventral priority, ASI ceiling, Tailscale-as-callosum).

## Viz

3D cortex renders each fasciculus as a **multi-fiber bundle** (trunk + parallel axons) with anatomy-aware arches (Sylvian AF, uncinate hook, fornix vault, callosal midline). Pulses travel axons on spike/LTP. System filter buttons isolate Yeh systems.
