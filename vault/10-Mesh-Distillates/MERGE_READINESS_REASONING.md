# Merge readiness — Cam reasoning logic (SGR + LitServe plan + Phase B)

**Branch:** `cursor/cam-reasoning-logic-plan-99b0`  
**Date:** 2026-09-19  
**Authorized:** Aaron — plan Cam reasoning · adopt SGR + LitServe · thin slice · go Phase B · dual billion QA

## Verdict

**READY TO MERGE**

Dual billion campaigns green (0 failures) for connectome, trajectory OCL/CPV, and cam-reason Phase B. Suggestive implementations added. CI gate green. `switch.cam_enhance` remains **hold** (reasoning-logic stays `proposed`; runtime dry-run only).

## Campaigns

| Pass | Tool | N | Failed | Rate | Artifact |
|---|---|---|---|---|---|
| A | `qa-loop.py` connectome | 1e9 | 0 | ~1.98M sims/s | `connectome-sim-1b-reason-pass1.json` · `qa-cycles/20260919T195602Z-cycle-01/` |
| A′ | `trajectory-billion-fuzz.py` | 1e9 | 0 | ~4.42M/s | `trajectory-1b-reason-pass1.json` |
| A″ | `cam-reason-billion-fuzz.py` | 1e9 | 0 | ~0.94M/s | `cam-reason-1b-pass1.json` |
| Fix + suggest | CI cam-reason gate, suggestion kind, QA standing notes, config cache | — | — | — | this PR |
| B | `qa-loop.py` connectome | 1e9 | 0 | ~1.27M sims/s | `connectome-sim-1b-reason-pass2.json` · `qa-cycles/20260919T203537Z-cycle-01/` |
| B′ | `trajectory-billion-fuzz.py` | 1e9 | 0 | ~4.29M/s | `trajectory-1b-reason-pass2.json` |
| B″ | `cam-reason-billion-fuzz.py` | 1e9 | 0 | (pass2) | `cam-reason-1b-pass2.json` |

## Correctives / suggestive implementations shipped

1. `scripts/cam-reason.py` Phase B dry-run loop (escalate bar, CamReasoningTool, min toolkit)  
2. `scripts/cam-reason-billion-fuzz.py` — modular + sparse full dry-run campaign  
3. CI: `test_cam_reason.py` + 1M cam-reason fuzz in `ci-connectome.sh`  
4. Suggestive kind `cam-reason` + AGI suggestion in `suggestions.ts`  
5. QA standing suggestions: Phase C bar-only, LitServe thin proxy, no vLLM farm  
6. Config JSON cache in `cam_reason.py` for fuzz throughput  
7. Submodules: `integrations/sgr-agent-core`, `integrations/litserve` (plan-only host)

## Pre-merge checklist (verified)

- [x] `bash scripts/ci-connectome.sh`
- [x] `python3 scripts/test_cam_reason.py`
- [x] Dual billion connectome campaigns
- [x] Dual trajectory billion campaigns
- [x] Dual cam-reason billion campaigns
- [x] Vitest `billion-round2` (includes cam-reason suggestion)

## Notes

- Reasoning config `status: proposed` — not an enhance apply  
- Phase C (converse bar-only + LitServe proxy) is **post-merge**  
- Cut list still stands: every-mic SGR, TS-first, LitServe/vLLM farm, Skills/ACP early  
- Runtime noise (`activity-events.jsonl`, reasoning JSONL) gitignored  
