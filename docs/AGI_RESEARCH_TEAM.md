# AGI Research Scan Team

Aaron authorized (2026-09-17) a standing team that **every day** scans the open internet for new AI/AGI research papers and findings that could enhance Cam. Aaron keeps **ultimate say** over applying functionality changes.

## Why this is allowed

- Scanning + citing + proposing = standing autonomy
- Changing Cam’s behavior/config = `switch.cam_enhance` (Aaron)
- Kill switch still silences all motor

## Roster

| Role | Job |
|---|---|
| `agi-scout` | Lead; crawl arXiv + feeds; spawn gatherers |
| `agi-analyst` | Score Cam-relevance; extract methods |
| `agi-synthesist` | Map to connectome / roles / sLM-DL proposals |
| `capability-broker` | Tickets; gated apply |
| `qa` | Cite-check |
| `memory-curator` | Archive mesh + vault |

All members may spawn unlimited subagents.

## Sources

arXiv (cs.AI/LG/CL/MA/NE, stat.ML), OpenReview, ACL Anthology, Hugging Face Papers, major lab blogs,
and **Google Scholar** (`sense.web.scholar` · `config/integrations/google-scholar.md`) for citation-aware literature.

## Connectome pathway

```text
sense.clock.daily → center.agi_scan → center.enhance → center.qa
                 → switch.research_scan → motor.web_fetch
                 (+ motor.vault, motor.mesh, motor.dl)
```

Paper spikes: `sense.web.arxiv`, `sense.web.agi_feed`

## Run

```bash
python3 scripts/agi-research-scan.py
python3 scripts/connectome-route.py --sense sense.clock.daily --goal "daily agi scan"
python3 scripts/connectome-check.py
```

Outputs:

- `vault/04-Research/agi-daily/<day>/`
- `vault/02-Cam/enhancement-proposals/`
- `vault/10-Mesh-Distillates/agi-scan/`
- Index: `vault/04-Research/AGI-Daily-Scan.md`

## Apply an enhancement

```bash
python3 scripts/cam-enhance-propose.py --proposal vault/02-Cam/enhancement-proposals/<file>.md
# Aaron approves:
python3 scripts/cam-enhance-propose.py --proposal ... --aaron-approve
```

Pipeline: `config/pipelines/cam-enhance-gate.json`
