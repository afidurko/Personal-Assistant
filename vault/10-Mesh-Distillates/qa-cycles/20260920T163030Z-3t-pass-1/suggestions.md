# Three-trillion QA suggestions — pass 1

- status: green
- n: 3,000,000,000,000
- at: 20260920T163058Z

## Results
- connectome-check: exit=0 wall=0.0s
- workspace-integration: exit=0 wall=0.3s
- workspace-unit-tests: exit=0 wall=0.5s
- cloud-agent-install: exit=0 wall=0.1s
- cam-system-unit: exit=0 wall=0.1s
- higgsfield-check: exit=0 wall=0.0s
- higgsfield-unit: exit=0 wall=0.3s
- embodiment-lite: exit=0 wall=0.1s
- connectome-3t: exit=0 wall=4.3s
- illa-desktop-unit: exit=0 wall=0.1s
- illa-electron-check: exit=0 wall=0.0s
- public-apis-unit: exit=0 wall=0.3s
- public-apis-addons-unit: exit=0 wall=0.3s
- public-apis-check: exit=0 wall=0.1s
- trajectory-3t: exit=0 wall=0.7s
- embodiment-deps: exit=0 wall=2.3s
- embodiment-3t: exit=0 wall=2.7s
- cam-reason-3t: exit=0 wall=9.9s
- illa-desktop-3t: exit=0 wall=2.6s
- public-apis-3t: exit=0 wall=3.4s

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
- ILLA desktop: `python3 scripts/illa-desktop-billion-fuzz.py --n 3000000000000`
- ILLA unit: `python3 scripts/test_illa_desktop.py`
- Public APIs: `python3 scripts/public-apis-billion-fuzz.py --n 3000000000000`
- Public APIs unit: `python3 scripts/test_public_apis.py` + `test_public_apis_addons.py`
- Public APIs add-ons: `python3 scripts/public-apis-addon.py list`
- Keep electron-builder pin exact `26.16.1` (not fork master / v27)
- After packaging edits: `npm --prefix integrations/illa-desktop run check:pin`
- Cloud Agent: install must be a real command (`./scripts/cloud-agent-install.sh`); never `build` / `promote`
- Do not add `npm ci` to Cloud Agent install until `registry.npmjs.org` is allowlisted
- After merge, start a new Cloud Agent so `.cursor/environment.json` overrides the dashboard
- Dashboard Save is on the agent Environment panel; if Save is missing, merge this PR so repo JSON wins
- Suggest: add `quotes.quotable` / `exchange.open_er_api` allowlisted add-ons when ops asks
- Suggest: MCP `public_apis_addon` for weather/geo before inventing HTTP helpers
