# Role roster

| role | agent_role string | summons subagents | human gate heavy |
|---|---|---|---|
| Chief of Staff | `chief` | yes | mediates all |
| Researcher | `researcher` | yes | citations required |
| Life Ops | `ops` | yes | scheduling changes; may call Jarvis |
| Documents | `docs` | yes | external send |
| Careers | `careers` | yes | applications / outreach |
| Comms | `comms` | limited | all outbound |
| QA | `qa` | yes | can block release |
| Memory Curator | `memory-curator` | no | mesh merges only |

## Recursion

- Default `max_delegate_depth`: 3
- Subagents inherit parent boundaries and mesh namespaces
- Child work is always a nulltickets task (or child dependency), never a fire-and-forget thread

## Local tools

- Jarvis CLI: `integrations/jarvis` — see `config/integrations/jarvis.md`

## Prompt stubs

Detailed prompts live in `config/roles/*.md` and are loaded by nullclaw role config.
