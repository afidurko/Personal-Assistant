# Enhancement proposal — Dreaming the Sound of Contact: Leveraging Video and Audio Generation for Zero-Shot Force-Aware Manipulation and Data Generation

**Status:** propose_only (awaiting Aaron / `switch.cam_enhance`)
**Date:** 2026-09-17
**Source:** [http://arxiv.org/abs/2609.19137v1](http://arxiv.org/abs/2609.19137v1)
**Relevance:** 6 — {'enhance_cam_routing': 0, 'enhance_memory_mesh': 3, 'enhance_presence_voice': 0, 'enhance_vision': 2, 'enhance_slm_local': 0, 'enhance_dl_embeddings': 0, 'general_agi_theory': 1}

## Suggested Cam touchpoints

- `center.dl`
- `center.info`
- `center.memory`
- `center.vision`
- `smart-second-brain`

## Why it might enhance Cam

Recent advances in video generation allow robots to learn manipulation trajectories from generated videos. However, these approaches produce purely kinematic trajectories that lack force information, causing failures in contact-rich tasks where appropriate contact forces are essential for success. In this work, we explore augmenting generated video with audio to shape a bounded, time-varying desired-force profile using the loudness of generated contact sounds. We present a pipeline that jointly leverages generated video and audio to derive motion trajectories and corresponding desired-force profiles from a structured natural-language task prompt. We execute these force-aware trajectories on a Franka Panda robot using a closed-loop force regulator that tracks the audio-shaped force profile 

## Apply gate

1. QA cite-check
2. Aaron approve via `config/pipelines/cam-enhance-gate.json`
3. capability-broker applies with implementer subagents
4. `python3 scripts/connectome-check.py`
