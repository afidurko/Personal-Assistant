# Continuous QA loop (persistent · always on)

**Authorized by:** Aaron · **Date:** 2026-09-16 · **Status:** always active  
**Test protocol updated:** 2026-09-19 — Aaron base function **test**

## Mandate

Cam must **always** watch for issues in the connectome / assistant stack. When anything fails or looks wrong:

1. **Detect** — record failure signature in mesh + vault  
2. **Dispatch a team** — spawn as many subagents as needed (no human gate)  
3. **Diagnose** — root cause + fix plan  
4. **Fix** — rewrite/simplify code  
5. **Rerun** — full simulation campaign  
6. **Repeat** — loop until green, then keep watching  

## Aaron base function: **test**

When Aaron says **test** (workspace QA redesign / simplify / function test):

1. Run **three trillion** checks (`N = 3_000_000_000_000`)  
2. Fix errors (prefer simplify-over-complicate)  
3. Add suggestions under `vault/10-Mesh-Distillates/qa-cycles/`  
4. Run **three trillion** again  
5. If fully successful → merge (see `MERGE_READINESS_THREE_TRILLION.md`)

Entrypoint:

```bash
python3 scripts/three-trillion-campaign.py --passes 2
# or
bash scripts/merge-prep-trillion.sh
```

Harnesses use exhaustive/modular scale for finite pathway spaces plus a
physical stress subset (default 10M; raise with `--physical`).

## Standing orders

- Unlimited subagents allowed for diagnosis and repair  
- Aaron still assigns root goals / owns kill switch  
- Do not wait for Aaron mid-loop once a campaign is tasked  
- Log every cycle under `vault/10-Mesh-Distillates/qa-cycles/`  
- Prefer simplify-over-complicate when rewriting  

## Default campaign sizes

| Mode | N | Entrypoint |
|---|---|---|
| Nightly / CI smoke | `1_000_000`–`1_000_000_000` | `qa-loop.py`, `ci-connectome.sh` |
| Aaron **test** | `3_000_000_000_000` | `three-trillion-campaign.py` |

## Automation entrypoint (billion loop still valid)

```bash
python3 scripts/qa-loop.py --n 1000000000 --cycles 2
```

## Machine prefs

```json
{
  "continuous_qa": true,
  "qa_on_failure_dispatch_team": true,
  "qa_auto_fix": true,
  "qa_auto_rerun": true,
  "qa_default_n": 1000000000,
  "qa_test_protocol_n": 3000000000000,
  "qa_test_protocol": "3t_fix_suggest_3t_merge"
}
```
