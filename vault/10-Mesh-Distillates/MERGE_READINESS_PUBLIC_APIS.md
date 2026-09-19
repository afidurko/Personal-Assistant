# Merge readiness — public-apis for all agents

**Branch:** `cursor/integrate-public-apis-all-agents-8866`  
**PR:** https://github.com/afidurko/Personal-Assistant/pull/15  
**Date:** 2026-09-19  
**Authorized:** Aaron — integrate public-apis with all agents + dual billion QA

## Verdict

**READY TO MERGE**

Both billion connectome campaigns green (0 failures). Trajectory OCL/CPV billion green. Suggestive implementations added (`api-catalog`). CI gate green including public-apis unit/wiring checks.

## Campaigns

| Pass | Tool | N | Failed | Rate | Artifact |
|---|---|---|---|---|---|
| A | `qa-loop.py` connectome | 1e9 | 0 | ~2.44M sims/s | `qa-cycles/20260919T183433Z-cycle-01/` · `connectome-sim-1b-pass1-public-apis.json` |
| Fix + suggest | traffic weight, health pulse, `api-catalog` suggestions, CI public-apis gates | — | — | — | `qa-cycles/PUBLIC-APIS-SUGGESTIVE-20260919.md` |
| B | `qa-loop.py` connectome | 1e9 | 0 | ~2.56M sims/s | `qa-cycles/20260919T184255Z-cycle-01/` · `connectome-sim-1b-pass2-public-apis.json` |
| B′ | `trajectory-billion-fuzz.py` | 1e9 | 0 | ~8.6M checks/s | `trajectory-1b-public-apis.json` |

## Correctives / suggestive implementations shipped

1. Traffic-weighted sampling includes `sense.catalog.public_apis`  
2. Health `integration_pulse` expects public-apis (+ cline config-backed)  
3. Suggestive kind `api-catalog` for improvements/swarm workspaces  
4. CI gate: `test_public_apis.py` + `public-apis-check.py`  
5. QA standing suggestions document public-apis pre-merge steps  
6. **Add-ons** — allowlisted thin wrappers (`public-apis-addons.json` + `public-apis-addon.py` + MCP)  

## Pre-merge checklist (verified)

- [x] `bash scripts/ci-connectome.sh`
- [x] `python3 scripts/trajectory-policy-check.py`
- [x] `python3 scripts/memory-tier-check.py`
- [x] `python3 scripts/connectome-check.py`
- [x] `python3 scripts/workspace-integration-check.py`
- [x] Dual billion connectome campaigns
- [x] Trajectory billion campaign
- [x] Vitest suggestive + api-catalog coverage (`billion-round2.test.ts`)

## Notes

- Empty submodule soft-warnings (jarvis/paddledetection/…) are expected in this cloud checkout  
- `integrations/public-apis` is populated and searchable  
- Runtime noise (`activity-events.jsonl`, plasticity timelines) not required for merge  
