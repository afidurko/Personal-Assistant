# Persistent grant — daily AGI research scan + Cam enhancement proposals

**Authorized by:** Aaron  
**Date:** 2026-09-17  
**Status:** active · stored in mesh + identity

## Rule

Cam’s **AGI Research Scan Team** may **every day** (and on demand) scan the open internet for new AI/AGI papers and findings that can enhance Cam, distill them into vault/mesh, and draft enhancement proposals — **without asking Aaron each day**.

Aaron retains **ultimate say** over applying functionality changes (`switch.cam_enhance`).

## Details

- Standing trigger: `sense.clock.daily` (America/New_York)
- Sources: arXiv + open research feeds (see `config/teams/agi-research-scan.json`)
- Teams may spawn unlimited subagents (no human gate)
- Propose autonomously; apply only with Aaron approval
- Kill switch still pauses all motor

## Machine form

```json
{
  "daily_agi_research_scan": true,
  "agi_scan_requires_human_each_day": false,
  "cam_enhance_apply_requires_aaron": true,
  "switch_research_scan_default": "standing_on",
  "switch_cam_enhance_default": "hold"
}
```

See `docs/AGI_RESEARCH_TEAM.md` and `identity/persistence/mesh-seed.json`.
