# Persistence — Cam across workspaces

Aaron required: store Session/memory for **this workspace and all future workspaces**.

## What persists

| Artifact | Path | Purpose |
|---|---|---|
| Answers | `identity/ANSWERS_SESSION_01.json` | Capability grants |
| Profile | `identity/PROFILE.md` | Who Aaron & Cam are |
| Boundaries | `identity/BOUNDARIES.md` | Hard gates |
| Goals | `identity/GOALS.md` | Priorities |
| Mesh seed | `identity/persistence/mesh-seed.json` | Prefs/facts for nulltickets |
| Bundle manifest | `identity/persistence/manifest.json` | Versioned export metadata |
| Daily AGI grant | `identity/persistence/DAILY_AGI_SCAN.md` | Standing research-scan authority |
| Teams + sLM/DL | `config/teams/`, `config/enhancement/slm-dl.json` | Agent teams + local cortex |
| Workspace registry | `config/workspaces/registry.json` | Vault + scan + integration map |

## Guarantees

1. **Survives repo clones** — identity files are committed (no secrets in them).
2. **Portable bundle** — `scripts/persist-export.py` builds a zip/json bundle Cam can import into a new workspace (includes AGI teams + enhancement cortex).
3. **Import into future workspaces** — `scripts/persist-import.py` restores identity + mesh seed.
4. **Runtime mesh** — when nulltickets is up, curator `PUT`s seed into `mesh/prefs`, `mesh/facts`, `mesh/careers`, etc.
5. **Auto-archive** — after completed tasks, distill notes into mesh (Q60); export refreshes the portable bundle.
6. **Workspace integration check** — `scripts/workspace-integration-check.py` confirms wiring after import.

## What does *not* go in git

- API keys, OAuth tokens, phone numbers, raw resume PDFs with PII dumps
- Those live in a local secrets store / nullclaw encrypted secrets and are referenced, not committed

## Commands

```bash
# Export portable Cam memory (safe subset)
python3 scripts/persist-export.py --out /tmp/cam-persistence.zip

# Import into a new workspace checkout
python3 scripts/persist-import.py --from /tmp/cam-persistence.zip

# Refresh mesh-seed.json from current identity files
python3 scripts/persist-export.py --seed-only

# Confirm integrations + workflow wiring
python3 scripts/workspace-integration-check.py
```

## New workspace checklist

1. Clone/create the new workspace
2. Copy or `persist-import` the bundle
3. `git submodule update --init --recursive` if using this repo’s integrations
4. Confirm `identity/PROFILE.md` still says Aaron / Cam / EST
5. Confirm mesh flags: `daily_agi_research_scan`, `unlimited_subagents`, `cam_enhance_apply_requires_aaron`
6. Run `python3 scripts/workspace-integration-check.py`
7. Re-attach secrets/connectors locally

## Multi-PR workspace stack

See [WORKSPACES_WORKFLOW.md](WORKSPACES_WORKFLOW.md) for how this checkout relates to PR #2 (scan workspaces) and PR #3 (Brodmann viz).

## Versioning

`manifest.json` bumps `bundle_version` on each export. Newer bundle wins on import unless `--keep-local` is set.
