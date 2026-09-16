# Personal-Assistant — Cam for Aaron

Cam is Aaron’s human-governed AI team for life automation, source-backed research,
documents, job search (LinkedIn + Indeed), and approved outbound contact
(text / call / FaceTime).

## Design in one paragraph

We run on the **Null stack** for efficiency: **nullclaw** executes,
**nulltickets** remembers work and shared mesh memory, **nullboiler**
schedules the team, **nullhub** is where **Aaron** stays in charge.
**Jarvis** (submodule) is the local CLI toolbelt for deterministic chores.
**PaddleDetection** (submodule, `release/2.9`) is vision inference on media Aaron approves.
OpenClaw/Assistant- and Lucida inspire connectors and specialist roles only —
their heavy runtimes are not the core.

**Persistence:** Cam’s identity + mesh seed export/import across this and future
workspaces — see [docs/PERSISTENCE.md](docs/PERSISTENCE.md).

Full decision record: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Current phase

Session 1 answered. Profile compiled. Next: wire live Null stack in priority order.

→ Profile: [identity/PROFILE.md](identity/PROFILE.md)  
→ Boundaries: [identity/BOUNDARIES.md](identity/BOUNDARIES.md)

## Stack (target)

```text
Aaron → nullhub (approve / override)
        → nullboiler (who runs what)
          → nulltickets (tasks + mesh KV)
            → Cam / nullclaw agents (specialists + recursive subagents)
                → Jarvis CLI plugins (local utilities)
                → PaddleDetection (vision on approved media)
                → LinkedIn + Indeed (careers watch, gated submit)
```

## Repo layout

```text
docs/                         architecture, persistence
identity/                     Aaron/Cam profile, answers, persistence bundle
config/                       roles, connectors, priority-boot
integrations/jarvis/          Jarvis submodule
integrations/paddledetection/ PaddleDetection @ release/2.9
scripts/                      persist + mesh helpers
```

## Integrations

```bash
git submodule update --init --recursive
python3 scripts/persist-export.py --seed-only
# optional portable zip:
python3 scripts/persist-export.py --out /tmp/cam-persistence.zip
```

## Principles

1. Aaron has ultimate say.
2. Shared persistent mesh memory across agents and future workspaces.
3. Tasks queue and retry until done or Aaron cancels.
4. Research cites sources.
5. Simplest efficient code — prefer config over frameworks.
6. Outbound contact, cameras, money, and irreversible actions are approval-gated.

## Status

Identity captured (Aaron / Cam / EST). Capabilities enabled with gates.
Persistence feature added. Runtime install next per `config/priority-boot.json`.
