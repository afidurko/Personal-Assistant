# Jarvis integration

Source: [afidurko/Jarvis](https://github.com/afidurko/Jarvis) (fork of sukeesh/Jarvis)  
Path: [`integrations/jarvis`](../../integrations/jarvis) (git submodule)

## Role in the team

Jarvis is the **local deterministic toolbelt** — weather, file helpers, conversions,
health calculators, system info, and ~185 CLI plugins. It is **not** the brain.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw |
| Task queue / persistence | nulltickets |
| Scheduling | nullboiler |
| Human override | nullhub |
| Fast local utilities | **Jarvis** |

The `ops` role (and subagents it spawns) may invoke Jarvis plugins for chores that
do not need an LLM. Irreversible or outbound actions still go through human gates.

## Install (on your machine)

```bash
git submodule update --init --recursive
cd integrations/jarvis
python3 installer   # or: python installer
# then: jarvis   or   ./jarvis
```

## Memory mesh bridge

Jarvis stores key/values in `jarviscli/packages/memory/memory.json`.
That file is a **local cache**. Authoritative shared memory is nulltickets mesh.

```bash
# Export Jarvis memory → mesh/jarvis JSON document (stdout)
python3 scripts/sync-jarvis-memory.py export

# Preview merge of a mesh dump back into Jarvis memory (dry-run)
python3 scripts/sync-jarvis-memory.py import --from path/to/mesh-jarvis.json --dry-run
```

When nulltickets is running, the curator/`ops` role should `PUT` the export under
`mesh/jarvis` and pull it before Jarvis-dependent tasks.

## Personality items

Jarvis ships a bipolar personality TSV used here as optional questionnaire
section 14 — see `identity/QUESTIONNAIRE.md`.

## Custom plugins

Put personal plugins in `integrations/jarvis/custom/` (gitignored patterns
already exist upstream). Prefer thin wrappers that call into our policies
rather than re-implementing agent logic inside Jarvis.
