# Enhancement proposal — Hierarchical Memory Orchestration (HMO) for Cam mesh

**Status:** propose_only (awaiting Aaron / `switch.cam_enhance`)  
**Date:** 2026-09-17  
**Source:** [Hierarchical Memory Orchestration for Personalized Persistent Agents](https://arxiv.org/abs/2604.01670)  
**Priority:** P0 — directly improves Cam as Aaron’s persistent personal assistant  
**Relevance:** memory mesh · persona · OpenClaw-class personal agents

## Suggested Cam touchpoints

- `center.memory` / `memory-curator`
- `mesh/prefs`, `mesh/facts`, `mesh/persona`, `mesh/runs`
- smart-second-brain vault (archive tier)
- session recall (primary cache)

## Why it might enhance Cam

HMO organizes interaction history into three tiers driven by an evolving user profile:

1. **Primary cache** — recent + pivotal memories (lean context for Cam chief)  
2. **Secondary** — high-priority but not always in-context  
3. **Global archive** — full history (vault + nulltickets)

The **user persona redistributes** what rises to active tiers. That matches Cam’s need to stay soft-airy and Aaron-aligned without stuffing every mesh key into every prompt. Deployments in OpenClaw-like ecosystems report better fluidity and personalization.

## Proposed Cam mapping (config-first)

| HMO tier | Cam substrate |
|---|---|
| Primary | nullclaw session memory + last N mesh hits tagged `pivotal` |
| Secondary | `mesh/*` hot namespaces (`prefs`, `facts`, `persona`, open tickets) |
| Archive | `vault/` + persistence bundle + mesh distillates |

Add curator rules: promote Aaron-bound preferences; demote one-off tool noise; never put private raw media in primary.

## Apply gate

1. QA cite-check  
2. Aaron approve via `config/pipelines/cam-enhance-gate.json`  
3. Implement as mesh-seed + curator prompt + optional `scripts/` tierer — **no new agent framework**  
4. `python3 scripts/connectome-check.py`
