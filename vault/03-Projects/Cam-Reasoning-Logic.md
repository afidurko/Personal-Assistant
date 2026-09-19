# Cam Reasoning Logic

Plan: **SGR** (System-2) + **LitServe** (deferred host) + dual-process / MAP / HMO / QA.

- **Repo plan:** `docs/CAM_REASONING.md` (includes **cut list**)
- **SGR:** `integrations/sgr-agent-core`
- **LitServe:** `integrations/litserve` (submodule present; **not** Phase B)
- **Config:** `config/enhancement/reasoning-logic.json` (`proposed`)

## Thin slice (Phase B)

`cam-reason.py --dry-run` → escalate bar → MeshRecall / ConnectomeRoute / TrajectoryCheck / FinalAnswer → `reasoning_trace`

## Cut (slow / nonsense)

Every-mic SGR · TS-first · full LitServe/vLLM farm · skills/ACP · wide toolkit · motor.sgr early · cortex HUD · Tavily default

## Next

Implement Phase B dry-run when Aaron says go. Only open live question: cloud LLM vs stubs until LitServe proxy.
