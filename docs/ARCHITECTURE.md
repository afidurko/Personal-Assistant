# Personal Assistant Architecture

This repository defines **your** personal assistant team: a human-governed,
durable, multi-agent system for life automation, research, documents, jobs,
and outbound contact (text / FaceTime / call) when needed.

## Decision: which upstreams we keep

| Upstream | Verdict | Why |
|---|---|---|
| [nullclaw](https://github.com/nullclaw/nullclaw) | **Core runtime** | Smallest efficient agent binary; tools, channels, memory engines, subagent delegate |
| [nulltickets](https://github.com/nullclaw/nulltickets) | **Task + shared memory spine** | Durable queue, leases, retries, KV + FTS — source of truth for work and mesh state |
| [nullboiler](https://github.com/nullclaw/nullboiler) | **Team orchestrator** | Schedules roles, concurrency, retries; does not own tasks or execute them |
| [nullhub](https://github.com/nullclaw/nullhub) | **Human control plane** | Install, monitor, approve, mission control — where *you* override the team |
| [Assistant- / OpenClaw](https://github.com/afidurko/Assistant-) | **Connector inspiration only** | Rich SMS / voice-call / companion-app patterns; too heavy to be the core |
| [lucida](https://github.com/claritylab/lucida) | **Role ideas only** | Speech/vision “service team” concept; Java/Thrift stack rejected for simplicity |
| [Jarvis](https://github.com/afidurko/Jarvis) | **Local CLI utility layer** | Deterministic life tools; submodule — not the brain |
| [PaddleDetection](https://github.com/afidurko/PaddleDetection) (`release/2.9`) | **Vision tool layer** | Detection on approved media; submodule — not always-on camera |
| [LLMAvatarTalk](https://github.com/afidurko/LLMAvatarTalk-An-Interactive-AI-Assistant) | **Cam presence (face/voice)** | RIVA ASR/TTS + Audio2Face (+ optional Metahuman); not a second brain |
| [smart-second-brain](https://github.com/afidurko/smart-second-brain) | **Knowledge cortex** | Obsidian vault search/graph/agents — enhances Cam’s long-term memory |
| [cline](https://github.com/afidurko/cline) | **Coding effector** | CLI/SDK/IDE agent — shared by all roles & workspaces; not the brain |

**Rule:** Null stack owns execution truth. Jarvis, Cline, PaddleDetection, LLMAvatarTalk, and
smart-second-brain are tools Cam uses. Only Aaron assigns work; Cam finishes granted
work without mid-task interference.

## Mental model

Primary architecture is the **Cam Connectome** (sensory → higher centers → switches → motor),
inspired by Berg et al. Cell 2026 Drosophila CNS mapping:

→ Full design: [docs/CONNECTOME_ARCHITECTURE.md](CONNECTOME_ARCHITECTURE.md)  
→ Maps: `config/connectome/*.json` · router: `scripts/connectome-route.py`

```
Aaron (sole task-giver)
   │
   ▼
Sensory periphery  (chat, vault, boards, calendar, ASR, vision)
   │
   ▼
Higher centers     (Cam chief, specialists, memory, nullboiler router)
   │
   ▼
Circuit switches   (autonomy / outbound / careers / presence / kill)
   │
   ├─ act  → Motor periphery (text, call, FaceTime, speak, Jarvis, docs, jobs, vault)
   └─ hold → mesh log only
```

Runtime binding:

```
You (human) ──override / kill──► nullhub / chat
                                      │
                                      ▼
                               nullboiler  (center.router)
                                      │
                                      ▼
                               nulltickets (synapses + mesh)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              Cam centers      Hotspot roles      Subagents…
              (nullclaw)       (research, jobs,   (interneurons)
                               ops, comms…)
                                      │
                    ┌──────────────────┴──────────────────┐
                    ▼      ▼       ▼         ▼            ▼
                 Jarvis  Cline  PaddleDet  AvatarTalk  smart-second-brain
                 motor   code    sense     face/voice   memory cortex
```

- **Tracker = synaptic truth** (nulltickets)
- **Orchestrator = higher-center policy** (nullboiler)
- **Agent = neuron executor** (nullclaw)
- **Human = master switch** (Aaron only)

## Team roles (initial)

| Role id | Job |
|---|---|
| `chief` | Cam — talks to Aaron; always-on; finishes work without mid-task interruption |
| `researcher` | Source-backed research; uses vault + web |
| `ops` | Life automation; Jarvis |
| `docs` | Draft/fix documents |
| `coding` | Cline-powered code edits (also invokable by every role) |
| `careers` | LinkedIn + Indeed |
| `comms` | Text / call / FaceTime + avatar presence |
| `vision` | PaddleDetection on tasked media |
| `qa` | Verifies outputs and logs |
| `memory-curator` | Mesh + smart-second-brain coherence |
| `agi-scout` | Daily AI/AGI paper scan lead (`team.agi-research-scan`) |
| `agi-analyst` | Score papers for Cam relevance |
| `agi-synthesist` | Map findings → Cam enhancement proposals |
| `capability-broker` | Task decomposition + enhance gate brokerage |
| `task-executor` | Concrete work units under standing autonomy |
| `info-retriever` | Vault → mesh → web cited information |
| `slm-runtime` | Local small-LM cortex assists |
| `dl-enhance` | Embeddings / rerank / identity / paper vectors |
| `tool-creator` | Design/register tools (`team.tooling`) |
| `tool-user` | Run registered tools under switches |

Any role or team may **summon subagents**; subagents may summon more.
Depth/count are **uncapped** (`unlimited_subagents`). Privileges **inherit as a
subset** of the parent (`config/swarm/privileges.json`); aaron_only privileges
never transfer. Ancestors may terminate lineage. Aaron retains ultimate say
over Cam functionality apply (`switch.cam_enhance`).

Teams: `config/teams/` · Brain: [docs/CAM_BRAIN.md](CAM_BRAIN.md) · AGI scan: [docs/AGI_RESEARCH_TEAM.md](AGI_RESEARCH_TEAM.md) · HAAS patterns: [docs/HAAS_CAM_PATTERNS.md](HAAS_CAM_PATTERNS.md)

## HAAS → Cam (patterns only)

Upstream: [OpenAI_Agent_Swarm](https://github.com/afidurko/OpenAI_Agent_Swarm) — **inspiration**, not runtime.

| Keep | Skip |
|---|---|
| Privilege inheritance, lineage terminate | Assistants API HAAS Python stack |
| Boss/worker synapse primitives | Supreme Oversight Board of archetypes |
| Tool-creator → tool-user team | Unsupervised root goal invention |
| Autonomy triad under Aaron gates | Heuristic imperatives as tasking |

Validate: `python3 scripts/swarm-check.py`

## Neural mesh (shared persistent memory)

All agents share one mesh, not private silos:

1. **Durable facts** → nulltickets `store` namespaces (`mesh/facts`, `mesh/people`, `mesh/prefs`, `mesh/projects`)
2. **Session recall** → each nullclaw instance’s memory engine (default SQLite hybrid)
3. **Jarvis local memory** → `integrations/jarvis` `memory.json` is a *cache*; sync into `mesh/jarvis` via `scripts/sync-jarvis-memory.py`
4. **Cline sessions** → coding distillates across workspaces in `mesh/cline` via `scripts/sync-cline-session.py`
5. **Vision distillates** → PaddleDetection outputs summarized into `mesh/vision` (no raw frames by default)
6. **Sync rule** → after every completed run, agents `PUT` distilled notes into the mesh; before claim, they `GET` / `search` relevant namespaces
7. **Persistence of pursuit** → unfinished work stays as tasks with retries / dead-letter stages; agents may not “forget” open tickets

This is the “neural meshing network”: a shared, searchable, versioned memory
plus a durable work graph — not a separate ML training stack.

## Human ultimate say

Hard rules encoded in pipelines:

- Stages marked `requires_human: true` cannot transition without your approval in nullhub (or signed CLI).
- Outbound contact (text/call/FaceTime), job applications, money moves, and sending docs externally are always gated.
- You can pause, cancel, or reassign any run; agents resume from mesh + ticket state.
- Prefer ask over act when uncertainty is high.

## Connectors strategy

Prefer nullclaw built-ins (iMessage, email, Telegram, etc.). For gaps
(FaceTime, phone call, SMS via phone):

- Implement as **external channel plugins** (stdin/stdout JSON-RPC) or device
  companion bridges — patterns borrowed from OpenClaw, running outside core.
- Document each connector in `config/connectors.md` with approval policy.

## Simplicity / efficiency bar

- No Lucida-style Java microservice mesh.
- No OpenClaw monorepo as the runtime.
- This repo holds: identity, policies, role prompts, pipelines, connector
  configs, and thin glue — not a second agent framework.
- Prefer config + prompts over new code. New code only when a contract is missing.

## Build order (after identity questionnaire)

1. Capture who you are (`identity/`) — **in progress**
2. Keep Jarvis available as local CLI utilities (`integrations/jarvis`) — **added**
3. Keep PaddleDetection for vision (`integrations/paddledetection` @ `release/2.9`) — **added**
4. Keep LLMAvatarTalk for Cam face/voice presence (`integrations/llmavatartalk`) — **added**
5. Keep smart-second-brain for vault intelligence (`integrations/smart-second-brain`) — **added**
6. Keep Cline as shared coding effector for all agents/workspaces (`integrations/cline`) — **added**
7. Workspace registry + motor runner + MCP + schedules (`config/workspaces/`, `scripts/run-cline.py`) — **added**
8. Stand up nulltickets → nullclaw → nullboiler → nullhub locally
9. Seed pipelines with standing autonomy (Aaron assigns; Cam finishes)
10. Wire mesh + vault + Cline session/ticket sync into live nulltickets
11. Bridge AvatarTalk I/O to Cam on Aaron’s studio machine
12. Add connectors; expand specialists

## Non-goals (v1)

- Training custom neural nets in this repo
- Replacing nullhub UI
- Porting Lucida ASR/IMM services as-is
- Letting AvatarTalk or smart-second-brain bypass Aaron as sole task-giver
- Always-on surveillance without Aaron tasking it
- Accepting orders from anyone but Aaron
