# QA cycle suggestions

- status: green
- sims: 500000
- passed/failed: 500000/0
- throughput: 1380585.9643639913 sims/s
- missing_edges: 0

## Findings
- none

## After green (standing improvements)
- CI job: `--n 1_000_000 --strict-edges` smoke + nightly billion
- Progress heartbeats every N million sims for long campaigns
- Traffic-weighted sense sampling instead of uniform
- Promote `--strict-edges` as QA-loop default once synapses stay green
- Mirror each team_dispatch / cycle summary into mesh persistence
