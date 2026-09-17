# Enhancement proposal — Agentic Societies Need a Social Harness

**Status:** propose_only (awaiting Aaron / `switch.cam_enhance`)
**Date:** 2026-09-17
**Source:** [http://arxiv.org/abs/2609.17527v1](http://arxiv.org/abs/2609.17527v1)
**Relevance:** 8 — {'enhance_cam_routing': 3, 'enhance_memory_mesh': 0, 'enhance_presence_voice': 2, 'enhance_vision': 2, 'enhance_slm_local': 0, 'enhance_dl_embeddings': 0, 'general_agi_theory': 1}

## Suggested Cam touchpoints

- `center.capability`
- `center.comms`
- `center.dl`
- `center.router`
- `center.vision`
- `config/roles`
- `motor.speak`

## Why it might enhance Cam

An agentic society is a collection of AI agents that coordinate autonomously across trust boundaries, on behalf of different principals whose objectives may only partially align. We show experimentally that in agentic societies even honest, competent agents often fail to reach satisfactory outcomes with existing harnesses and messaging primitives, and that faulty or malicious agents can stall collaboration, influence outcomes, and pursue other harmful goals by exploiting vulnerabilities in communication (``speech''). We argue that agentic societies need a \emph{social harness} for inter-agent interactions, in addition to each agent's \emph{personal harness}, which manages its private context and communication with its principal. We propose a layered architecture for social harnesses which 

## Apply gate

1. QA cite-check
2. Aaron approve via `config/pipelines/cam-enhance-gate.json`
3. capability-broker applies with implementer subagents
4. `python3 scripts/connectome-check.py`
