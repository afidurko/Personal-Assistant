# HAAS → Cam patterns

Cam borrows **patterns** from [OpenAI_Agent_Swarm (HAAS)](https://github.com/afidurko/OpenAI_Agent_Swarm) — not the Assistants runtime, not a Supreme Oversight Board.

## Adopted

| HAAS idea | Cam implementation |
|---|---|
| Privilege inheritance | `config/swarm/privileges.json` — child privileges ⊆ parent; aaron_only never granted |
| Spawn one level below | Child `level = parent.level + 1`; count/depth still **unlimited** |
| Lineage terminate | Ancestors (or Aaron kill) cancel descendants → `mesh/agent-lineage` |
| Boss/worker messaging | `synapse.assign_task` / `broadcast` / `resolve_task` / `send_message` in `config/swarm/primitives.json` |
| Tool creator → tool user | `team.tooling` · `config/roles/tool-creator.md` · `tool-user.md` · `config/tools/registry.json` |
| Autonomy triad | `config/swarm/autonomy-triad.json` — reframed under Aaron governance |

## Explicitly not adopted

- OpenAI Assistants HAAS Python runtime as Cam’s core
- Multi-agent Supreme Oversight Board (Aaron is sole human master)
- Heuristic imperatives as root tasking
- Fully unsupervised invention of new root goals

## Runtime binding

```text
HAAS queue/chat room  →  nulltickets + mesh/agent-commute + motor.swarm
HAAS SOB              →  Aaron (human) + switch.kill / switch.cam_enhance
HAAS Executive        →  Cam chief + capability-broker
HAAS Sub-agent        →  specialists / unlimited subagents with privilege inheritance
```

## Local runtime (CLI / MCP / loops)

- `scripts/cam_swarm.py` — file-backed lineage for the same six primitives when the Node server is not running: `spawn` (level = parent + 1, privileges ⊆ parent, Aaron-only never granted, unlimited), `assign`, `resolve`, `send`, `broadcast` (team channels from `primitives.json`), `terminate` (ancestor or Aaron; cascades; cancels open actions), plus `kill` / `resume` for Aaron
- Ledger `data/swarm/lineage.json`; counts-only distillate `vault/10-Mesh-Distillates/agent-lineage/latest.json`; the server's `data/swarm-lineage.json` is read for stats/doctor, never written
- Instinct binds jobs to lineages: `scripts/instinct.py delegate <job>`; MCP `swarm_*` + `instinct_delegate`; nightly `swarm_distill` in `instinct-followups`
- Tests: `python3 scripts/test_cam_swarm.py`

## Neural mesh + memory (all workspaces / agents)

| Piece | Path |
|---|---|
| Privilege TS engine | `shared/swarmPrivileges.ts` |
| Swarm cycle runtime | `server/core/swarm-runtime.ts` |
| Agent layer | `swarm` in `shared/agentLayers.ts` (privilege-broker, lineage-guardian, boss-router, tool-broker) |
| Scan workspace | `server/workspaces/swarm.ts` |
| Lineage file | `data/swarm-lineage.json` |
| Namespace mirror | `data/mesh-namespaces.json` |
| Memory traces | `kind: swarm` + semantic tags `mesh/agent-lineage`, `cross-workspace`, `all-agents` |

Every `AgentMeshRuntime.runCycle` (after commute/memory/persistence/issue-loop) runs the swarm cycle so **all scan workspaces** get assign/broadcast/resolve traffic and shared namespace updates.

## Validate

```bash
python3 scripts/swarm-check.py
python3 scripts/swarm-check.py --json
npm test -- server/core/swarm-runtime.test.ts
npm run scan
```

## Connectome

- Center: `center.tooling`
- Switches: `switch.tooling`
- Motors: `motor.tool`, `motor.swarm`
- Senses: `sense.swarm.message`, `sense.tool.result`
- Hotspots: `hotspot.tooling`, `hotspot.swarm_bus`, `hotspot.tool_result`

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) · [CAM_BRAIN.md](CAM_BRAIN.md) · [CONNECTOME_ARCHITECTURE.md](CONNECTOME_ARCHITECTURE.md)
- Persistence: `identity/persistence/HAAS_CAM_PATTERNS.md`
