# Google Trends data — open dataset catalog

Source: [GoogleTrends/data](https://github.com/GoogleTrends/data)  
Open CSV/XLSX (and related) datasets behind Google Trends graphics and interactives.

Aggregated · anonymised · indexed · normalized search-interest series — free to explore.
Contact listed upstream: `newslabtrends@google.com`.

## Why not a submodule?

The upstream tree is hundreds of MB. Cam indexes it remotely (GitHub git trees API)
and fetches **individual** files on demand. Offline/CI uses a bundled fixture subset.

## Role in the team

| Concern | Owner |
|---|---|
| Topic / event dataset lookup | `info-retriever` / `researcher` |
| Trend context for AGI / capability briefs | `agi-scout` / `capability-broker` |
| Mesh / vault distillates | nulltickets (`mesh/research`) |

Vault-first still applies for Aaron’s personal facts. This catalog is for **public
Trends source data**, not live Trends queries (no unofficial scrape).

## Connectome

```text
sense.catalog.google_trends → center.info → center.research → switch.autonomy
                           → motor.google_trends (+ motor.mesh, motor.vault)
```

Config: [`google-trends.json`](google-trends.json)  
Hotspot: `hotspot.google_trends`

## CLI

```bash
# Offline fixture (no network)
python3 scripts/google-trends-search.py --query election --offline

# Live index via GitHub API (cached under data/runtime/)
python3 scripts/google-trends-search.py --query "nba finals" --num 8

# List extensions / years in catalog
python3 scripts/google-trends-search.py --list-years --offline
python3 scripts/google-trends-search.py --list-ext --offline

# Fetch one dataset into vault (path from search results)
python3 scripts/google-trends-search.py --fetch 20150626_SameSexMarriage.csv --offline

# Pack search JSON into mesh/research
python3 scripts/pack-google-trends-result.py --results path/to/results.json

# Wiring check
python3 scripts/google-trends-check.py
```

## Mesh / vault

- Distillates → `mesh/research` (via pack script)
- Notes / fetched files → `vault/04-Research/google-trends/`
- Cite: dataset path + `https://github.com/GoogleTrends/data` + date accessed

## Boundaries

- Read-only public GitHub data — no spend, no SerpAPI key
- Do not clone the whole repo into Cam
- Do not scrape trends.google.com HTML; this connector is the **published open datasets** only
- Respect GitHub unauthenticated rate limits; prefer cache / `--offline` in CI
- Kill switch / `switch.autonomy` hold pauses live fetches
