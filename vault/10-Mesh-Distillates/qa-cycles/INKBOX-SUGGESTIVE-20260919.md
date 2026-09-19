# Suggestive implementations — Inkbox dual-billion QA

**Authorized:** Aaron · **Date:** 2026-09-19  
**PR:** Integrate Inkbox into Cam (#21)

## Coverage gaps found before 1B (fixed this cycle)

1. **Trajectory MOTORS** — `motor.inkbox` (and `motor.public_apis`) were missing from
   `trajectory-billion-fuzz.py` random samples, so outbound-hold could not leak-detect Inkbox.
2. **Outbound hold apply** — full `apply_policies` samples now include `motor.inkbox` and
   assert strip on `switch.outbound=hold` / kill clears Inkbox with other outbound motors.
3. **Policy check** — `trajectory-policy-check.py` verifies Inkbox is stripped with text on hold.
4. **Traffic weight** — `sense.inkbox.event` = 2.0 in `connectome-simulate.py`.
5. **QA suggestions** — `qa-loop.py` documents `inkbox-check` + no free-send from Cline.

## Standing (not blockers)

- Live `INKBOX_API_KEY` stays local — never commit.
- Empty sibling submodules on cloud checkouts remain soft warnings.
- Cursor Marketplace Inkbox plugin is pre-release upstream.

## Verify commands

```bash
python3 scripts/inkbox-check.py
python3 scripts/trajectory-policy-check.py
python3 scripts/qa-loop.py --n 1000000000 --cycles 1
python3 scripts/trajectory-billion-fuzz.py --n 1000000000
```

## Dual billion results

| Pass | Connectome 1B | Trajectory 1B |
|---|---|---|
| 1 (`20260919T194605Z`) | 1e9 passed / 0 failed | PASS |
| 2 verify (`20260919T195455Z`) | 1e9 passed / 0 failed | PASS |

| post-merge (`20260919T200709Z`) | 1e9 passed / 0 failed | PASS |
