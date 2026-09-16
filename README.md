# Personal-Assistant

Your human-governed AI team for life automation, source-backed research,
documents, job search, and approved outbound contact (text / call / FaceTime).

## Design in one paragraph

We run on the **Null stack** for efficiency: **nullclaw** executes,
**nulltickets** remembers work and shared mesh memory, **nullboiler**
schedules the team, **nullhub** is where **you** stay in charge.
OpenClaw/Assistant- and Lucida inspire connectors and specialist roles only —
their heavy runtimes are not the core.

Full decision record: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Current phase: know you first

Before wiring agents, complete the identity questionnaire:

→ **[identity/QUESTIONNAIRE.md](identity/QUESTIONNAIRE.md)**

Answer in chat or edit the file. Partial answers are fine.

## Stack (target)

```text
you → nullhub (approve / override)
        → nullboiler (who runs what)
          → nulltickets (tasks + mesh KV)
            → nullclaw agents (chief + specialists + recursive subagents)
```

## Repo layout

```text
docs/           architecture and policies
identity/       questionnaire, profile, boundaries, goals
config/         roles, pipelines, connector policies
scripts/        thin local bootstrap helpers (later)
```

## Principles

1. Human has ultimate say.
2. Shared persistent mesh memory across all agents.
3. Tasks queue and retry until done or you cancel.
4. Research cites sources.
5. Simplest efficient code — prefer config over frameworks.
6. Outbound contact and irreversible actions are approval-gated.

## Status

Foundation docs only. Runtime install comes after identity capture.
