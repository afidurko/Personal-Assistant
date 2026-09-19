# Enhancement proposal — Compositional Policy Violations: When Step-Level Compliance Fails In Agentic AI Workflows

**Status:** applied (Aaron approved 2026-09-17 · `switch.cam_enhance` for this batch)
**Date:** 2026-09-17
**Source:** [http://arxiv.org/abs/2609.18820v1](http://arxiv.org/abs/2609.18820v1)
**Relevance:** 5 — {'enhance_cam_routing': 3, 'enhance_memory_mesh': 0, 'enhance_presence_voice': 0, 'enhance_vision': 2, 'enhance_slm_local': 0, 'enhance_dl_embeddings': 0, 'general_agi_theory': 0}

## Suggested Cam touchpoints

- `center.capability`
- `center.dl`
- `center.router`
- `center.vision`
- `config/roles`

## Why it might enhance Cam

Agentic workflows now make consequential decisions in regulated settings, and the governance placed around them is almost entirely step-scoped: input-output classifiers, per turn rails, and span-level evaluators. The policies organizations actually hold, such as referral thresholds, authority limits, and review requirements, are properties of the whole execution rather than of any one step. This mismatch admits a failure mode we call a Compositional Policy Violation (CPV): every individual step passes its own check while the composed execution violates the governing policy. A predicate over a single step cannot evaluate a property that step does not determine, so no improvement in the accuracy of the step-scoped monitors detects this class. We define CPVs as the failure of step-level compl

## Apply gate

1. QA cite-check
2. Aaron approve via `config/pipelines/cam-enhance-gate.json`
3. capability-broker applies with implementer subagents
4. `python3 scripts/connectome-check.py`


## Apply record

- **BATCH APPLIED** by Aaron 2026-09-17 via `scripts/apply-cam-enhancements.py`
- Implementer: Cam capability-broker (this checkout)
