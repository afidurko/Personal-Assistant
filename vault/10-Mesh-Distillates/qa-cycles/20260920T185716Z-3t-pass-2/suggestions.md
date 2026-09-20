# Three-trillion QA suggestions — pass 2

- status: green
- n: 3,000,000,000,000
- at: 20260920T185745Z

## Results
- ci-static-gate: exit=0 wall=0.3s
- workspace-unit-tests: exit=0 wall=0.5s
- cloud-agent-install: exit=0 wall=0.1s
- cam-system-unit: exit=0 wall=0.1s
- cam-reason-unit: exit=0 wall=0.2s
- converse-voice-unit: exit=0 wall=0.2s
- higgsfield-check: exit=0 wall=0.0s
- higgsfield-unit: exit=0 wall=0.3s
- embodiment-lite: exit=0 wall=0.2s
- presence-check: exit=0 wall=0.0s
- trajectory-policy-check: exit=0 wall=0.0s
- connectome-3t: exit=0 wall=4.2s
- illa-desktop-unit: exit=0 wall=0.1s
- illa-electron-check: exit=0 wall=0.0s
- public-apis-unit: exit=0 wall=0.3s
- public-apis-addons-unit: exit=0 wall=0.4s
- public-apis-check: exit=0 wall=0.1s
- trajectory-3t: exit=0 wall=0.7s
- embodiment-deps: exit=0 wall=0.0s
- embodiment-3t: exit=0 wall=2.6s
- cam-reason-3t: exit=0 wall=10.3s
- illa-desktop-3t: exit=0 wall=2.7s
- aaron-voice-3t: exit=0 wall=1.0s
- public-apis-3t: exit=0 wall=4.3s

## Fixes applied this cycle
- Converse `/api/turn` is one `cam_reason.reason()` + `speak_from_trace` (camera/pupil/voice overlays)
- In-process `connectome-route.route()` + `cam_inproc` (no python3 spawn per check/route)
- `ci-static-gate.py` one-process static CI; 1M fuzz stays isolated
- 3T campaign now runs `ci-static-gate` + converse/reason units + Aaron-voice 3T
- `aaron-voice-billion-fuzz.py` honors `--physical` / modular_period_scaled (N≥1e11)
- cam-reason 3T workers assert in-process coding route + converse greeting/see-me overlay
- workspace-integration-check is inside the static gate (was campaign-only)
- Public-apis 3T + expanded allowlisted add-ons (frankfurter / advice slip) from #42
- CI: install pydantic before joshinator embodiment unit tests
- Embodiment 3T: pydantic-free `embodiment_lite` catalog path when pypi is blocked
- 3T campaign auto-installs `integrations/joshinator-analyzer/backend/requirements-ci.txt` before embodiment fuzz
- connectome-simulate v4-exhaustive-scaled for N≥1e11
- Companion fuzzers: modular_period_scaled via trillion_scale.py
- Codified Aaron test protocol (this entrypoint + CONTINUOUS_QA)
- Google Trends: `scripts/google-trends-check.py` + curated add-ons (`trends.search_*`)
- Presence: Higgsfield Speak clips rejected — portrait + A2F only (`scripts/presence-check.py`)
- Trajectory: `higgsfield_rejected_for_cam_face` strips Speak clips from speak plans
- Higgsfield IDs are GPU train (`switch.cam_enhance`); Speak never owns `motor.higgsfield`

## Suggested add-ons
- `config/persona/converse-overlays.json` — move camera/pupil/voice lines out of the server so new presence phrases do not fork `speak_from_trace`
- `scripts/converse-billion-fuzz.py` — modular overlay/intent matrix at 3T (companion to cam-reason fuzz)
- `public-apis` add-on: offline fixture for `sense.catalog.public_apis` smoke without subprocess search
- `google-trends` add-on: same in-process search helper as `cam_inproc.route`
- Voice add-on: FunASR enroll checksum in aaron-voice 3T (hash_dev already covers contract)
- Activity add-on: quiet `write_live_activity()` already exists; emit converse refresh only on last row (done) — add a mesh-params dual_stream cache invalidation hook

## Standing suggestions
- Keep `python3 scripts/ci-static-gate.py` as the fast static gate; `bash scripts/ci-connectome.sh` still owns 1M fuzz
- Dual three-trillion: `python3 scripts/three-trillion-campaign.py --passes 2`
- Merge prep: `bash scripts/merge-prep-trillion.sh`
- Raise `--physical 1000000000` when you want a full 1B physical stress under 3T
- Aaron voice 3T: `python3 scripts/aaron-voice-billion-fuzz.py --n 3000000000000`
- Converse units: `AARON_VOICE_TEST=1 AARON_VOICE_ALLOW_DEV_BACKEND=1 python3 scripts/test_cam_converse_voice_gate.py`
- Slim CI deps: `integrations/joshinator-analyzer/backend/requirements-ci.txt`
- After registry edits: `python3 scripts/test_cline_workspaces.py`
- Trends add-ons: `python3 scripts/google-trends-addon.py list`
- Higgsfield: `python3 scripts/higgsfield-run.py --doctor` then pack to `mesh/runs`
- Higgsfield train jobs stay enhance-gated; never free-spend GPU from Cline
- `git submodule update --init integrations/higgsfield` before any live train intent
- Allowlist `pypi.org` / `files.pythonhosted.org` if you want full embodiment resolve in Cloud Agent
- Presence add-on: `python3 scripts/presence-check.py` (no Speak overlay on Cam’s face)
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
