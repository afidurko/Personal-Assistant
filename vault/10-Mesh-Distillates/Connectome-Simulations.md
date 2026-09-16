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
- `scripts/connectome-simulate.py` (v2 simplified + audit fixes)
- `scripts/qa-loop.py` — detect → dispatch team → fix → rerun
- Workers = parallel subagent processes

## Pass 1 — 1,000,000,000 (pre-rewrite harness in-flight binary)
Source: `connectome-sim-1b-pass1.json`

| Metric | Value |
|---|---|
| Simulations | 1,000,000,000 |
| Passed / Failed | **1,000,000,000 / 0** |
| Kill-switch holds | 2,000,738 |
| Non-Aaron holds | 111,209 |
| Feedback OK | 997,888,053 |
| Throughput | ~1.79M sims/sec |
| Wall time | ~559s (4 workers) |
| Exit | 0 |

**Verdict:** green — antagonistic switches behaved; no pathway failures.

## Baseline (100,000,000 — earlier)
| Passed / Failed | 100,000,000 / 0 |
| Throughput | ~1.19M sims/sec |

## Simulator v2 smoke (post-rewrite / post-audit)
- 5M + 2M + 1M strict-edge smokes: **0 fail**, **0 missing edges**
- Route regressions: `--no-autonomy` / `--kill` → empty motors

## Pass 2
In progress → `connectome-sim-1b-pass2.json` (v2 + audit-fixed graph).

See `Continuous-QA-Campaign.md` and `qa-cycles/AUDIT-FIX-20260916.md`.
