# Google Scholar integration — academic research periphery

Google Scholar is Cam’s **citation / paper search** connector for the Information
and Research pathways (and AGI scan when a query is AI/AGI-relevant).

Google Scholar has **no official public API**. Cam uses **SerpAPI**
(`engine=google_scholar`) as the supported bridge.

## Role in the team

| Concern | Owner |
|---|---|
| Query planning / cite-check | `info-retriever` / `researcher` |
| AI/AGI paper watch | `agi-scout` (optional Scholar pass) |
| Task queue / mesh truth | nulltickets (`mesh/research`) |
| Credential | local `.env` → `SERPAPI_API_KEY` |

Vault-first still applies: search smart-second-brain before Scholar for Aaron’s
personal facts. Scholar is for **open literature**.

## Connectome

```text
sense.web.scholar → center.info → center.research → center.qa
                 → switch.research_scan → motor.web_fetch
                 (+ motor.vault, motor.mesh)
```

Config: [`google-scholar.json`](google-scholar.json)  
Hotspot: `hotspot.google_scholar`

## Enable (on your machine)

1. Create a [SerpAPI](https://serpapi.com/) key (free tier is enough to start).
2. Put it in local secrets only:

```bash
# repo root .env (gitignored)
SERPAPI_API_KEY=your_key_here
```

3. Optional — Aaron’s Scholar profile (citation watch):

Edit `config/integrations/google-scholar.json` → `profile.author_id`
(from `https://scholar.google.com/citations?user=AUTHOR_ID`).

## CLI

```bash
# Offline / fixture (no network, no key)
python3 scripts/scholar-search.py --query "connectome mapping" --offline

# Live SerpAPI search
python3 scripts/scholar-search.py --query "connectome mapping" --num 8

# Author profile (requires profile.author_id or --author-id)
python3 scripts/scholar-search.py --author-id USER_ID --offline

# Pack a results JSON into a mesh/research document
python3 scripts/pack-scholar-result.py --results path/to/results.json
```

Outputs land under `vault/04-Research/scholar/` when `--save-vault` is used
(search script default when writing files).

## Mesh / vault

- Distillates → `mesh/research` (via pack script / curator PUT)
- Notes → `vault/04-Research/scholar/`
- Every claim still needs title + URL + date accessed

## Boundaries

- Read-only literature access — no outbound email to authors
- Do not scrape Scholar HTML directly (ToS + fragility); use SerpAPI
- Never commit `SERPAPI_API_KEY`
- Kill switch / `switch.research_scan` hold pauses fetches
