# Public APIs integration — free API catalog for every agent & workspace

Source: [afidurko/public-apis](https://github.com/afidurko/public-apis)  
Path: [`integrations/public-apis`](../../integrations/public-apis) (git submodule)  
Upstream: community-curated free/public API index (APILayer-sponsored list)

## Role in the team

Public APIs is Cam’s **shared API discovery catalog** — category-indexed free and
public HTTP APIs agents can recommend or thin-wrap. It is **not** the brain and
**not** a credential store.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw (Cam) |
| Task queue / mesh truth | nulltickets |
| Tool registration / thin wrappers | `team.tooling` |
| Literature / citations | Google Scholar |
| Free API lookup by topic | **public-apis** (`motor.public_apis`) |

**All Cam roles and subagents** may invoke `motor.public_apis` when work needs
an external free API (weather, geocode, stocks, animals, ML demos, etc.) —
not only `tool-user` or `info-retriever`.

## Connectome

```text
sense.catalog.public_apis → center.tooling → center.info → switch.autonomy
                         → motor.public_apis (+ motor.mesh, motor.tool)
```

Config: [`public-apis.json`](public-apis.json)  
Hotspot: `hotspot.public_apis`

## Runtime surface

| Piece | Path |
|---|---|
| Integration config | `config/integrations/public-apis.json` |
| Search CLI | `scripts/public-apis-search.py` |
| Mesh packer | `scripts/pack-public-apis-result.py` |
| Thin-wrapper add-ons | `scripts/public-apis-addon.py` · `config/integrations/public-apis-addons.json` |
| Wiring check | `scripts/public-apis-check.py` |
| MCP (Cam) | `scripts/cam-mcp-server.py` → `public_apis_search` / `public_apis_addon` |
| Mesh namespace | `mesh/tools` (catalog hits + addon results) + optional vault notes |
| Vault distillates | `vault/04-Research/public-apis/` |

## Enable

```bash
git submodule update --init integrations/public-apis
python3 scripts/public-apis-search.py --query weather --offline
python3 scripts/public-apis-check.py
```

No API key is required to **search the catalog**. Individual listed APIs may
require their own keys — store those in local `.env` only, never commit.

## CLI

```bash
# Search local submodule README (or bundled fixture with --offline)
python3 scripts/public-apis-search.py --query "weather" --num 8
python3 scripts/public-apis-search.py --category Animals --auth No --https
python3 scripts/public-apis-search.py --list-categories

# Pack results into a mesh/tools document
python3 scripts/pack-public-apis-result.py --results path/to/results.json

# Thin-wrapper add-ons (allowlisted only — no free-form URLs)
python3 scripts/public-apis-addon.py --list
python3 scripts/public-apis-addon.py call weather.open_meteo --latitude 40.7 --longitude -74.0 --offline
python3 scripts/public-apis-addon.py call geo.open_meteo --name "New York"
```

## Thin-wrapper add-ons

First-wave allowlist lives in [`public-apis-addons.json`](public-apis-addons.json):

| Id | Purpose |
|---|---|
| `weather.open_meteo` | Forecast by lat/lon |
| `geo.open_meteo` | Place name → coordinates |
| `ip.ipify` | Public IP |
| `facts.catfact` | Smoke / presence demo |
| `dogs.ceo` | Random dog image URL |
| `crypto.coingecko_simple` | Simple crypto USD prices |

Rules: only allowlisted endpoints; prefer Auth=No HTTPS; kill switch pauses live calls; fixtures for CI/`--offline`.

## How every agent uses it

1. Aaron tasks Cam (or a standing goal needs an external data source).
2. `connectome-route.py` may select `hotspot.public_apis`.
3. Agents run `scripts/public-apis-search.py` or Cam MCP tools.
4. When reuse is likely, call an allowlisted add-on via `scripts/public-apis-addon.py`
   (or MCP `public_apis_addon`) — never invent free-form fetch URLs.
5. Tooling may register additional allowlisted wrappers under
   `config/integrations/public-apis-addons.json` after Aaron-aligned standing goals.
6. Cite the catalog entry URL + date accessed; do not invent endpoints.

## Mesh bridge

| Namespace | Content |
|---|---|
| `mesh/tools` | catalog search distillates + registered wrappers |
| `mesh/runs` | runs that used public-apis discovery |
| `mesh/research` | research briefs that cite a public API source |

## Boundaries

- Catalog search is read-only discovery — not a license to spend money or scrape ToS-blocked sites
- Kill switch / `switch.autonomy` hold pauses new motor fires
- Never commit third-party API keys discovered via listed services
- Prefer Jarvis for trivial local chores; prefer public-apis when an HTTP free API is the right tool
- Prefer Scholar for academic papers; prefer public-apis for service endpoints

## Cross-workspace checklist

1. `persist-import` (brings mesh-seed + integration config)
2. `git submodule update --init integrations/public-apis`
3. `python3 scripts/public-apis-search.py --doctor`
4. `python3 scripts/public-apis-check.py` and `python3 scripts/workspace-integration-check.py`
