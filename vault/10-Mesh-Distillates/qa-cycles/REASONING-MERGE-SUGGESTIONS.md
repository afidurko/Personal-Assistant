# Suggestive implementations — Cam reasoning merge

Status: after pass-1 dual billion (connectome + trajectory + cam-reason)

## Shipped this campaign

1. `scripts/cam-reason-billion-fuzz.py` — modular + sparse full dry-run property campaign
2. CI gate: `test_cam_reason.py` + 1M cam-reason fuzz in `ci-connectome.sh`
3. QA standing suggestions include cam-reason billion + Phase C bar-only / LitServe thin proxy
4. Suggestive kind `cam-reason` in `shared/types.ts` + `server/core/suggestions.ts`
5. Config load cache in `cam_reason.py` for fuzz throughput

## Do next (not blocking merge)

- Phase C: converse wrap **bar-only** (never every mic turn)
- LitServe thin OpenAI-compatible **proxy** (not vLLM farm)
- Expand toolkit (Cline/Scholar) after merge
- Optional `motor.sgr` in enhance apply batch only

## Cut (still)

Every-mic SGR · TS-first · full LitServe/vLLM · Skills/ACP early · cortex HUD
