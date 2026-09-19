# Enhancement proposal — Organizational Control Layer (OCL) at Cam motors

**Status:** applied (Aaron approved 2026-09-17 · `switch.cam_enhance` for this batch)
**Date:** 2026-09-17  
**Source:** [Organizational Control Layer](https://arxiv.org/abs/2606.04306) · also [Compositional Policy Violations](https://arxiv.org/abs/2609.18820)  
**Priority:** P0/P1 — hardens Aaron’s ultimate say at the execution boundary  
**Relevance:** switches · human gate · trajectory policy

## Suggested Cam touchpoints

- all `switch.*` and `motor.*`
- `center.qa`
- `switch.cam_enhance`, `switch.outbound`, `switch.careers_submit`, `switch.kill`
- `config/pipelines/*`

## Why it might enhance Cam

OCL separates **proposal generation** from **environment-facing execution**. It intercepts actions and approves / revises / blocks / escalates without changing the LLM. Experiments cut unsafe executions dramatically while raising valid success.

Separately, Compositional Policy Violations (CPV) show that **every step can look compliant while the composed trajectory violates policy** (authority limits, review requirements). Cam’s switches are step-scoped today; whole-pathway policies (e.g. “research may fetch but never apply enhance”) need trajectory checks.

## Proposed Cam mapping (config-first)

1. Treat connectome `motor_plan` as the OCL intercept point (already in `connectome-route.py`).  
2. Add trajectory predicates in QA: e.g. forbid `motor.enhance` unless Aaron-approved ticket; forbid outbound+jobs in same unsupervised burst without standing grant.  
3. On block: revise to draft-only / mesh-log-only (structured recovery, not silent drop).

## Apply gate

1. QA cite-check  
2. Aaron approve  
3. Extend `scripts/connectome-route.py` + `center.qa` prompts; add CPV fixtures to connectome-check  
4. Re-run `python3 scripts/connectome-check.py`


## Apply record

- **BATCH APPLIED** by Aaron 2026-09-17 via `scripts/apply-cam-enhancements.py`
- Implementer: Cam capability-broker (this checkout)
