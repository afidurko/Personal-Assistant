# Cam Reasoning Logic

Plan + **Phase B dry-run** + dual billion QA — merged.

- Plan: `docs/CAM_REASONING.md`
- CLI: `python3 scripts/cam-reason.py --goal "…" --no-write`
- Tests: `python3 scripts/test_cam_reason.py`
- Billion: `python3 scripts/cam-reason-billion-fuzz.py --n 1000000000`

## Phase C — InfiniteMind (slow) + Fast path (speed)

| Gate | Surface |
|---|---|
| Slow | `cam-infinitemind` / stage `logic` before SGR |
| Fast | `cam-fast` — classify once, skip connectome scan + recall/logic/SGR |

```bash
python3 scripts/test_cam_fast.py
python3 scripts/cam-fast.py --bench 5000
python3 scripts/cam-reason.py --goal "hi cam" --no-write
```

Next: LitServe sLM classify on fast path (`switch.slm_local`); converse bar-only.

