# Three-trillion QA suggestions — pass 1

- status: needs_work
- n: 3,000,000,000,000
- at: 20260919T214733Z

## Results
- connectome-check: exit=0 wall=0.0s
- workspace-integration: exit=0 wall=0.3s
- workspace-unit-tests: exit=0 wall=0.5s
- connectome-3t: exit=0 wall=4.6s
- trajectory-3t: exit=0 wall=1.4s
- embodiment-3t: exit=1 wall=0.1s
- cam-reason-3t: exit=0 wall=11.0s

## Fixes applied this cycle
- CI: install pydantic before joshinator embodiment unit tests
- connectome-simulate v4-exhaustive-scaled for N≥1e11
- Companion fuzzers: modular_period_scaled via trillion_scale.py
- Codified Aaron test protocol (this entrypoint + CONTINUOUS_QA)

## Standing suggestions
- Keep `bash scripts/ci-connectome.sh` as the push gate
- Dual three-trillion: `python3 scripts/three-trillion-campaign.py --passes 2`
- Merge prep: `bash scripts/merge-prep-trillion.sh`
- Raise `--physical 1000000000` when you want a full 1B physical stress under 3T
- Slim CI deps: `integrations/joshinator-analyzer/backend/requirements-ci.txt`
- After registry edits: `python3 scripts/test_cline_workspaces.py`
- Mirror cycles into `identity/persistence/qa-mesh-latest.json`
