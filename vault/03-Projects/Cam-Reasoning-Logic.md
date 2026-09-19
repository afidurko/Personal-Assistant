# Cam Reasoning Logic

Plan: **SGR** (System-2) + **LitServe** (deferred) + dual-process / MAP / HMO / QA.

- **Repo plan:** `docs/CAM_REASONING.md`
- **Phase B (done):** `scripts/cam-reason.py` dry-run + `scripts/test_cam_reason.py`
- **SGR / LitServe submodules:** present; live LLM / LitServe host still deferred

## Run

```bash
python3 scripts/cam-reason.py --goal "hi cam" --no-write
python3 scripts/cam-reason.py --goal "enhance Cam functionality please" --no-write
python3 scripts/test_cam_reason.py
```

## Next (Phase C)

Converse bar-only wire + thin LitServe proxy — not every mic turn.
