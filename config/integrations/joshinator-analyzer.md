# Joshinator Analyzer integration — sports card OCR + IP-safe 3D embodiment

Source: [afidurko/joshinator-analyzer](https://github.com/afidurko/joshinator-analyzer)  
Path: [`integrations/joshinator-analyzer`](../../integrations/joshinator-analyzer) (vendored checkout; push upstream when write access is available)

## Role

Joshinator is Cam’s **card-analyze → embody** effector for live auction streams:

1. Detect / OCR card identity from a screen region  
2. Price + ROI signal  
3. Resolve an **original procedural 3D champion** (no franchise character IP)  
4. Render in the React `EmbodimentViewer`

## IP policy

Hard rules live in `integrations/joshinator-analyzer/docs/EMBODIMENT.md`:

- Procedural primitives only (capsule / cone / sphere / fins / rings)
- Original archetype names (`Diamond Arc`, `Court Pulse`, …)
- No Pokémon / Nintendo / team-logo / manufacturer trade-dress meshes
- Athlete `player_name` is factual OCR text only

## Run locally

```bash
# Backend
cd integrations/joshinator-analyzer
PYTHONPATH=backend uvicorn app.main:socket_app --app-dir backend --host 0.0.0.0 --port 3001

# Frontend
cd integrations/joshinator-analyzer/frontend
npm install && npm start
```

Tests:

```bash
PYTHONPATH=backend python3 -m unittest backend.test_embodiment -v
cd frontend && CI=true npm test -- --watchAll=false
```

## Mesh / Cam wiring (target)

- Vision-adjacent distillates → optional `mesh/vision` card identity summary  
- Embodiment spawn events → `mesh/projects` or session log only (no raw frames)  
- Do not start screen capture unless Aaron tasks it (`switch.ios_capture` / local region select)

## Upstream sync

Branch prepared against the analyzer repo: `cursor/card-embodiment-3d-b576`  
Personal-Assistant mirrors the same tree here until Cursor can push to `afidurko/joshinator-analyzer`.
