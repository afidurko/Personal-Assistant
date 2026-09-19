# Cam Reasoning Logic

Plan to unify dual-process, MAP PFC modules, HMO recall, dual-stream language, and QA/trajectory reflection into one inspectable turn loop.

- **Repo plan:** `docs/CAM_REASONING.md`
- **Proposed config:** `config/enhancement/reasoning-logic.json` (`status: proposed` — not applied)
- **Apply:** future enhancement proposal + `switch.cam_enhance` (Aaron only)

## Loop (abbrev.)

Accept → Fast (sLM) → Escalate? → Recall → MAP plan → Dual-stream → Reflect → Switches → Motor → Distill

## Next

1. Aaron answers open questions in the plan (or accept interim defaults)
2. Phase B: `scripts/cam-reason.py` dry-run
3. Phase C: wire home converse / chief
4. Phase E: apply batch
