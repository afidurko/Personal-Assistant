# LOOP.md — Cam / Personal-Assistant

How this repository is operated with [loop-engineering](https://github.com/afidurko/loop-engineering) patterns.

Cam designs loops that prompt agents. Aaron remains sole operator. Week-one mode: **L1 report-only**.

## Active loops

### Daily Triage (L1 — automated + report)
- Cadence: daily (`cam-daily-loop-triage` in `config/workspaces/schedules.json`)
- Runner: `python3 scripts/loop-run.py --pattern daily-triage --level L1`
- Neuron: `neuron.loop_triage` · Hotspot: `hotspot.loop_engineering`
- Updates: `STATE.md`, `loop-run-log.md`, `mesh/loops`
- Phase: Report-only. No auto-fix.

### QA Cycle (standing — Cam conflict monitor)
- Cadence: standing / on demand
- Bridge: `scripts/qa-loop.py` ↔ loop spine via `loop-run.py --pattern qa-cycle`
- Neuron: `neuron.qa_cycle` (ACC)
- Phase: Continuous detect → dispatch → fix → rerun (existing Cam QA). Loop spine records distillates.

### PR Babysitter (L1 — opt-in)
- Cadence: disabled by default (`cam-loop-pr-babysitter`)
- Starter: `integrations/loop-engineering/starters/pr-babysitter`
- Phase: Report open PRs / CI status. No auto-merge. Raise to L2 only after Aaron approval.

### Post-Merge Cleanup (L1 — weekly suggest)
- Cadence: weekly Sunday
- Runner: `python3 scripts/loop-run.py --pattern post-merge-cleanup --level L1`
- Phase: Suggest cleanup tickets; human/Aaron gate on architectural debt.

### Issue Triage (L1 — propose-only)
- Cadence: with daily triage
- Phase: Propose labels/priorities into STATE.md; no auto-close.

## Multi-loop priority

1. Kill switch / autonomy hold  
2. QA Cycle (regressions)  
3. Daily Triage  
4. Issue Triage  
5. Post-Merge Cleanup (off-peak)  
6. PR Babysitter (when enabled)

## Worktrees

Unattended code-change experiments run in isolated git worktrees via Cline (`motor.cline`). Discard after verifier REJECT or escalation.

## Budget & observability

- Caps: `loop-budget.md`
- History: `loop-run-log.md`
- Audit: `python3 scripts/loop-audit.py --suggest`
- Cost: `node integrations/loop-engineering/tools/loop-cost/dist/cli.js --pattern daily-triage --level L1`
- Pause: set `paused: true` in `STATE.md` or flip `switch.kill`

## Safety

- No auto-merge on `main`
- Outbound still gated by `switch.outbound` / Inkbox
- Secrets never committed
- Loop motor requires `switch.autonomy` act

## Local commands

```bash
python3 scripts/loop-check.py
python3 scripts/loop-audit.py --suggest
python3 scripts/loop-run.py --pattern daily-triage --level L1
python3 scripts/sync-cline-schedules.py --apply-cache --print-commands
```

## Safety doc

See [docs/loop-safety.md](docs/loop-safety.md). MCP connectors for Cam loops: `loop_check` / `loop_audit` / `loop_run` in `scripts/cam-mcp-server.py` (MCP required for Cline bridge; optional for L1 local runs).
