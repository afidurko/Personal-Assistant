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

## Sentinel (Muse pattern)

After switches and trajectory policies, `scripts/cam_sentinel.py` decides allow / ask / deny
per motor and journals the intent before any effect runs (`data/runtime/journal/`).

- `read` / `write_local` motors: allow by policy
- `egress` / `spend` / `self_modify` motors: ask unless an Aaron grant or an act switch covers them
- Plans that read untrusted input (email, inbound Inkbox mail, listings, web feeds, catalogs)
  are **tainted** — standing grants stop covering them, `perpetual` is never offered
- Guardrail paths only get `once`
- `python3 scripts/cam-sentinel.py pending | approve | deny | ledger | resume-check`

See [MUSE_CAM_PATTERNS.md](MUSE_CAM_PATTERNS.md).

## References

- `LOOP.md` · `loop-budget.md` · `loop-constraints.md`
- `config/integrations/loop-engineering.md`
- `config/connectome/sentinel-policy.json`
