# Three-trillion QA suggestions — pass 2

- status: green
- n: 3,000,000,000,000
- at: 20260920T041131Z

## Results
- connectome-check: exit=0 wall=0.0s
- workspace-integration: exit=0 wall=0.3s
- workspace-unit-tests: exit=0 wall=0.5s
- higgsfield-check: exit=0 wall=0.1s
- connectome-3t: exit=0 wall=4.3s
- illa-desktop-unit: exit=0 wall=0.1s
- illa-electron-check: exit=0 wall=0.0s
- trajectory-3t: exit=0 wall=1.7s
- embodiment-deps: exit=0 wall=0.4s
- embodiment-3t: exit=0 wall=2.6s
- cam-reason-3t: exit=0 wall=10.6s
- illa-desktop-3t: exit=0 wall=2.7s

## Fixes applied this cycle
- CI: install pydantic before joshinator embodiment unit tests
- 3T campaign auto-installs `integrations/joshinator-analyzer/backend/requirements-ci.txt` before embodiment fuzz
- connectome-simulate v4-exhaustive-scaled for N≥1e11
- Companion fuzzers: modular_period_scaled via trillion_scale.py
- Codified Aaron test protocol (this entrypoint + CONTINUOUS_QA)
- Google Trends: `scripts/google-trends-check.py` + curated add-ons (`trends.search_*`)
- Higgsfield: `scripts/higgsfield-check.py` + dry-run `higgsfield-run.py` + mesh pack
- Higgsfield OCL: `no_higgsfield_without_aaron` / jobs / outbound burst policies

## Standing suggestions
- Keep `bash scripts/ci-connectome.sh` as the push gate
- Dual three-trillion: `python3 scripts/three-trillion-campaign.py --passes 2`
- Merge prep: `bash scripts/merge-prep-trillion.sh`
- Raise `--physical 1000000000` when you want a full 1B physical stress under 3T
- Slim CI deps: `integrations/joshinator-analyzer/backend/requirements-ci.txt`
- After registry edits: `python3 scripts/test_cline_workspaces.py`
- Trends add-ons: `python3 scripts/google-trends-addon.py list`
- Higgsfield: `python3 scripts/higgsfield-run.py --doctor` then pack to `mesh/runs`
- Higgsfield train jobs stay enhance-gated; never free-spend GPU from Cline
- Mirror cycles into `identity/persistence/qa-mesh-latest.json`
- ILLA desktop: `python3 scripts/illa-desktop-billion-fuzz.py --n 3000000000000`
- ILLA unit: `python3 scripts/test_illa_desktop.py`
- Keep electron-builder pin exact `26.16.1` (not fork master / v27)
- After packaging edits: `npm --prefix integrations/illa-desktop run check:pin`
