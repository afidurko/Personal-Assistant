# Google Trends add-on suggestions (PR #24)

## Implemented (this cycle)

1. **`trends.search_election`** — curated election/primary catalog search  
2. **`trends.search_nba`** — NBA finals/draft/player CSVs  
3. **`trends.search_storm`** — storm / weather-event CSVs  
4. **`trends.dataset_game_theory`** — tiny CSV preview smoke path  
5. **`trends.dataset_same_sex_marriage`** — curated well-known graphic dataset preview  

CLI: `python3 scripts/google-trends-addon.py call <id> --offline`  
MCP: `google_trends_addon`

## Standing next add-ons (not in this PR unless requested)

- `trends.search_olympics` / `trends.search_worldcup` — sports mega-events  
- `trends.search_immigration` — migration interest series  
- `trends.year_pack_2016` — year-scoped browse (US election year)  
- MemoryBear bridge: distill Trends hits into `motor.memorybear` associate notes  

## Guardrails

- Allowlist only — no free-form `--path` / `--url` on the addon CLI  
- Offline fixtures required for CI  
- Full-repo clone still forbidden (~382MB upstream)
