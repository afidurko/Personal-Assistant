# Role roster

| role | agent_role string | summons subagents | human gate heavy |
|---|---|---|---|
| Chief of Staff | `chief` | yes | mediates all |
| Researcher | `researcher` | yes | citations required |
| Life Ops | `ops` | yes | scheduling changes; may call Jarvis |
| Vision | `vision` | yes | PaddleDetection on approved media |
| Documents | `docs` | yes | external send |
| Careers | `careers` | yes | applications / outreach |
| Comms | `comms` | limited | all outbound |
| QA | `qa` | yes | can block release |
| Memory Curator | `memory-curator` | no | mesh + smart-second-brain |
| Vision | `vision` | yes | PaddleDetection when tasked |

## Recursion

- Default `max_delegate_depth`: 3
- Subagents inherit boundaries and mesh/vault access
- Child work is always a nulltickets task

## Local tools

- Jarvis: `integrations/jarvis`
- Vision: `integrations/paddledetection`
- Presence: `integrations/llmavatartalk`
- Second brain: `integrations/smart-second-brain`

## Prompt stubs

Detailed prompts live in `config/roles/*.md`.
