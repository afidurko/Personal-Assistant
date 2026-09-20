# Loop Engineering (Cam)

Cam automates agent loops using the [loop-engineering](https://github.com/afidurko/loop-engineering) patterns.

## Commands

```bash
python3 scripts/loop-check.py
python3 scripts/loop-audit.py --suggest
python3 scripts/loop-run.py --pattern daily-triage --level L1
python3 scripts/loop-run.py --list
```

## Standing schedules

See `config/workspaces/schedules.json`:

- `cam-daily-loop-triage`
- `cam-weekly-loop-post-merge`
- `cam-loop-pr-babysitter` (disabled until Aaron raises trust)

## Policy

`config/integrations/loop-engineering.md`
