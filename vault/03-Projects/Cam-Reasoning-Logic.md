# Cam Reasoning Logic

Plan to unify **Schema-Guided Reasoning (SGR)** with dual-process, MAP PFC modules, HMO recall, dual-stream language, and QA/trajectory reflection into one inspectable turn loop.

- **Repo plan:** `docs/CAM_REASONING.md`
- **SGR fork:** https://github.com/afidurko/sgr-agent-core → `integrations/sgr-agent-core`
- **Integration policy:** `config/integrations/sgr-agent-core.md`
- **Proposed config:** `config/enhancement/reasoning-logic.json` (`status: proposed` — not applied)
- **Apply:** future enhancement proposal + `switch.cam_enhance` (Aaron only)

## Loop (abbrev.)

Accept → Fast (sLM) → Escalate? → Recall → **SGR (Reason → Select → Act)** → Dual-stream → Reflect → Switches → Motor → Distill

Default slow-path agent: `SGRToolCallingAgent`.

## Next

1. Aaron answers open questions in the plan (or accept interim defaults)
2. Phase B: `scripts/cam-reason.py` + Cam toolkit wrappers around SGR
3. Phase C: wire home converse / chief
4. Phase E: apply batch (+ optional `motor.sgr`)
