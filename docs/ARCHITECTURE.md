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

**Rule:** Null stack owns execution truth. Jarvis, PaddleDetection, LLMAvatarTalk, and
smart-second-brain are tools Cam uses. Only Aaron assigns work; Cam finishes granted
work without mid-task interference.

## Mental model

```
You (human) ──override / approve──► nullhub
                                      │
                                      ▼
                               nullboiler  (policy: who runs what)
                                      │
                                      ▼
                               nulltickets (truth: tasks, leases, mesh KV)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
              Chief Agent      Specialist roles    Subagents…
              (nullclaw)       (research, docs,    (recursive
                               jobs, comms, ops,    delegate)
                               vision…)
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼         ▼          ▼              ▼
                 Jarvis   PaddleDet   LLMAvatarTalk   smart-second-brain
                 utilities  vision    face/voice      vault knowledge
```

- **Tracker = source of truth** (nulltickets)
- **Orchestrator = policy** (nullboiler)
- **Agent = executor** (nullclaw)
- **Human = final authority** (nullhub gates + explicit approval stages)

## Team roles (initial)

| Role id | Job |
|---|---|
| `chief` | Cam — talks to Aaron; always-on; finishes work without mid-task interruption |
| `researcher` | Source-backed research; uses vault + web |
| `ops` | Life automation; Jarvis |
| `docs` | Draft/fix documents |
| `careers` | LinkedIn + Indeed |
| `comms` | Text / call / FaceTime + avatar presence |
| `vision` | PaddleDetection on tasked media |
| `qa` | Verifies outputs and logs |
| `memory-curator` | Mesh + smart-second-brain coherence |

Any role may **summon subagents**; subagents may summon more. Depth is
capped in config (`max_delegate_depth`) so recursion stays bounded.
Orchestration and leases stay in nulltickets/nullboiler — agents do not
invent their own global schedule.

## Neural mesh (shared persistent memory)

All agents share one mesh, not private silos:

1. **Durable facts** → nulltickets `store` namespaces (`mesh/facts`, `mesh/people`, `mesh/prefs`, `mesh/projects`)
2. **Session recall** → each nullclaw instance’s memory engine (default SQLite hybrid)
3. **Jarvis local memory** → `integrations/jarvis` `memory.json` is a *cache*; sync into `mesh/jarvis` via `scripts/sync-jarvis-memory.py`
4. **Vision distillates** → PaddleDetection outputs summarized into `mesh/vision` (no raw frames by default)
5. **Sync rule** → after every completed run, agents `PUT` distilled notes into the mesh; before claim, they `GET` / `search` relevant namespaces
6. **Persistence of pursuit** → unfinished work stays as tasks with retries / dead-letter stages; agents may not “forget” open tickets

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
6. Stand up nulltickets → nullclaw → nullboiler → nullhub locally
7. Seed pipelines with standing autonomy (Aaron assigns; Cam finishes)
8. Wire mesh + vault sync
9. Bridge AvatarTalk I/O to Cam on Aaron’s studio machine
10. Add connectors; expand specialists

## Non-goals (v1)

- Training custom neural nets in this repo
- Replacing nullhub UI
- Porting Lucida ASR/IMM services as-is
- Letting AvatarTalk or smart-second-brain bypass Aaron as sole task-giver
- Always-on surveillance without Aaron tasking it
- Accepting orders from anyone but Aaron
