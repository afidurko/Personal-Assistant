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

**Rule:** if two repos solve the same problem, pick the Null path (Zig, tiny,
explicit contracts). Borrow OpenClaw/Lucida *behaviors* as external channel
plugins or agent roles — never fork their full runtimes into this repo.

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
                               jobs, comms…)        delegate)
```

- **Tracker = source of truth** (nulltickets)
- **Orchestrator = policy** (nullboiler)
- **Agent = executor** (nullclaw)
- **Human = final authority** (nullhub gates + explicit approval stages)

## Team roles (initial)

| Role id | Job |
|---|---|
| `chief` | Talks to you; breaks work into tasks; never bypasses your approvals |
| `researcher` | Source-backed research; every claim cites URL/title/date |
| `ops` | Life automation, calendars, reminders, recurring chores |
| `docs` | Draft/fix documents; diff before apply |
| `careers` | Job search, applications, outreach drafts (approval-gated) |
| `comms` | SMS / iMessage / call / FaceTime bridges when you want contact |
| `qa` | Verifies outputs, sources, and that human gates were honored |
| `memory-curator` | Keeps the neural mesh coherent; merges/dedupes memories |

Any role may **summon subagents**; subagents may summon more. Depth is
capped in config (`max_delegate_depth`) so recursion stays bounded.
Orchestration and leases stay in nulltickets/nullboiler — agents do not
invent their own global schedule.

## Neural mesh (shared persistent memory)

All agents share one mesh, not private silos:

1. **Durable facts** → nulltickets `store` namespaces (`mesh/facts`, `mesh/people`, `mesh/prefs`, `mesh/projects`)
2. **Session recall** → each nullclaw instance’s memory engine (default SQLite hybrid)
3. **Sync rule** → after every completed run, agents `PUT` distilled notes into the mesh; before claim, they `GET` / `search` relevant namespaces
4. **Persistence of pursuit** → unfinished work stays as tasks with retries / dead-letter stages; agents may not “forget” open tickets

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
2. Stand up nulltickets → nullclaw → nullboiler → nullhub locally
3. Seed pipelines: research, docs, careers, life-ops (all with human gates)
4. Wire mesh namespaces + curator role
5. Add connectors one at a time with approval tests
6. Only then expand specialist depth / recursive subagents

## Non-goals (v1)

- Training custom neural nets
- Replacing nullhub UI
- Porting Lucida ASR/IMM services as-is
- Autonomous spending or unsupervised external outreach
