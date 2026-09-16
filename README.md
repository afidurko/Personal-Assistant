# Personal Assistant

Neural-mesh personal assistant that continuously scans system health, architecture, vulnerabilities, updates, and improvement opportunities — visualized as an interactive brain map with persistent memory.

## Capabilities

| Workspace | Role |
| --- | --- |
| **System Health** | Vitals: resources, readiness, process health |
| **Architecture Map** | Structural topology and layering |
| **Vulnerability Scan** | Threat surface and insecure patterns |
| **Updates & Drift** | Freshness and tooling drift |
| **Improvement Engine** | Cross-workspace actionable suggestions |

Scans feed a **neural mesh** (nodes + weighted edges) and **persistent memory** (`data/memory.json`). Brain-map colors shift live:

- Blue — scanning
- Green — healthy
- Amber — warning
- Coral — critical
- Slate — idle / stale

Nodes and workspaces are interactive: focusing a region spreads activation across linked workspaces.

## Quick start

```bash
npm install
npm run dev
```

- UI: http://localhost:5173
- API / WS: http://localhost:8787 (`/api/state`, `/ws`)

One-shot scan:

```bash
npm run scan
```

## Architecture

```
shared/          Domain types & color palette
server/
  workspaces/    Parallel health / arch / vuln / updates / improvements scanners
  core/          Neural mesh, persistent memory, scan orchestrator
  index.ts       Express + WebSocket fan-out
src/             React brain map UI
data/            Persisted mesh + memory (gitignored runtime state)
```

Continuous scanning starts with the server so the brain map is always observing.
