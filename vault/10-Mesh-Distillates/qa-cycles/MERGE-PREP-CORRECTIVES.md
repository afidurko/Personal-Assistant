# Merge-prep QA campaign — corrective measures

## Corrective (shipped this loop)
1. `scripts/connectome-check.py` — static graph gate (no billion fuzz required to catch missing edges)
2. `qa-loop.py` runs static check **before** each sim cycle; `--strict-edges` by default
3. Auto-fill missing hotspot synapses on failure, then rerun
4. Standing suggestions written every cycle under `qa-cycles/*/suggestions.md`

## Suggestive (post-merge / standing)
- CI on push: `connectome-check.py` + `connectome-simulate.py --n 1000000 --strict-edges`
- Nightly: `qa-loop.py --n 1000000000 --cycles 1`
- Heartbeats every 50M sims
- Traffic-weighted sense sampling
- Mesh-mirror of QA events
- When Mac ready: flip Tailscale host to `aaron-mac`

## Campaign files
- Pass A: `vault/10-Mesh-Distillates/connectome-sim-1b-merge-a.json`
- Pass B: `vault/10-Mesh-Distillates/connectome-sim-1b-merge-b.json`
- Verdict: `vault/10-Mesh-Distillates/MERGE_READINESS.md`
