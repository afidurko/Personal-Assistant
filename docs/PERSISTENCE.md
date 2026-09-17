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
| Cline cache | `identity/persistence/cline-session-cache.json` | Coding sessions across workspaces |
| Bundle manifest | `identity/persistence/manifest.json` | Versioned export metadata |
| Cline rules | `.clinerules` | Policy for every Cline session / workspace |

## Guarantees

1. **Survives repo clones** — identity files are committed (no secrets in them).
2. **Portable bundle** — `scripts/persist-export.py` builds a zip/json bundle Cam can import into a new workspace.
3. **Import into future workspaces** — `scripts/persist-import.py` restores identity + mesh seed.
4. **Runtime mesh** — when nulltickets is up, curator `PUT`s seed into `mesh/prefs`, `mesh/facts`, `mesh/careers`, etc.
5. **Auto-archive** — after completed tasks, distill notes into mesh (Q60); export refreshes the portable bundle.

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
```

## New workspace checklist

1. Clone/create the new workspace
2. Copy or `persist-import` the bundle
3. `git submodule update --init --recursive` (includes `integrations/cline`)
4. Confirm `.clinerules` is present for Cline policy inheritance
5. Confirm `identity/PROFILE.md` still says Aaron / Cam / EST
6. Re-attach secrets/connectors locally (`cline auth` or provider env vars)

## Versioning

`manifest.json` bumps `bundle_version` on each export. Newer bundle wins on import unless `--keep-local` is set.
