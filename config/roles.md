# Role roster

| role | agent_role string | summons subagents | notes |
|---|---|---|---|
| Cam (Chief) | `chief` | yes | always-on; finishes without mid-task interference |
| Researcher | `researcher` | yes | citations; uses vault |
| Life Ops | `ops` | yes | Jarvis |
| Documents | `docs` | yes | drafts/fixes |
| Coding | `coding` | yes | Cline effector — shared by all agents |
| Careers | `careers` | yes | LinkedIn + Indeed |
| Comms | `comms` | yes | text/call/FaceTime + avatar |
| Vision | `vision` | yes | PaddleDetection when tasked |
| QA | `qa` | yes | verifies + logs |
| Memory Curator | `memory-curator` | no | mesh + smart-second-brain |

## Recursion

- **Unlimited subagents** — Cam may spawn as many as needed without asking Aaron
- No `max_delegate_depth` / no `max_subagents` cap (persistent grant 2026-09-16)
- Subagents inherit boundaries and mesh/vault access
- Child work is still tracked as nulltickets tasks when the runtime is live
- **Any role may invoke Cline** (`motor.cline`) for coding — not siloed to `coding`

## Local tools

- Jarvis: `integrations/jarvis`
- Cline: `integrations/cline` (all agents / all workspaces)
- Vision: `integrations/paddledetection`
- Presence: `integrations/llmavatartalk`
- Second brain: `integrations/smart-second-brain`

## Prompt stubs

Detailed prompts live in `config/roles/*.md`.
