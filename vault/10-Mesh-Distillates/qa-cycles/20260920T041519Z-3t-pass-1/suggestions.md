# Three-trillion QA suggestions — pass 1

- status: green
- n: 3,000,000,000,000
- at: 20260920T041547Z

## Results
- connectome-check: exit=0 wall=0.0s
- workspace-integration: exit=0 wall=0.3s
- workspace-unit-tests: exit=0 wall=0.5s
- cloud-agent-install: exit=0 wall=0.1s
- cam-system-unit: exit=0 wall=0.1s
- higgsfield-check: exit=0 wall=0.0s
- higgsfield-unit: exit=0 wall=0.3s
- embodiment-lite: exit=0 wall=0.1s
- connectome-3t: exit=0 wall=4.2s
- trajectory-3t: exit=0 wall=1.8s
- embodiment-deps-offline: exit=0 wall=7.9s
- embodiment-3t: exit=0 wall=2.3s
- cam-reason-3t: exit=0 wall=10.8s

## Fixes applied this cycle
- CI: install pydantic before joshinator embodiment unit tests
- 3T campaign auto-installs `integrations/joshinator-analyzer/backend/requirements-ci.txt` before embodiment fuzz
- connectome-simulate v4-exhaustive-scaled for N≥1e11
- Companion fuzzers: modular_period_scaled via trillion_scale.py
- Codified Aaron test protocol (this entrypoint + CONTINUOUS_QA)
- Google Trends: `scripts/google-trends-check.py` + curated add-ons (`trends.search_*`)
- Higgsfield: `scripts/higgsfield-check.py` + dry-run `higgsfield-run.py` + mesh pack
- Higgsfield OCL: `no_higgsfield_without_aaron` / jobs / outbound burst policies
- Cloud Agent install: `scripts/test_cloud_agent_install.py` + `.cursor/environment.json`
- 3T campaign + CI run cloud-agent-install and cam-system unit gates
- Higgsfield dry-run / doctor: empty submodule is a warning, not a campaign-fail
- Embodiment 3T: pydantic-free `embodiment_lite` catalog path when pypi is blocked

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
- `git submodule update --init integrations/higgsfield` before any live train intent
- Allowlist `pypi.org` / `files.pythonhosted.org` if you want full embodiment resolve in Cloud Agent
- Mirror cycles into `identity/persistence/qa-mesh-latest.json`
- Cloud Agent: install must be a real command (`./scripts/cloud-agent-install.sh`); never `build` / `promote`
- Do not add `npm ci` to Cloud Agent install until `registry.npmjs.org` is allowlisted
- After merge, start a new Cloud Agent so `.cursor/environment.json` overrides the dashboard
- Dashboard Save is on the agent Environment panel; if Save is missing, merge this PR so repo JSON wins
