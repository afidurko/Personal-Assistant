# Loop safety (Cam)

Week-one defaults for `motor.loop` / loop-engineering integration.

## Policy

- **L1 report-only** by default (`config/loops/patterns.json`)
- No auto-merge to `main`
- No auto-fix from `scripts/loop-run.py` (L2+ refused without Aaron raise)
- Outbound remains gated by `switch.outbound` / Inkbox
- Secrets never committed; denylist paths in `loop-constraints.md`

## MCP

Cam MCP (`scripts/cam-mcp-server.py`) exposes `loop_check`, `loop_audit`, `loop_run`.
These are read/report tools under week-one gates. Live Cline edits still go through
`motor.cline` with worktree isolation.

## Pause

- `STATE.md` → `paused: true`
- `switch.kill` act
- Disable schedules in `config/workspaces/schedules.json`

## References

- `LOOP.md` · `loop-budget.md` · `loop-constraints.md`
- `config/integrations/loop-engineering.md`
