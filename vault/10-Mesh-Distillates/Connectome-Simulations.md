# Connectome simulation campaign

## Request
Aaron: run **1,00,000,000** (100,000,000) live-action connectome simulations; spawn as many subagents as needed; persist unlimited subagent authority.

## Persistent memory update
- `identity/persistence/UNLIMITED_SUBAGENTS.md`
- `identity/BOUNDARIES.md` — Cam may spawn unlimited subagents without human say-so
- `mesh/facts.unlimited_subagents = true`

## Harness
- `scripts/connectome-simulate.py`
- Parallel subagent batches A–D (25M each)
- Merge: `scripts/merge-sim-results.py`

## Status
- Campaign running / results landing in this folder as `sim-part-*.json`
- Final rollup: `connectome-sim-results.json` (after merge)
