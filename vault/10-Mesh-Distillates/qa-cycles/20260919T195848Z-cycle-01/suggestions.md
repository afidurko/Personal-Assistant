# QA cycle suggestions

- status: green
- sims: 1000000000
- passed/failed: 1000000000/0
- throughput: 2045277.6422160633 sims/s
- missing_edges: 0

## Findings
- none

## After green (standing improvements)
- CI: `bash scripts/ci-connectome.sh` (check + workspace unit tests + 1M strict)
- Standing: `python3 scripts/system-health-scan.py` (health_conductor)
- Nightly billion fuzz via `qa-loop.py --n 1000000000 --cycles 1`
- Trajectory OCL/CPV billion: `python3 scripts/trajectory-billion-fuzz.py --n 1000000000`
- Progress heartbeats every 50M sims for long campaigns (simulator v3)
- Traffic-weighted sense sampling (chat/vault/cline/scholar/arxiv/public-apis-heavy)
- Mirror QA cycle events into `identity/persistence/qa-mesh-latest.json`
- Cline workspace runtime: `python3 scripts/test_cline_workspaces.py`
- Public APIs catalog: `python3 scripts/public-apis-check.py` + `test_public_apis.py`
- Joshinator embodiment: `unittest backend.test_embodiment` + `embodiment-billion-fuzz.py`
- When Mac is available: flip Tailscale preferred host to aaron-mac
- Suggest: bind `run-cline.py` tickets into live nulltickets when stack is up
- Suggest: `cline mcp install cam` on each Aaron machine after persist-import
- Suggest: pack research mesh writes with `scripts/pack-mesh-claim.py` (MMP)
- Suggest: keep HMO primary lean — persona/prefs only; archive vault distillates
- Suggest: before inventing HTTP helpers, run `scripts/public-apis-search.py`
- Suggest: before merge run `trajectory-policy-check` + dual billion campaigns
- Suggest: keep card 3D spawns procedural — never load franchise GLTF/character packs
- Suggest: push joshinator embodiment upstream when Cursor has write access
