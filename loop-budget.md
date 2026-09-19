# loop-budget.md — Cam token / autonomy caps

Week-one defaults (L1). Raise only with Aaron approval.

| Pattern | Level | Suggested daily cap (tokens) | Early exit | Auto-fix |
|---|---|---|---|---|
| daily-triage | L1 | 100000 | no | no |
| qa-cycle | L1 report | 50000 | yes | via existing qa-loop only |
| pr-babysitter | L1 | 200000 | yes | no |
| post-merge-cleanup | L1 | 200000 | no | no |
| issue-triage | L1 | 100000 | no | no |

## Hard stops

- `switch.kill` → silence `motor.loop`
- `STATE.md` `paused: true` → runner exits 0 without acting
- No auto-merge; no outbound from loop runner
- Never spend money / submit jobs from loop scripts

## Estimate

```bash
node integrations/loop-engineering/tools/loop-cost/dist/cli.js --pattern daily-triage --level L1 --cadence 1d
```
