# MemoryBear integration — cognitive memory for every agent & workspace

Source: [afidurko/MemoryBear](https://github.com/afidurko/MemoryBear)  
Path: [`integrations/memorybear`](../../integrations/memorybear) (git submodule)  
Upstream product: [memorybear.ai](https://www.memorybear.ai/)

## Role in the team

MemoryBear is Cam’s **cognitive memory engine** — perceive → extract → associate →
forget — inspired by hippocampal encoding, neocortical consolidation, and synaptic
pruning. It is **not** the brain and **not** a replacement for the vault or mesh.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw (Cam) |
| Task queue / mesh KV truth | nulltickets |
| Vault notes / Obsidian graph | smart-second-brain |
| Hierarchical memory tiers (HMO) | `config/memory/hmo-tiers.json` + memory-curator |
| Cognitive extract / graph / forget / reflect | **MemoryBear** |

**All Cam roles and subagents** may invoke `motor.memorybear` when work needs
durable conversational memory, preference extraction, or graph-backed recall —
not only `memory-curator`.

## Memory stack (layered)

```text
primary   → lean Aaron-facing context (persona / prefs / pivotal mesh)
secondary → hot mesh + MemoryBear cognitive store (on demand)
archive   → vault + persistence + distillates
```

- **Vault first** for Aaron’s personal notes (smart-second-brain).
- **Mesh first** for tickets, prefs, and cross-agent claims.
- **MemoryBear** for life-like extraction, hybrid search, forgetting, and reflection
  over conversational / multimodal engrams that should evolve over time.

## Connectome

```text
sense.memorybear.hit → center.memory → switch.autonomy → motor.memorybear
sense.chat.aaron     → center.chief  → center.memory → … → motor.memorybear
```

Config: [`memorybear.json`](memorybear.json)  
Hotspots: `hotspot.memorybear_recall`, `hotspot.memorybear_write`  
Area: `area.mtl` (MTL / hippocampus-adjacent)

## Runtime surface

| Piece | Path |
|---|---|
| Integration config | `config/integrations/memorybear.json` |
| Client CLI | `scripts/memorybear.py` |
| Mesh packer | `scripts/pack-memorybear-result.py` |
| Wiring check | `scripts/memorybear-check.py` |
| MCP (Cam) | `scripts/cam-mcp-server.py` → `memorybear_read` / `memorybear_write` |
| Mesh namespace | `mesh/memorybear` |
| Vault distillates | `vault/10-Mesh-Distillates/memorybear/` |

## Enable (on Aaron’s machine)

1. Init submodule (optional local checkout of upstream):

```bash
git submodule update --init integrations/memorybear
```

2. Run MemoryBear per its README (API default Docker port `8002`, or manual `8000`).

3. Put credentials in local secrets only:

```bash
# repo root .env (gitignored)
MEMORYBEAR_API_BASE=http://127.0.0.1:8002
MEMORYBEAR_API_KEY=your_api_key
MEMORYBEAR_END_USER_ID=aaron-cam-end-user
```

4. Smoke:

```bash
python3 scripts/memorybear.py --doctor --offline
python3 scripts/memorybear.py read --query "Aaron preferences" --offline
python3 scripts/memorybear-check.py
```

## CLI

```bash
# Offline / fixture (no network, no key)
python3 scripts/memorybear.py read --query "coffee preference" --offline
python3 scripts/memorybear.py write --message "Aaron prefers soft airy Cam voice" --offline

# Live Service API
python3 scripts/memorybear.py read --query "open projects" --search-switch normal
python3 scripts/memorybear.py write --message "Standing goal: daily AGI scan"

# Pack a result JSON into a mesh/memorybear document
python3 scripts/pack-memorybear-result.py --results path/to/result.json
```

## How every agent uses it

1. Aaron tasks Cam (or a standing goal fires).
2. `connectome-route.py` may select `hotspot.memorybear_recall` / `_write`.
3. Agents fire `motor.memorybear` via `scripts/memorybear.py` or Cam MCP tools.
4. Curator packs distillates into `mesh/memorybear` and optional vault notes.
5. Fornix / HMO promotion still apply — MemoryBear does not bypass mesh claim schema.

## Mesh bridge

| Namespace | Content |
|---|---|
| `mesh/memorybear` | read/write sessions, doctor status, distillates |
| `mesh/memory` / `mesh/facts` | curated claims (via pack + memory-curator) |
| `mesh/runs` | run summaries that used MemoryBear |

## Boundaries

- Only Aaron may assign the original task; Cam/MemoryBear finish under standing autonomy
- Kill switch / `switch.autonomy` hold pauses new writes
- Never commit `MEMORYBEAR_API_KEY` or end-user identifiers that are secrets
- Do not invent Aaron personal facts — prefer vault + mesh over MemoryBear invention
- Prefer Jarvis for trivial deterministic chores; prefer MemoryBear for cognitive recall/write
- Smart-second-brain remains the Obsidian vault cortex; MemoryBear is the graph/forget engine

## Cross-workspace checklist

1. `persist-import` (brings mesh-seed + integration config)
2. `git submodule update --init integrations/memorybear` (optional local API source)
3. Confirm `MEMORYBEAR_*` env on the host that runs Cam
4. `python3 scripts/memorybear.py --doctor --offline` then live doctor when ready
5. `python3 scripts/memorybear-check.py` and `python3 scripts/workspace-integration-check.py`
