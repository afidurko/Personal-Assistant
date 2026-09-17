# Persistent grant — HAAS → Cam patterns

**Authorized by:** Aaron  
**Date:** 2026-09-17  
**Status:** active · stored in mesh + identity

## Rule

Cam may use HAAS-inspired **privilege inheritance**, **lineage terminate**, **boss/worker synapse primitives**, and **tool-creator → tool-user** — without adopting the HAAS Assistants runtime or a multi-agent oversight board.

## Details

- Unlimited subagent **count and depth** remain (see `UNLIMITED_SUBAGENTS.md`)
- Child privileges must be a **subset** of the parent; aaron_only privileges never granted to agents
- Creators / ancestors may **terminate lineage**; Aaron kill silences all
- Internal agent bus: assign / broadcast / resolve / send_message → mesh + nulltickets (when live)
- Tool registry: `config/tools/registry.json` · team: `config/teams/tooling.json`
- Self-improve proposals stay Aaron-gated via `switch.cam_enhance`

## Machine form

```json
{
  "haas_cam_patterns": true,
  "privilege_inheritance": true,
  "lineage_terminate": true,
  "boss_worker_primitives": true,
  "tool_creator_user": true,
  "haas_assistants_runtime": false,
  "supreme_oversight_board": false
}
```

See `docs/HAAS_CAM_PATTERNS.md` and `config/swarm/`.
