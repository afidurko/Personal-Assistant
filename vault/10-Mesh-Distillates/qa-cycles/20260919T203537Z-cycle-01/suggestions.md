# QA cycle suggestions

- status: green
- sims: 1000000000
- passed/failed: 1000000000/0
- throughput: 1270794.5949662232 sims/s
- missing_edges: 0

## Findings
- none

## After green (standing improvements)
- CI: `bash scripts/ci-connectome.sh` (check + workspace unit tests + 1M strict)
- Standing: `python3 scripts/system-health-scan.py` (health_conductor)
- Nightly billion fuzz via `qa-loop.py --n 1000000000 --cycles 1`
- Trajectory OCL/CPV billion: `python3 scripts/trajectory-billion-fuzz.py --n 1000000000`
- Cam reason billion: `python3 scripts/cam-reason-billion-fuzz.py --n 1000000000`
- Progress heartbeats every 50M sims for long campaigns (simulator v3)
- Traffic-weighted sense sampling (chat/vault/cline/scholar/arxiv-heavy)
- Mirror QA cycle events into `identity/persistence/qa-mesh-latest.json`
- Cline workspace runtime: `python3 scripts/test_cline_workspaces.py`
- Cam reason dry-run: `python3 scripts/test_cam_reason.py`
- When Mac is available: flip Tailscale preferred host to aaron-mac
- Suggest: bind `run-cline.py` tickets into live nulltickets when stack is up
- Suggest: `cline mcp install cam` on each Aaron machine after persist-import
- Suggest: pack research mesh writes with `scripts/pack-mesh-claim.py` (MMP)
- Suggest: keep HMO primary lean — persona/prefs only; archive vault distillates
- Suggest: before merge run `trajectory-policy-check` + dual billion + cam-reason billion
- Suggest: Phase C converse bar-only — never every-mic SGR
- Suggest: LitServe thin proxy after dry-run green; no vLLM farm yet
- Suggest: expand Cam toolkit (Cline/Scholar) only after Phase B merge
