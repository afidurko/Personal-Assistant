# Cam Brodmann cortex remap

Research brief for remapping Cam’s connectome from fly-CNS analogy alone into a
**human Brodmann functional cortex** where **agents and repetitive loops are cortical
columns**, and the **neural mesh is association-fiber coupling**.

## Literature (selected)

1. **Brodmann areas** — cytoarchitectonic map still used as functional nomenclature
   (Radiopaedia; Kenhub summaries). Key Cam anchors:
   - BA9/46 DLPFC — executive / working memory → `area.dlpfc` (chief, router)
   - BA10 aPFC — prospective memory / abstract planning → `area.apfc` (cartography, docs)
   - BA11 OFC — valuation / boundaries → `area.ofc`
   - BA44/45 Broca — production → `area.broca` (comms, speak loop)
   - BA22/39/40 Wernicke+ — comprehension → `area.wernicke`
   - BA5/7 parietal association — spatial-temporal ops → `area.parietal`
   - BA20/21/37 temporal association — research/careers → `area.temporal`
   - BA17–19 visual → `area.visual`
   - BA41/42 auditory → `area.auditory`
   - BA24/32 cingulate — conflict monitoring → `area.cingulate` (QA loops)
   - MTL/hippocampal-adjacent — engrams → `area.mtl`

2. **Association cortex flexibility** — Yeo / Yeo-style association networks: specialized
   regions couple into flexible frontal–parietal binders
   ([PMC4598819](https://pmc.ncbi.nlm.nih.gov/articles/PMC4598819/)).

3. **Structural ↔ functional mesh** — Jung et al.: dense graded *intra*-lobe links vs
   discrete *inter*-lobe tracts that mirror functional networks
   ([PMC5726605](https://pmc.ncbi.nlm.nih.gov/articles/PMC5726605/)).
   Major tracts Cam maps: arcuate, SLF, uncinate, cingulum, ILF, IFOF, thalamocortical,
   corticospinal, plus callosal-like `mesh/*` coherence.

4. **Columns as agents/loops** — Mountcastle cortical column; Hawkins Thousand Brains /
   STAM: recurrent columnar modules with local loops and long-range consensus.
   Cam: each role agent and each repetitive script (`qa-loop`, converse turn, careers
   watch, mesh sync) is a `neuron.*` column inside an area.

5. **Neural mesh models** — Syncytial / Brain-Mesh proposals add cross-area coherence
   beyond point synapses; Cam’s `mesh/*` + Hebbian tract weights are the software analog.

## Architecture files

- `config/connectome/areas.json` — Brodmann functional areas
- `config/connectome/neurons.json` — agents + loops as columns
- `config/connectome/tracts.json` — association fibers / mesh
- `config/connectome/hotspots.json` — pathways through areas
- Viz lenses: **Cortex** · Spinal · Mind map

## Rule kept

Aaron remains sole task-giver; OFC identity gate + kill switch still master motor silence.
