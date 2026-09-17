# Mesh namespaces

Shared across every agent. Backed by nulltickets `/store`.

| namespace | purpose |
|---|---|
| `mesh/prefs` | preferences from questionnaire |
| `mesh/facts` | durable facts about you / world |
| `mesh/people` | people graph notes |
| `mesh/projects` | active projects |
| `mesh/research` | research briefs + source lists |
| `mesh/careers` | job search state |
| `mesh/docs` | document index / templates |
| `mesh/runs` | distilled run outcomes |
| `mesh/open-questions` | unresolved questions for the team |
| `mesh/jarvis` | synced Jarvis `memory.json` cache (local utilities) |
| `mesh/cline` | Cline sessions, registry workspaces, schedules, tickets |
| `mesh/projects` | coding workspace registry distillate |
| `mesh/vision` | distilled detection/pose results (no raw frames by default) |
| `mesh/persistence` | export pointers / bundle version for cross-workspace restore |
| `mesh/vault` | smart-second-brain vault path + topic distillates |
| `mesh/cartography` | SwiftGuide mind-map hits + iOS stack distillates |
| `mesh/language` | Arcuate language loop distillates (Wernicke↔Broca) |
| `mesh/frontoparietal` | SLF ops↔executive coupling |
| `mesh/valuation` | Uncinate OFC↔temporal boundary notes |
| `mesh/tracts` | Hebbian association-fiber weights |
| `mesh/persona` | Cam identity/voice/availability prefs |
| `mesh/agent-commute` | Task commute paths + efficiency rankings |
| `mesh/agent-memory` | Agent-consolidated memory promotions |
| `mesh/agent-persistence` | Sticky jobs until completion |
| `mesh/agent-issue-loop` | Automated fix-loop attempts + escalations |
| `mesh/enhance` | sLM/DL cortex recipes + cam_enhance gate state |
| `mesh/research/agi-scan` | daily AGI paper distillates (via vault mirror) |
| `mesh/workspaces` | scan-workspace snapshots (health/arch/vuln/updates/improvements) |
| `mesh/agent-lineage` | spawn tree, privilege grants, lineage terminations |
| `mesh/tools` | registered tool specs + run distillates (team.tooling) |

## Deep agent layers (TypeScript neural mesh)

Stacked on the interactive brain map (`server/core/agent-mesh.ts`):

1. **Commute** — route tasks via high-confidence hops  
2. **Memory** — consolidate + amplify recall  
3. **Persistence** — keep jobs alive until done  
4. **Issue-fix loop** — dedicated automated detect → fix → verify → escalate agents  
5. **Swarm** — privilege inheritance, lineage terminate, boss/worker bus for **all agents + all workspaces**

Runtime: `server/core/swarm-runtime.ts` writes:

- `data/swarm-lineage.json` — live agent tree  
- `data/mesh-namespaces.json` — cross-workspace mirror of `mesh/agent-lineage`, `mesh/tools`, `mesh/swarm/*`  
- PersistentMemory traces with `kind: swarm` tagged `cross-workspace` / `all-agents`

Scan workspace: `server/workspaces/swarm.ts` (`workspace-swarm`)

## HAAS → Cam swarm layer

Config (not a second runtime): `config/swarm/`

- Privilege inheritance + lineage terminate
- Boss/worker primitives → `motor.swarm` / `sense.swarm.message`
- Validate: `python3 scripts/swarm-check.py`
- Neural integration: every scan cycle runs swarm after issue-loop

## Write rules

- Distill; do not dump raw chat transcripts
- Tag sensitivity: `public` | `team` | `private`
- Private never leaves local store / approved channels
- Curator dedupes conflicting facts; Aaron resolves ties
- Jarvis memory syncs via `scripts/sync-jarvis-memory.py`
- Cline session syncs via `scripts/sync-cline-session.py` → `mesh/cline`
- Cline schedules via `scripts/sync-cline-schedules.py` → `mesh/cline.schedules`
- Cline tickets via `scripts/export-cline-tickets.py` → `mesh/runs`
- Workspace registry via `scripts/choose-workspace.py --mesh-projects`
- Vision results sync via `scripts/pack-vision-result.py`
- Vault intelligence via smart-second-brain; sync summaries to `mesh/vault`
- Knowledge maps via SwiftGuide; sync stack/taxonomy distillates to `mesh/cartography`
- AGI daily scan archives via `scripts/agi-research-scan.py` → vault + mesh distillates
- Tool specs/runs via team.tooling → `mesh/tools`
- Cross-workspace: `scripts/persist-export.py` / `persist-import.py`
- Integration confirmation: `scripts/workspace-integration-check.py` · `docs/WORKSPACES_WORKFLOW.md`
- Swarm contracts: `scripts/swarm-check.py` · `docs/HAAS_CAM_PATTERNS.md`

## Read rules

- Before claiming work, search mesh + vault
- Cite mesh keys / vault notes used
- Prefer vault knowledge before inventing Aaron’s personal facts
