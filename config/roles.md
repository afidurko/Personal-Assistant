# Role roster

| role | agent_role string | summons subagents | team | notes |
|---|---|---|---|---|
| Cam (Chief) | `chief` | yes | — | always-on; finishes without mid-task interference |
| Researcher | `researcher` | yes | — | citations; vault + **Google Scholar** |
| Life Ops | `ops` | yes | — | Jarvis |
| Documents | `docs` | yes | — | drafts/fixes |
| Coding | `coding` | yes | — | Cline effector — shared by all agents |
| Careers | `careers` | yes | — | LinkedIn + Indeed |
| Comms | `comms` | yes | — | text/call/FaceTime + avatar + **Inkbox** identity |
| Vision | `vision` | yes | — | PaddleDetection when tasked |
| QA | `qa` | yes | — | verifies + logs |
| Memory Curator | `memory-curator` | yes | — | mesh + smart-second-brain |
| AGI Scout | `agi-scout` | yes | `team.agi-research-scan` | daily AI/AGI paper scan lead |
| AGI Analyst | `agi-analyst` | yes | `team.agi-research-scan` | Cam-relevance scoring |
| AGI Synthesist | `agi-synthesist` | yes | `team.agi-research-scan` | map findings → Cam proposals |
| Capability Broker | `capability-broker` | yes | `team.capability` | task + enhance brokerage |
| Task Executor | `task-executor` | yes | `team.capability` | concrete work units |
| Info Retriever | `info-retriever` | yes | `team.info` | vault→mesh→**Scholar**→**public-apis**→web facts |
| SLM Runtime | `slm-runtime` | yes | — | local small-LM cortex |
| DL Enhance | `dl-enhance` | yes | — | embeddings / rerank / vectors |
| Tool Creator | `tool-creator` | yes | `team.tooling` | design/register tools (HAAS pattern) |
| Tool User | `tool-user` | yes | `team.tooling` | run registered tools under switches |

## Teams

| team | config | standing |
|---|---|---|
| AGI Research Scan | `config/teams/agi-research-scan.json` | **daily** internet scan for Cam-enhancing AI/AGI findings |
| Capability | `config/teams/capability.json` | on Aaron tasks / enhance proposals |
| Information | `config/teams/info.json` | on information needs |
| Tooling | `config/teams/tooling.json` | create/run tools; boss/worker synapse ops |

## Recursion

- **Unlimited subagents** — Cam **and every team/agent** may spawn as many as needed without asking Aaron
- No `max_delegate_depth` / no `max_subagents` cap (persistent grant 2026-09-16; reaffirmed 2026-09-17)
- **Privilege inheritance** — child privileges ⊆ parent; spawn at `parent.level + 1`; no escalation (`config/swarm/privileges.json`)
- **Lineage terminate** — ancestors (or Aaron kill) may cancel descendants
- Subagents inherit boundaries and mesh/vault access
- Child work is still tracked as nulltickets tasks when the runtime is live
- Boss/worker primitives: `config/swarm/primitives.json`
- **Any role may invoke Cline** (`motor.cline`) for coding — not siloed to `coding`
- **Any role may invoke public-apis** (`motor.public_apis`) for free API discovery — not siloed to tooling
- **Outbound Inkbox** (`motor.inkbox`) is gated by `switch.outbound` — prefer `comms`; do not free-send from Cline

## Enhancement cortex (DL + sLMs)

- Config: `config/enhancement/slm-dl.json`
- Centers: `center.slm`, `center.dl`
- Aaron ultimate say on functionality apply: `switch.cam_enhance` (default hold)

## HAAS → Cam (patterns only)

- Docs: `docs/HAAS_CAM_PATTERNS.md`
- Swarm configs: `config/swarm/`
- Validate: `python3 scripts/swarm-check.py`

## Local tools

- Jarvis: `integrations/jarvis`
- Cline: `integrations/cline` (all agents / all workspaces)
- Public APIs: `integrations/public-apis` (all agents — free API catalog)
- Inkbox: `integrations/inkbox` (agent identity — email/phone/vault/tunnels; outbound gated)
- Vision: `integrations/paddledetection`
- Presence: `integrations/llmavatartalk`
- Local speech: `integrations/voicestudio`
- Second brain: `integrations/smart-second-brain`
- Google Scholar: `config/integrations/google-scholar.md` (SerpAPI bridge)
- Cartography: `integrations/swiftguide` (mind maps + iOS stack)
- Tool registry: `config/tools/registry.json`

## Prompt stubs

Detailed prompts live in `config/roles/*.md`.
