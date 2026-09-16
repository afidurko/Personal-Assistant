# QA cycle suggestions

- status: green
- sims: 200000
- passed/failed: 200000/0
- throughput: 1022963.447668225 sims/s
- missing_edges: 0

## Findings
- none

## After green (standing improvements)
- CI: `python3 scripts/connectome-check.py` + `--n 1000000 --strict-edges` on push
- Nightly billion fuzz via `qa-loop.py --n 1000000000 --cycles 1`
- Progress heartbeats every 50M sims for long campaigns
- Traffic-weighted sense sampling (chat-heavy)
- Mirror QA cycle events into mesh persistence
- When Mac is available: flip Tailscale preferred host to aaron-mac
