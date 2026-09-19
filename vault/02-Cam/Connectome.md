# Cam Connectome

Cam’s architecture is a **Brodmann functional cortex**:

- Functional areas (`area.*`) instead of only fly-CNS centers
- **Agents and repetitive loops = cortical columns** (`neuron.*`)
- **Association tracts = neural mesh** (`tract.*` + `mesh/*`)
- Shared sensory periphery (arXiv/AGI feeds, daily clock, sLM/DL feedback, Cline results, public-apis catalog) + Aaron-flipped circuit switches
- Specialized hotspots (**coding**, **agi_scan**, **enhance**, **capability**, **info**, **slm**, **dl**, cartography, …)
- Circuit switches for antagonistic outcomes (`research_scan` vs pause; `cam_enhance` propose vs apply)
- Motor effectors that only fire on mapped **act** pathways (`cline`, `web_fetch`, `enhance`, `slm`, `dl`, …)

Docs: `docs/CONNECTOME_ARCHITECTURE.md` · `docs/CAM_BRAIN.md`  
Live viz: **3D** `visualizations/connectome/` (spin + rewind) · 2D `flat.html` (`bash scripts/serve-connectome-viz.sh`)  
Coding effector: Cline (`integrations/cline`) — shared by all agents & workspaces  
Free API catalog: public-apis (`integrations/public-apis`) — shared by all agents & workspaces  
Research: [[2026-09-16-Brodmann-neural-mesh-remap]] · [[2026-09-16-Neuroplasticity-neurogenesis-mesh]] · [[2026-09-16-SwiftGuide-brain-map]] · [[2026-09-16-Drosophila-male-CNS-connectome-Cell]] · [[AGI-Daily-Scan]]  
iOS stack: [[iOS-Companion-SwiftGuide-Stack]]
