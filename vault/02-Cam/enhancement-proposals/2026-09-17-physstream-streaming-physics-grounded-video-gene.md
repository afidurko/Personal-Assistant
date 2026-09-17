# Enhancement proposal — PhysStream: Streaming Physics-Grounded Video Generation with Structured Scene Memory and Fine-Grained Motion Control

**Status:** propose_only (awaiting Aaron / `switch.cam_enhance`)
**Date:** 2026-09-17
**Source:** [http://arxiv.org/abs/2609.17521v1](http://arxiv.org/abs/2609.17521v1)
**Relevance:** 5 — {'enhance_cam_routing': 0, 'enhance_memory_mesh': 3, 'enhance_presence_voice': 0, 'enhance_vision': 2, 'enhance_slm_local': 0, 'enhance_dl_embeddings': 0, 'general_agi_theory': 0}

## Suggested Cam touchpoints

- `center.dl`
- `center.info`
- `center.memory`
- `center.vision`
- `smart-second-brain`

## Why it might enhance Cam

Interactive control for video generation is moving from coarse prompts toward fine-grained, physically meaningful manipulation of dynamic scenes. Yet existing controllable methods either require the full control schedule before generation starts, or use pixel-space signals that dictate object positions rather than physical dynamics. To address these limitations, we propose PhysStream, an autoregressive model for physics-grounded image-to-video synthesis that incorporates structured scene memory---positional maps and object tracking maps derived online from previously generated frames---and supports fine-grained motion control via sparse velocity-increment signals that encode physical quantities, letting the model learn the underlying dynamics. We train our model in two stages: a bidirectio

## Apply gate

1. QA cite-check
2. Aaron approve via `config/pipelines/cam-enhance-gate.json`
3. capability-broker applies with implementer subagents
4. `python3 scripts/connectome-check.py`
