# QA cycle suggestions

- sims: 2000000
- passed: 2000000 failed: 0
- throughput: 1407891.7265935945 sims/s
- missing_edges: 0

## Findings
- none — campaign green

## Improvement ideas
- Cover orphan senses (email, vision, jarvis, mesh, vault) with real hotspots
- Validate synapse edges in the hot loop under a --strict-edges mode for CI
- Add progress heartbeats every N million sims for long campaigns
- Weight sense sampling by real traffic mix instead of uniform
- Keep simulator v2 path tables; avoid re-parsing JSON inside workers
