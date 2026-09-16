# Connectome simulation campaign

## Request
Aaron: run billion-scale live-action connectome simulations; spawn as many subagents as needed; persist unlimited subagent + continuous QA authority.

## Persistent memory
- `identity/persistence/UNLIMITED_SUBAGENTS.md`
- `identity/persistence/CONTINUOUS_QA.md`
- `identity/BOUNDARIES.md`
- `mesh/facts.unlimited_subagents = true`
- `mesh/facts.continuous_qa = true`

## Harness
- `scripts/connectome-simulate.py` (v2 simplified) — sense→center→switch→motor→feedback
- `scripts/qa-loop.py` — detect → dispatch team → fix → rerun
- Workers = parallel subagent processes

## Baseline (100,000,000 — pre-rewrite)
| Metric | Value |
|---|---|
| Passed / Failed | 100,000,000 / 0 |
| Throughput | ~1.19M sims/sec |
| Wall time | ~84s (4 workers) |

## Simulator v2 smoke (5,000,000 — post-rewrite, strict edges)
| Metric | Value |
|---|---|
| Passed / Failed | 5,000,000 / 0 |
| Missing synapse edges | 0 |
| Throughput | ~1.28M sims/sec |

## Fixes applied this cycle
- Multi-hotspot pathways per sense (chat→research **and** docs)
- Orphan-sense hotspots: email, vision, jarvis, vault, mesh
- Synapse fill + pathway simplify (no chained motors)
- Continuous QA loop + campaign docs

See `Continuous-QA-Campaign.md` for full working/not-working + suggestions.
