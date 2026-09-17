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
| `mesh/vision` | distilled detection/pose results (no raw frames by default) |
| `mesh/persistence` | export pointers / bundle version for cross-workspace restore |
| `mesh/vault` | smart-second-brain vault path + topic distillates |
| `mesh/persona` | Cam identity/voice/availability prefs |
<<<<<<< HEAD
| `mesh/agent-commute` | Task commute paths + efficiency rankings |
| `mesh/agent-memory` | Agent-consolidated memory promotions |
| `mesh/agent-persistence` | Sticky jobs until completion |
| `mesh/agent-issue-loop` | Automated fix-loop attempts + escalations |

## Deep agent layers (TypeScript neural mesh)

Stacked on the interactive brain map (`server/core/agent-mesh.ts`):

1. **Commute** — route tasks via high-confidence hops  
2. **Memory** — consolidate + amplify recall  
3. **Persistence** — keep jobs alive until done  
4. **Issue-fix loop** — dedicated automated detect → fix → verify → escalate agents  
=======
| `mesh/enhance` | sLM/DL cortex recipes + cam_enhance gate state |
| `mesh/research/agi-scan` | daily AGI paper distillates (via vault mirror) |
| `mesh/workspaces` | scan-workspace snapshots when PR#2 server is live |
>>>>>>> d6bc4c6 (Confirm multi-workspace integration and close persist-export gaps)

## Write rules

- Distill; do not dump raw chat transcripts
- Tag sensitivity: `public` | `team` | `private`
- Private never leaves local store / approved channels
- Curator dedupes conflicting facts; Aaron resolves ties
- Jarvis memory syncs via `scripts/sync-jarvis-memory.py`
- Vision results sync via `scripts/pack-vision-result.py`
- Vault intelligence via smart-second-brain; sync summaries to `mesh/vault`
- AGI daily scan archives via `scripts/agi-research-scan.py` → vault + mesh distillates
- Cross-workspace: `scripts/persist-export.py` / `persist-import.py`
- Integration confirmation: `scripts/workspace-integration-check.py` · `docs/WORKSPACES_WORKFLOW.md`
## Read rules

- Before claiming work, search mesh + vault
- Cite mesh keys / vault notes used
- Prefer vault knowledge before inventing Aaron’s personal facts
