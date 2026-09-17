# Enhancement proposal — Cognitive Extensions for Dual-Process Language Agents: Memory and Self-Reflection in Interactive Environments

**Status:** applied (Aaron approved 2026-09-17 · `switch.cam_enhance` for this batch)
**Date:** 2026-09-17
**Source:** [http://arxiv.org/abs/2609.19128v1](http://arxiv.org/abs/2609.19128v1)
**Relevance:** 6 — {'enhance_cam_routing': 3, 'enhance_memory_mesh': 3, 'enhance_presence_voice': 0, 'enhance_vision': 0, 'enhance_slm_local': 0, 'enhance_dl_embeddings': 0, 'general_agi_theory': 0}

## Suggested Cam touchpoints

- `center.capability`
- `center.info`
- `center.memory`
- `center.router`
- `config/roles`
- `smart-second-brain`

## Why it might enhance Cam

Language agents remain brittle in interactive environments, where success requires long-horizon state tracking, valid action execution, and recovery from failed steps. We extend SwiftSage, a dual-process agent that combines a fast action proposer with a slower planner, using two modular cognitive extensions: an Adaptive Memory Module (AMM) for salience-gated episodic storage and trigger-driven retrieval, and a Self-Reflection Module (SRM) for bounded execution-time validation and corrective intervention. Both modules are implemented as feature-flagged extensions over the same execution substrate, enabling controlled ablations on ScienceWorld. Across four configurations---baseline, baseline+AMM, baseline+SRM, and the full system---the full system achieves the best mean final score (64.62), 

## Apply gate

1. QA cite-check
2. Aaron approve via `config/pipelines/cam-enhance-gate.json`
3. capability-broker applies with implementer subagents
4. `python3 scripts/connectome-check.py`


## Apply record

- **BATCH APPLIED** by Aaron 2026-09-17 via `scripts/apply-cam-enhancements.py`
- Implementer: Cam capability-broker (this checkout)
