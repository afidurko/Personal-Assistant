# Cline integration — shared coding effector for every agent & workspace

Source: [afidurko/cline](https://github.com/afidurko/cline)  
Path: [`integrations/cline`](../../integrations/cline) (git submodule)  
Upstream product: [cline.bot](https://cline.bot) (CLI · SDK · VS Code · Desktop · JetBrains)

## Role in the team

Cline is Cam’s **autonomous coding motor** — plan/act edits, shell, multi-agent
teams, schedules, and headless CI. It is **not** the brain.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw (Cam) |
| Task queue / persistence | nulltickets |
| Scheduling (team-level) | nullboiler |
| Human override | Aaron via nullhub / kill switch |
| Code edit / repo agent sessions | **Cline** (CLI / SDK / IDE) |

**All Cam roles and subagents** may invoke `motor.cline` when the work needs
repo edits, tests, or multi-file coding — not only a dedicated coding role.
Jarvis stays the deterministic CLI utility belt; Cline owns agentic code work.

## Surfaces (pick simplest that fits)

| Surface | When |
|---|---|
| CLI (`cline` / `bun run cli`) | Headless, CI, scripts, Cam motor fire |
| `@cline/sdk` | Programmatic tools / multi-agent teams from Cam glue |
| VS Code / JetBrains / Desktop | Aaron-facing IDE sessions |
| Messaging connectors | Slack/Telegram/etc. only if Aaron wires credentials |

## Install (on Aaron’s machine / any workspace)

```bash
git submodule update --init --recursive
# Option A — published CLI
npm i -g cline
# Option B — from this submodule (Bun 1.3+ / Node ≥22)
cd integrations/cline && bun install && bun run build:sdk
# Auth (required for live turns)
cline auth   # or set ANTHROPIC_API_KEY / OPENROUTER_API_KEY / CLINE_API_KEY
cline doctor
```

Repo rules for Cline live at [`.clinerules`](../../.clinerules) so every Cline
session in this checkout (and imported workspaces) inherits Cam policy.

## How every agent uses it

1. Aaron tasks Cam (or a standing goal fires).
2. Any center may route coding through `hotspot.coding` → `switch.autonomy` → `motor.cline`.
3. Cline runs in the **target workspace path** (this repo or another Aaron-opened folder).
4. Distill outcomes into `mesh/cline` + tickets; vault notes when the work is durable.

```bash
# Headless one-shot in a workspace
cline --workspace /path/to/repo "Implement X and run tests"

# JSON for Cam/nullclaw parsers
cline --json --workspace /path/to/repo "List failing tests"

# From this submodule after build
cd integrations/cline && bun run cli -- --workspace "$PWD/../.." "doctor"
```

Bridge session distillates:

```bash
python3 scripts/sync-cline-session.py export
python3 scripts/sync-cline-session.py import --from path/to/mesh-cline.json --dry-run
```

## Mesh bridge

| Namespace | Content |
|---|---|
| `mesh/cline` | last workspace, mode (plan/act), session ids, distillates, schedule pointers |
| `mesh/runs` | run outcomes that involved Cline |
| `mesh/projects` | repos Cline has touched across workspaces |

Persistence export includes the Cline integration policy + mesh seed so **future
workspaces** restore the same coding effector without re-wiring.

## Boundaries

- Only Aaron may assign the original task; Cam/Cline finish under standing autonomy
- Kill switch silences `motor.cline` with all other motors
- No outbound messaging / job submit / spend via Cline — those stay on gated motors
- Provider API keys stay in local secrets / env — never commit
- Prefer Jarvis for trivial deterministic chores; prefer Cline for multi-file code

## Cross-workspace checklist

1. `persist-import` (or clone this repo) in the new workspace
2. `git submodule update --init integrations/cline`
3. Confirm `.clinerules` present at workspace root
4. Re-attach LLM provider credentials locally
5. `cline doctor` then a dry headless prompt
