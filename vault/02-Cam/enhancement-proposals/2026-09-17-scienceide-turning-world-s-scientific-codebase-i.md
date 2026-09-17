# Enhancement proposal — ScienceIDE: Turning World's Scientific Codebase into Agent Learnable Environments

**Status:** propose_only (awaiting Aaron / `switch.cam_enhance`)
**Date:** 2026-09-17
**Source:** [http://arxiv.org/abs/2609.19134v1](http://arxiv.org/abs/2609.19134v1)
**Relevance:** 6 — {'enhance_cam_routing': 3, 'enhance_memory_mesh': 3, 'enhance_presence_voice': 0, 'enhance_vision': 0, 'enhance_slm_local': 0, 'enhance_dl_embeddings': 0, 'general_agi_theory': 0}

## Suggested Cam touchpoints

- `center.capability`
- `center.info`
- `center.memory`
- `center.router`
- `config/roles`
- `smart-second-brain`

## Why it might enhance Cam

Scientific code repositories encode decades of human knowledge in executable models, methods, and tools. Yet fragmented toolchains, implicit domain conventions, and specialized correctness criteria make this knowledge difficult to convert into reliable learning experience-a challenge we call the scientific experience bottleneck. We introduce ScienceIDE, infrastructure for turning the world's scientific code into programmable environments for scientific agents. Guided by expert-defined scientific cases and acceptance criteria, agents transform repositories into executable environments that support task generation, execution, and scientific verification. These environments provide a shared foundation for supervised fine-tuning, reinforcement learning, and evaluation. Using verified interacti

## Apply gate

1. QA cite-check
2. Aaron approve via `config/pipelines/cam-enhance-gate.json`
3. capability-broker applies with implementer subagents
4. `python3 scripts/connectome-check.py`
