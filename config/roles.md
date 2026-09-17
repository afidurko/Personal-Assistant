# Role roster

| role | agent_role string | summons subagents | team | notes |
|---|---|---|---|---|
| Cam (Chief) | `chief` | yes | — | always-on; finishes without mid-task interference |
| Researcher | `researcher` | yes | — | citations; uses vault |
| Life Ops | `ops` | yes | — | Jarvis |
| Documents | `docs` | yes | — | drafts/fixes |
| Careers | `careers` | yes | — | LinkedIn + Indeed |
| Comms | `comms` | yes | — | text/call/FaceTime + avatar |
| Vision | `vision` | yes | — | PaddleDetection when tasked |
| QA | `qa` | yes | — | verifies + logs |
| Memory Curator | `memory-curator` | yes | — | mesh + smart-second-brain |
| AGI Scout | `agi-scout` | yes | `team.agi-research-scan` | daily AI/AGI paper scan lead |
| AGI Analyst | `agi-analyst` | yes | `team.agi-research-scan` | Cam-relevance scoring |
| AGI Synthesist | `agi-synthesist` | yes | `team.agi-research-scan` | map findings → Cam proposals |
| Capability Broker | `capability-broker` | yes | `team.capability` | task + enhance brokerage |
| Task Executor | `task-executor` | yes | `team.capability` | concrete work units |
| Info Retriever | `info-retriever` | yes | `team.info` | vault→mesh→web facts |
| SLM Runtime | `slm-runtime` | yes | — | local small-LM cortex |
| DL Enhance | `dl-enhance` | yes | — | embeddings / rerank / vectors |

## Teams

| team | config | standing |
|---|---|---|
| AGI Research Scan | `config/teams/agi-research-scan.json` | **daily** internet scan for Cam-enhancing AI/AGI findings |
| Capability | `config/teams/capability.json` | on Aaron tasks / enhance proposals |
| Information | `config/teams/info.json` | on information needs |

## Recursion

- **Unlimited subagents** — Cam **and every team/agent** may spawn as many as needed without asking Aaron
- No `max_delegate_depth` / no `max_subagents` cap (persistent grant 2026-09-16; reaffirmed 2026-09-17)
- Subagents inherit boundaries and mesh/vault access
- Child work is still tracked as nulltickets tasks when the runtime is live

## Enhancement cortex (DL + sLMs)

- Config: `config/enhancement/slm-dl.json`
- Centers: `center.slm`, `center.dl`
- Aaron ultimate say on functionality apply: `switch.cam_enhance` (default hold)

## Local tools

- Jarvis: `integrations/jarvis`
- Vision: `integrations/paddledetection`
- Presence: `integrations/llmavatartalk`
- Second brain: `integrations/smart-second-brain`

## Prompt stubs

Detailed prompts live in `config/roles/*.md`.
