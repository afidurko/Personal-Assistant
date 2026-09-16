# Role roster

| role | agent_role string | summons subagents | notes |
|---|---|---|---|
| Cam (Chief) | `chief` | yes | always-on; finishes without mid-task interference |
| Researcher | `researcher` | yes | citations; uses vault |
| Life Ops | `ops` | yes | Jarvis |
| Documents | `docs` | yes | drafts/fixes |
| Careers | `careers` | yes | LinkedIn + Indeed |
| Comms | `comms` | yes | text/call/FaceTime + avatar |
| Vision | `vision` | yes | PaddleDetection when tasked |
| QA | `qa` | yes | verifies + logs |
| Memory Curator | `memory-curator` | no | mesh + smart-second-brain |

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
