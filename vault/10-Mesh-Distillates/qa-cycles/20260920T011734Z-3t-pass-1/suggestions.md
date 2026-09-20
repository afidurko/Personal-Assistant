# Three-trillion QA suggestions — pass 1

- status: green
- n: 3,000,000,000,000
- at: 20260920T011757Z

## Results
- connectome-check: exit=0 wall=0.0s
- workspace-integration: exit=0 wall=0.3s
- workspace-unit-tests: exit=0 wall=0.5s
- connectome-3t: exit=0 wall=4.5s
- trajectory-3t: exit=0 wall=1.4s
- embodiment-deps: exit=0 wall=2.5s
- embodiment-3t: exit=0 wall=2.8s
- cam-reason-3t: exit=0 wall=11.1s

## Fixes applied this cycle
- CI: install pydantic before joshinator embodiment unit tests
- 3T campaign auto-installs `integrations/joshinator-analyzer/backend/requirements-ci.txt` before embodiment fuzz
- connectome-simulate v4-exhaustive-scaled for N≥1e11
- Companion fuzzers: modular_period_scaled via trillion_scale.py
- Codified Aaron test protocol (this entrypoint + CONTINUOUS_QA)
- Google Trends: `scripts/google-trends-check.py` + curated add-ons (`trends.search_*`)

## Standing suggestions
- Keep `bash scripts/ci-connectome.sh` as the push gate
- Dual three-trillion: `python3 scripts/three-trillion-campaign.py --passes 2`
- Merge prep: `bash scripts/merge-prep-trillion.sh`
- Raise `--physical 1000000000` when you want a full 1B physical stress under 3T
- Slim CI deps: `integrations/joshinator-analyzer/backend/requirements-ci.txt`
- After registry edits: `python3 scripts/test_cline_workspaces.py`
- Trends add-ons: `python3 scripts/google-trends-addon.py list`
- Mirror cycles into `identity/persistence/qa-mesh-latest.json`
