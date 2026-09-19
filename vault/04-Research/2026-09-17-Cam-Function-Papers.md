# Research Brief — Papers to help Cam function better

**Accessed:** 2026-09-17  
**Question:** Which AI / agent papers most improve how Cam thinks, remembers, routes, speaks, and stays under Aaron’s control?  
**Method:** Live arXiv AGI daily scan (`scripts/agi-research-scan.py`) + targeted literature search (memory, mesh, persona, governance).  
**Gate:** Distill + propose only. Functionality apply still needs Aaron (`switch.cam_enhance`).

## Status — APPLIED

Aaron approved **all** proposals and ordered implement-all on **2026-09-17**.  
Batch log: `identity/persistence/CAM_ENHANCE_BATCH_2026-09-17.md`  
Future enhancement batches still require Aaron (`switch.cam_enhance` defaults to hold).

## Summary

Cam already has the right skeleton (connectome, teams, mesh, switches). The highest-leverage papers strengthen **four layers**:

1. **Memory hierarchy** — keep Aaron-facing context lean while persisting full history  
2. **Multi-agent mesh semantics** — how specialist centers share claims without dumping raw chat  
3. **Execution-boundary governance** — switches that check whole trajectories, not only single steps  
4. **Persona continuity** — soft-airy Cam voice/identity that does not drift across sessions  

Secondary wins: dual-process fast/slow routing, vision grounding, and scientific-tool environments for research roles.

## Priority stack (for Cam)

| Priority | Paper | Why Cam | Touchpoints |
|---|---|---|---|
| P0 | [Hierarchical Memory Orchestration (HMO)](https://arxiv.org/abs/2604.01670) | Persona-driven 3-tier memory; OpenClaw-class personal agents | `center.memory`, vault, mesh namespaces |
| P0 | [Mesh Memory Protocol (MMP)](https://arxiv.org/abs/2604.19540) | Field-level accept/remix of peer agent claims + lineage | `mesh/*`, teams, `center.qa` |
| P0 | [Organizational Control Layer (OCL)](https://arxiv.org/abs/2606.04306) | Separate propose vs execute; cut unsafe motor fires | switches, `motor.*`, human gate |
| P1 | [Cognitive Extensions for Dual-Process Agents](http://arxiv.org/abs/2609.19128v1) | Fast proposer + slow planner + adaptive memory + self-reflection | `center.router`, `center.slm`, `center.capability` |
| P1 | [Compositional Policy Violations](http://arxiv.org/abs/2609.18820v1) | Step-OK ≠ trajectory-OK — strengthen QA over whole pathways | `center.qa`, switches |
| P1 | [Agentic Societies Need a Social Harness](https://arxiv.org/abs/2609.17527) | Inter-agent speech needs a harness beyond personal context | teams, `center.comms` |
| P2 | [REALM — retrieval-driven reconsolidation](https://arxiv.org/abs/2609.16053) | Memory evolves from retrieval feedback | mesh curator |
| P2 | [Infini Memory](https://arxiv.org/abs/2606.10677) | Topic documents ≈ vault notes with agentic retrieval | smart-second-brain |
| P2 | [AgeMem / VerMem](https://aclanthology.org/2026.acl-long.981) | Memory ops as tools (store/update/discard) | `center.memory`, tool motors |
| P2 | [ARPM temporal persona memory](https://arxiv.org/html/2605.14802v1) | Temporal governance for long-term persona consistency | `mesh/persona`, Cam voice |
| P2 | [Persona multi-turn RL consistency](https://arxiv.org/html/2511.00222v1) | Metrics + training to stop persona drift | presence / chief prompts |
| P3 | [ScienceIDE](http://arxiv.org/abs/2609.19134v1) | Scientific codebases as agent learning envs | researcher / info |
| P3 | [PANORAMA](http://arxiv.org/abs/2609.19143v1) | Panoptic grounded vision captions | `center.vision` |
| P3 | Human oversight framework ([2605.16278](https://arxiv.org/abs/2605.16278)) | Document oversight architecture (Aaron roles) | nullhub / kill switch |

## What to do next (propose → Aaron)

1. **Memory tiering (HMO)** — map primary/secondary/archive onto session recall + `mesh/*` + vault. Keep Aaron chat lean.  
2. **Mesh claim schema (MMP)** — CAT7-like fields for every mesh write; QA remixes, never dumps peer raw.  
3. **OCL at motors** — every `motor.*` already sits behind switches; add trajectory CPV checks in `center.qa`.  
4. **Dual-process** — `center.slm` as fast proposer; `center.capability` / chief as slow planner; AMM-style salience for mesh.  
5. **Persona audits** — periodic prompt-to-line / line-to-line checks for Cam soft-airy English + Aaron-only tasking.

Detailed proposals: `vault/02-Cam/enhancement-proposals/` (auto + Cam-function set below).  
Live scan note: `vault/04-Research/agi-daily/2026-09-17/`.

## Counter-arguments / risks

- Keyword scoring over-weights vision/robotics papers that do not help desktop Cam. Prefer P0 memory/governance first.  
- RL memory training (AgeMem) is heavy; Cam should adopt **interfaces** (memory-as-tools, topic docs), not retrain models in-repo.  
- Social-harness ideas for open agent societies are larger than Aaron-only Cam — adopt messaging validation among Cam’s own teams, not internet-wide agents.  
- Persona RL fine-tunes conflict with “prompts + config over new code”; start with evaluation metrics + prompt governance.

**Recommendation**

**Done (Aaron 2026-09-17):** HMO tiers + MMP claim fields + OCL/CPV checks + dual-process + persona continuity + related role/config wiring are **applied**. Future model fine-tunes or new runtimes still need a fresh Aaron-approved proposal.

## Sources

- Live scan: `vault/04-Research/agi-daily/2026-09-17/2026-09-17-AGI-scan.md` — accessed 2026-09-17  
- https://arxiv.org/abs/2604.01670 — Hierarchical Memory Orchestration — accessed 2026-09-17  
- https://arxiv.org/abs/2604.19540 — Mesh Memory Protocol — accessed 2026-09-17  
- https://arxiv.org/abs/2606.04306 — Organizational Control Layer — accessed 2026-09-17  
- https://arxiv.org/abs/2609.19128 — Cognitive Extensions dual-process — accessed 2026-09-17  
- https://arxiv.org/abs/2609.18820 — Compositional Policy Violations — accessed 2026-09-17  
- https://arxiv.org/abs/2609.17527 — Agentic Societies Social Harness — accessed 2026-09-17  
- https://arxiv.org/abs/2609.16053 — REALM — accessed 2026-09-17  
- https://arxiv.org/abs/2606.10677 — Infini Memory — accessed 2026-09-17  
- https://arxiv.org/html/2605.14802v1 — ARPM persona memory — accessed 2026-09-17  
- https://arxiv.org/html/2511.00222v1 — Persona multi-turn RL — accessed 2026-09-17  
- https://arxiv.org/abs/2605.16278 — Human oversight framework — accessed 2026-09-17  
