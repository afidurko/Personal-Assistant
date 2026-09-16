# Personal-Assistant — Cam for Aaron

Cam is Aaron’s human-governed AI team for life automation, source-backed research,
documents, job search (LinkedIn + Indeed), and approved outbound contact
(text / call / FaceTime) with optional talking avatar presence.

## Design in one paragraph

We run on the **Null stack** for efficiency: **nullclaw** executes,
**nulltickets** remembers work and shared mesh memory, **nullboiler**
schedules the team, **nullhub** is where **Aaron** stays in charge.
**Jarvis** is the local CLI toolbelt. **PaddleDetection** is gated vision.
**LLMAvatarTalk** gives Cam face + voice (RIVA + Audio2Face; optional Metahuman).
Only Aaron may task, authorize, or approve.

**Persistence:** across this and future workspaces — [docs/PERSISTENCE.md](docs/PERSISTENCE.md)  
**Persona:** [docs/PERSONA.md](docs/PERSONA.md)  
**Architecture:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Current phase

Identity captured. AvatarTalk wired as presence submodule. Next: studio bring-up
(RIVA/Audio2Face) + Null stack in priority order.

→ Profile: [identity/PROFILE.md](identity/PROFILE.md)  
→ Boundaries: [identity/BOUNDARIES.md](identity/BOUNDARIES.md)

## Stack (target)

```text
Aaron → nullhub (approve / override)
        → nullboiler (who runs what)
          → nulltickets (tasks + mesh KV)
            → Cam / nullclaw agents (specialists + recursive subagents)
                → Jarvis · PaddleDetection · LinkedIn/Indeed
                → LLMAvatarTalk (hear/speak/animate Cam)
```

## Repo layout

```text
docs/                         architecture, persistence, persona
identity/                     Aaron/Cam profile, persistence bundle
config/                       roles, connectors, persona voice, priority-boot
integrations/jarvis/
integrations/paddledetection/   @ release/2.9
integrations/llmavatartalk/     Cam face/voice presence
scripts/                      persist + avatar hints
```

## Integrations

```bash
git submodule update --init --recursive
python3 scripts/persist-export.py --seed-only
bash scripts/cam-avatar-hint.sh
```

## Principles

1. Aaron has ultimate say (sole operator).
2. Shared persistent mesh memory across agents and future workspaces.
3. Tasks queue and retry until done or Aaron cancels.
4. Research cites sources.
5. Simplest efficient path — AvatarTalk for presence, Null for brain.
6. Outbound contact, cameras, money, and irreversible actions are approval-gated.

## Status

Aaron / Cam / EST locked. Capabilities enabled with gates. Persistence added.
LLMAvatarTalk submodule added for face/voice. Studio setup on Aaron’s machine next.
