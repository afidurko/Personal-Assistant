# Higgsfield — Cam function + improvements (2026-09-20)

## Function for Cam

Higgsfield is Cam’s **Aaron-gated multi-node GPU training effector** — not the brain.

| Layer | ID |
|---|---|
| Submodule | `integrations/higgsfield` |
| Motor | `motor.higgsfield` |
| Sense | `sense.train.higgsfield` |
| Hotspot | `hotspot.higgsfield` |
| Gate | `switch.cam_enhance` + `switch.kill` |
| Check / run / pack | `scripts/higgsfield-{check,run}.py` · `pack-higgsfield-result.py` |

```text
Train / fine-tune large weights  → Higgsfield (multi-node, spend risk)
Serve / classify / embed locally → LitServe (motor.slm / motor.dl)
```

## Improvements landed

1. **Dry-run runner** — `higgsfield-run.py` AST-validates `@experiment`, inventory, nodes; default `mode=dry_run`; never SSH  
2. **Live arming** — `--live` only with `--enhance` + `CAM_HIGGSFIELD_LIVE=1` (intent only; no remote exec yet)  
3. **Mesh distill** — `pack-higgsfield-result.py` → `mesh/runs` (`higgsfield_train_plan`)  
4. **LitServe handoff stub** — plan includes `litserve_handoff` (no auto-load)  
5. **Trajectory / cost envelope** — `no_higgsfield_without_aaron`, `…_with_jobs_burst`, `…_with_outbound_burst`  
6. **Tools + CI + unit tests** — `tool.higgsfield.*`, `test_higgsfield.py`, ci-connectome wiring  

## Verify

```bash
python3 scripts/higgsfield-check.py
python3 scripts/test_higgsfield.py
python3 scripts/trajectory-policy-check.py
python3 scripts/higgsfield-run.py --doctor | tee /tmp/hf.json
python3 scripts/pack-higgsfield-result.py --results /tmp/hf.json --goal smoke
```

## Still deferred

- Real SSH / DeepSpeed launch on cloud nodes  
- Automatic adapter load into LitServe  
- Full flight-envelope GPU budget meter  
