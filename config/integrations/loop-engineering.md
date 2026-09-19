# Loop Engineering integration — design loops that prompt Cam’s agents

Source: [afidurko/loop-engineering](https://github.com/afidurko/loop-engineering)  
Path: [`integrations/loop-engineering`](../../integrations/loop-engineering) (git submodule)  
Upstream: [cobusgreyling/loop-engineering](https://github.com/cobusgreyling/loop-engineering)

## Role in the team

Loop Engineering is Cam’s **agent-loop control system** — patterns, readiness scoring,
budget/state spine, and standing automations. It is **not** the brain and **not** a
free pass to auto-merge.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw (Cam) |
| Task queue / mesh truth | nulltickets |
| Coding edits | Cline (`motor.cline`) |
| Connectome QA campaign | `scripts/qa-loop.py` |
| Loop patterns / audit / schedule spine | **loop-engineering** (`motor.loop`) |

**All Cam roles and subagents** may invoke `motor.loop` for triage, audit, cost,
and L1 report loops. L2+ auto-fix stays gated (worktree + verifier + Aaron-raised level).

## Connectome

```text
sense.loop.tick → area.cingulate / center.qa → switch.autonomy
               → motor.loop (+ motor.mesh, motor.cline, motor.vault)
```

Hotspot: `hotspot.loop_engineering`  
Config: [`loop-engineering.json`](loop-engineering.json)

## Runtime surface

| Piece | Path |
|---|---|
| Integration config | `config/integrations/loop-engineering.json` |
| Cam pattern map | `config/loops/patterns.json` |
| Spine files | `LOOP.md` · `STATE.md` · `loop-budget.md` · `loop-run-log.md` |
| Wiring check | `scripts/loop-check.py` |
| Audit wrapper | `scripts/loop-audit.py` |
| Loop runner | `scripts/loop-run.py` |
| Mesh packer | `scripts/pack-loop-result.py` |
| MCP | `scripts/cam-mcp-server.py` → `loop_check` / `loop_audit` / `loop_run` |
| Mesh namespace | `mesh/loops` |
| Vault | `vault/03-Projects/loop-engineering/` |

## Enable

```bash
git submodule update --init integrations/loop-engineering
python3 scripts/loop-check.py
python3 scripts/loop-audit.py --suggest
python3 scripts/loop-run.py --pattern daily-triage --level L1
```

## CLI

```bash
# Wiring (no network)
python3 scripts/loop-check.py

# Loop Ready score (local CLI under submodule)
python3 scripts/loop-audit.py
python3 scripts/loop-audit.py --suggest
python3 scripts/loop-audit.py --json

# Standing Cam loops (assistant side)
python3 scripts/loop-run.py --pattern daily-triage --level L1
python3 scripts/loop-run.py --pattern qa-cycle --level L1 --dry-run
python3 scripts/loop-run.py --list

# Pack last run into mesh/loops
python3 scripts/pack-loop-result.py --from-latest
```

## Patterns Cam automates (week one = L1)

| Pattern | Cadence | Cam action |
|---|---|---|
| Daily Triage | daily | Health + connectome check + STATE.md report |
| QA Cycle | standing | Bridge to `qa-loop.py`; append run-log |
| PR Babysitter | opt-in | L1 watch/report via Cline schedule (no auto-merge) |
| Post-Merge Cleanup | weekly | Suggest-only ticket list |
| Issue Triage | daily | Propose-only findings into STATE.md |

## How every agent uses it

1. Aaron tasks Cam (or a standing schedule fires).
2. `connectome-route.py` may select `hotspot.loop_engineering`.
3. Agents run `scripts/loop-run.py` / `loop-audit.py` or Cam MCP tools.
4. Outcomes update `STATE.md` + `loop-run-log.md` and mirror to `mesh/loops`.
5. Coding fixes still go through `motor.cline` in a worktree — never free-merge.

## Mesh bridge

| Namespace | Content |
|---|---|
| `mesh/loops` | audit scores, triage reports, pattern runs |
| `mesh/runs` | qa-cycle bridges + schedule ticks |
| `mesh/cline` | PR babysitter / fix attempts via Cline |

## Boundaries

- Week-one default: **L1 report-only** — no auto-fix, no auto-merge
- Kill switch / `switch.autonomy` hold pauses new motor fires
- Never commit secrets; budget caps live in `loop-budget.md`
- Prefer Jarvis for trivial chores; prefer loop-engineering for recurring agent control
- Prefer Cline for multi-file edits spawned from an L2+ loop after Aaron raises level

## Cross-workspace checklist

1. `persist-import` (brings mesh-seed + integration config)
2. `git submodule update --init integrations/loop-engineering`
3. Confirm `LOOP.md` / `STATE.md` / `loop-budget.md` / `loop-run-log.md` at repo root
4. `python3 scripts/loop-check.py` and `python3 scripts/workspace-integration-check.py`
5. Optional: `python3 scripts/sync-cline-schedules.py --apply-cache --print-commands`
