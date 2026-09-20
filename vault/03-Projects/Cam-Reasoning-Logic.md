# Cam Reasoning Logic

Plan + **Phase B dry-run** + dual billion QA — merged.

- Plan: `docs/CAM_REASONING.md`
- CLI: `python3 scripts/cam-reason.py --goal "…" --no-write`
- Tests: `python3 scripts/test_cam_reason.py`
- Billion: `python3 scripts/cam-reason-billion-fuzz.py --n 1000000000`

## Phase C — InfiniteMind

Build on [Advanced-logic-reason-idea-and-learning-algorithms](https://github.com/afidurko/Advanced-logic-reason-idea-and-learning-algorithms):

- Project: `vault/03-Projects/Cam-InfiniteMind.md`
- Adapter: `python3 scripts/cam-infinitemind.py --goal "…"`
- Tests: `python3 scripts/test_cam_infinitemind.py`
- Slow-path stage `logic` before SGR stub

Next: LitServe thin proxy + converse bar-only; mesh KnowledgeBase; gated idea gen.
