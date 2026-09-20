# Three-trillion QA suggestions — pass 1

- status: green
- n: 3,000,000,000,000
- at: 20260920T185017Z

## Results
- connectome-check: exit=0 wall=0.0s
- workspace-integration: exit=0 wall=0.3s
- workspace-unit-tests: exit=0 wall=0.5s
- presence-check: exit=0 wall=0.0s
- higgsfield-check: exit=0 wall=0.4s
- trajectory-policy-check: exit=0 wall=0.1s
- connectome-3t: exit=0 wall=6.7s
- trajectory-3t: exit=0 wall=3.0s
- embodiment-deps: exit=0 wall=0.4s
- embodiment-3t: exit=0 wall=4.2s
- cam-reason-3t: exit=0 wall=17.3s

## Fixes applied this cycle
- CI: install pydantic before joshinator embodiment unit tests
- 3T campaign auto-installs `integrations/joshinator-analyzer/backend/requirements-ci.txt` before embodiment fuzz
- connectome-simulate v4-exhaustive-scaled for N≥1e11
- Companion fuzzers: modular_period_scaled via trillion_scale.py
- Codified Aaron test protocol (this entrypoint + CONTINUOUS_QA)
- Google Trends: `scripts/google-trends-check.py` + curated add-ons (`trends.search_*`)
- Presence: Higgsfield Speak clips rejected — portrait + A2F only (`scripts/presence-check.py`)
- Trajectory: `higgsfield_rejected_for_cam_face` strips Speak clips from speak plans

## Standing suggestions
- Keep `bash scripts/ci-connectome.sh` as the push gate
- Dual three-trillion: `python3 scripts/three-trillion-campaign.py --passes 2`
- Merge prep: `bash scripts/merge-prep-trillion.sh`
- Raise `--physical 1000000000` when you want a full 1B physical stress under 3T
- Slim CI deps: `integrations/joshinator-analyzer/backend/requirements-ci.txt`
- After registry edits: `python3 scripts/test_cline_workspaces.py`
- Trends add-ons: `python3 scripts/google-trends-addon.py list`
- Presence add-on: `python3 scripts/presence-check.py` (no Speak overlay on Cam’s face)
- Higgsfield stays rejected: `python3 scripts/higgsfield-check.py`
- Mirror cycles into `identity/persistence/qa-mesh-latest.json`
