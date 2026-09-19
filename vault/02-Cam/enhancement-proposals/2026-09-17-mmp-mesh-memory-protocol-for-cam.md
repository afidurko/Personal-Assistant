# Enhancement proposal — Mesh Memory Protocol (MMP) for Cam teams

**Status:** applied (Aaron approved 2026-09-17 · `switch.cam_enhance` for this batch)
**Date:** 2026-09-17  
**Source:** [Mesh Memory Protocol: Semantic Infrastructure for Multi-Agent LLM Systems](https://arxiv.org/abs/2604.19540)  
**Priority:** P0 — namesake fit for Cam’s neural mesh + specialist teams  
**Relevance:** multi-agent claim sharing · lineage · remix

## Suggested Cam touchpoints

- all `mesh/*` namespaces
- `center.qa` (field-level accept)
- AGI / Capability / Information teams
- `mesh/agent-memory`, `mesh/runs`

## Why it might enhance Cam

MMP defines **semantic infrastructure** for agents that collaborate across sessions:

- **CAT7** — fixed fields for every Cognitive Memory Block  
- **SVAF** — receiver accepts **field-by-field**, not whole messages  
- **Lineage** — content-hash parents/ancestors so echoes are recognized  
- **Remix** — store the receiver’s role-evaluated understanding, never raw peer dumps  

Cam already has unlimited subagents and shared mesh. Without field-level remix, specialists risk polluting mesh with uncited or role-inappropriate claims.

## Proposed Cam mapping (config-first)

Require every mesh PUT to carry: `claim`, `role`, `sources`, `confidence`, `parents`, `sensitivity`, `accessed`.  
`center.qa` remixes into role-local understanding before `motor.mesh` commits.  
Reject whole-blob peer dumps from AGI scan / vision / careers into `mesh/facts`.

## Apply gate

1. QA cite-check  
2. Aaron approve  
3. Update `config/mesh.md` write rules + curator/researcher prompts; optional schema JSON  
4. `python3 scripts/workspace-integration-check.py`


## Apply record

- **BATCH APPLIED** by Aaron 2026-09-17 via `scripts/apply-cam-enhancements.py`
- Implementer: Cam capability-broker (this checkout)
