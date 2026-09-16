# Continuous QA loop (persistent · always on)

**Authorized by:** Aaron · **Date:** 2026-09-16 · **Status:** always active

## Mandate

Cam must **always** watch for issues in the connectome / assistant stack. When anything fails or looks wrong:

1. **Detect** — record failure signature in mesh + vault  
2. **Dispatch a team** — spawn as many subagents as needed (no human gate)  
3. **Diagnose** — root cause + fix plan  
4. **Fix** — rewrite/simplify code  
5. **Rerun** — full simulation campaign (default **1,000,000,000** live-action sims)  
6. **Repeat** — loop until green, then keep watching  

## Standing orders

- Unlimited subagents allowed for diagnosis and repair  
- Aaron still assigns root goals / owns kill switch  
- Do not wait for Aaron mid-loop once a campaign is tasked  
- Log every cycle under `vault/10-Mesh-Distillates/qa-cycles/`  
- Prefer simplify-over-complicate when rewriting  

## Default campaign size

`N = 1_000_000_000` (one billion) sense→center→switch→motor→feedback simulations.

## Automation entrypoint

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
  "qa_default_n": 1000000000
}
```
