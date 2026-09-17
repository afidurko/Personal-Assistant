# Enhancement proposal — ScienceBuddy: Recursive-in-Recursive Self-Improvement for Interactive Scientific Agents

**Status:** propose_only (awaiting Aaron / `switch.cam_enhance`)
**Date:** 2026-09-17
**Source:** [http://arxiv.org/abs/2609.17523v1](http://arxiv.org/abs/2609.17523v1)
**Relevance:** 6 — {'enhance_cam_routing': 3, 'enhance_memory_mesh': 3, 'enhance_presence_voice': 0, 'enhance_vision': 0, 'enhance_slm_local': 0, 'enhance_dl_embeddings': 0, 'general_agi_theory': 0}

## Suggested Cam touchpoints

- `center.capability`
- `center.info`
- `center.memory`
- `center.router`
- `config/roles`
- `smart-second-brain`

## Why it might enhance Cam

We introduce and release ScienceBuddy, an interactive scientific research workspace that brings continually improving scientific agents into researchers' everyday workflows. ScienceBuddy supports researchers in carrying out scientific tasks while transforming their requests, feedback, and execution evidence into tasks and evaluation rubrics for continual learning. At its core is recursive-in-recursive self-improvement, a paradigm that couples harness evolution with model reinforcement learning: the inner recursion improves the harness with the model fixed, while the outer recursion trains the model under the improved harness. Harness evolution shapes training experience, and model learning creates new opportunities for harness adaptation. We present case studies of researcher interaction, 

## Apply gate

1. QA cite-check
2. Aaron approve via `config/pipelines/cam-enhance-gate.json`
3. capability-broker applies with implementer subagents
4. `python3 scripts/connectome-check.py`
