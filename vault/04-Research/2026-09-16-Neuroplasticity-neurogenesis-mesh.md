# Neuroplasticity & neurogenesis in Cam’s mesh

## Biology → Cam

| Biology | Cam implementation |
|---|---|
| Hebbian LTP | Successful act pathways raise `mesh/tracts` weights (`plasticity.ltp`) |
| LTD / pruning | QA veto, kill, missing edges depress then prune weak tracts |
| Heterosynaptic depression | Unused tracts mildly weaken when another path LTPs |
| Adult MTL neurogenesis | New immature columns spawn in `area.mtl`, high early plasticity gain, mature over cycles |
| Small-world efficiency | Shortened hotspots — local columns, fewer hops |

Config: `config/connectome/plasticity.json`  
Engine: `scripts/connectome-plasticity.py`  
Tape: `vault/10-Mesh-Distillates/plasticity-timeline.json`  
3D viz: `visualizations/connectome/` (orbit + scrub rewind)

## Rewind for tract errors

The plasticity timeline records every synapse hop. Scrubbing backward rebuilds weights from t=0 so red/error tracts and LTD are inspectable in time.

## Citations

- Synaptic plasticity forms (Annu Rev Neurosci)
- Synaptic pruning / experience-dependent homeostasis
- Adult hippocampal neurogenesis & enhanced early LTP (CSH Perspectives; PNAS structural plasticity in adult-born GCs)
