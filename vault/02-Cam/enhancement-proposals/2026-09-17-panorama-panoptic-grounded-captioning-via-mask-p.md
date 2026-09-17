# Enhancement proposal — PANORAMA: Panoptic Grounded Captioning via Mask Proposal Selection

**Status:** propose_only (awaiting Aaron / `switch.cam_enhance`)
**Date:** 2026-09-17
**Source:** [http://arxiv.org/abs/2609.19143v1](http://arxiv.org/abs/2609.19143v1)
**Relevance:** 5 — {'enhance_cam_routing': 0, 'enhance_memory_mesh': 3, 'enhance_presence_voice': 0, 'enhance_vision': 2, 'enhance_slm_local': 0, 'enhance_dl_embeddings': 0, 'general_agi_theory': 0}

## Suggested Cam touchpoints

- `center.dl`
- `center.info`
- `center.memory`
- `center.vision`
- `smart-second-brain`

## Why it might enhance Cam

Intelligent systems that act in the world require image understanding that is both comprehensive and spatially grounded. Current vision-language models (VLMs) can generate fluent and detailed image captions, but reliably associating them with image pixels remains challenging. Existing methods that combine dense captioning with pixel-level grounding often produce either incomplete descriptions or inaccurate segmentation masks. We study this problem through panoptic grounded captioning, a task that requires a VLM to describe both foreground objects and background regions while grounding each referring phrase with pixel-level masks. We make three contributions. First, we introduce PanoCaps, a human-annotated benchmark constructed from panoptic segmentation datasets. It provides dense captions

## Apply gate

1. QA cite-check
2. Aaron approve via `config/pipelines/cam-enhance-gate.json`
3. capability-broker applies with implementer subagents
4. `python3 scripts/connectome-check.py`
