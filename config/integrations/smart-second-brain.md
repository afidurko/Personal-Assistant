# Smart Second Brain integration — Cam’s knowledge cortex

Source: [afidurko/smart-second-brain](https://github.com/afidurko/smart-second-brain)  
Path: [`integrations/smart-second-brain`](../../integrations/smart-second-brain) (git submodule)  
Upstream product: [smartsecondbrain.dev](https://smartsecondbrain.dev) (Obsidian plugin)

## Role in the team

Smart Second Brain enhances Cam’s **long-term knowledge** over Aaron’s notes:

- Hybrid search (keyword + meaning)
- Topic graph over the vault
- Agents that read/write notes with skills/memory/MCP

| Layer | Owner |
|---|---|
| Execution / tools / channels | nullclaw (Cam) |
| Task truth / mesh KV | nulltickets |
| Orchestration | nullboiler |
| Human control | Aaron via nullhub / chat |
| Vault intelligence | **smart-second-brain** |
| Talking face/voice | LLMAvatarTalk |

Cam should query the second brain before answering from thin air when Aaron’s notes may hold the answer. Distill outcomes back into mesh **and** the vault.

## How Cam uses it

1. Aaron keeps an Obsidian vault (path recorded in `config/persona/vault.json` when set)
2. Smart Second Brain plugin indexes search + graph
3. Cam (researcher / memory-curator / chief) pulls vault context for research, docs, careers, life ops
4. Writes/edits to the vault follow autonomy policy (complete without interference once Aaron tasked) and are logged

## Install (Aaron’s machine)

1. Install Obsidian
2. Install **Smart Second Brain** community plugin (or build from this submodule — see upstream README/CONTRIBUTING)
3. Point Cam at the vault path in `config/persona/vault.json`
4. Optional: embeddings + AI provider inside the plugin for full agent mode

Out of the box upstream: search/graph can stay local; network only to providers Aaron configures.

## Mesh bridge

| Namespace | Content |
|---|---|
| `mesh/vault` | vault path, last sync, topic summaries |
| `mesh/facts` / `mesh/projects` | distilled from vault when relevant |

Persistence export includes persona + mesh seed so future workspaces remember the vault link.

## Boundaries

- Only Aaron may task Cam to change the vault’s meaning at a high level
- Cam may complete note edits for assigned work without mid-task interruption
- No telemetry beyond providers Aaron configures in the plugin
