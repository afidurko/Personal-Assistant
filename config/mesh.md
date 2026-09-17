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
| `mesh/cline` | Cline session distillates, workspaces touched, schedules (all agents) |
| `mesh/vision` | distilled detection/pose results (no raw frames by default) |
| `mesh/persistence` | export pointers / bundle version for cross-workspace restore |
| `mesh/vault` | smart-second-brain vault path + topic distillates |
| `mesh/persona` | Cam identity/voice/availability prefs |

## Write rules

- Distill; do not dump raw chat transcripts
- Tag sensitivity: `public` | `team` | `private`
- Private never leaves local store / approved channels
- Curator dedupes conflicting facts; Aaron resolves ties
- Jarvis memory syncs via `scripts/sync-jarvis-memory.py`
- Cline session syncs via `scripts/sync-cline-session.py` → `mesh/cline`
- Vision results sync via `scripts/pack-vision-result.py`
- Vault intelligence via smart-second-brain; sync summaries to `mesh/vault`
- Cross-workspace: `scripts/persist-export.py` / `persist-import.py`

## Read rules

- Before claiming work, search mesh + vault
- Cite mesh keys / vault notes used
- Prefer vault knowledge before inventing Aaron’s personal facts
