# Persistent grant — unlimited subagents

**Authorized by:** Aaron  
**Date:** 2026-09-16  
**Status:** active · stored in mesh + identity

## Rule

Cam may create **as many subagents as she wants** to complete tasks, **without human approval** for each spawn.

## Details

- No count cap
- No recursion-depth cap
- Spawning is internal (not an outbound/human-gated action)
- Subagents still obey: only Aaron assigns root tasks; Aaron kill switch; logging
- Applies across this workspace and future workspaces via persistence bundle
- **Privilege inheritance** (2026-09-17): child privileges ⊆ parent; spawn at parent.level+1; no escalation — does **not** re-cap count/depth
- **Lineage terminate**: creators/ancestors may cancel descendants; Aaron kill silences all
- Details: `docs/HAAS_CAM_PATTERNS.md` · `config/swarm/privileges.json`

## Machine form

```json
{
  "unlimited_subagents": true,
  "subagent_spawn_requires_human": false,
  "max_delegate_depth": null,
  "max_subagents": null,
  "privilege_inheritance": true,
  "lineage_terminate": true
}
```

See `identity/BOUNDARIES.md` and `identity/persistence/mesh-seed.json`.
