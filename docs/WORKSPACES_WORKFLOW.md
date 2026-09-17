# Cam workspaces — integration & workflow

Aaron runs Cam across **repo checkouts**, **scan workspaces**, **integration submodules**, and **cloud-agent branches**. This doc confirms how they fit together and what is still open.

## Workspace map (confirmed)

| Layer | What it is | Status on this branch |
|---|---|---|
| **Personal-Assistant repo** | Cam identity, connectome, vault, teams | Active (`cursor/cam-brain-agi-scan-teams-bded`) |
| **Persistence bundle** | Cross-checkout Cam memory (`persist-export` / `persist-import`) | Present; must include teams + AGI grants |
| **Vault areas** | Obsidian second brain (`vault/01`…`10`) | Wired via smart-second-brain config |
| **Integration submodules** | Jarvis · PaddleDetection · LLMAvatarTalk · smart-second-brain | **Declared but empty until `git submodule update --init --recursive`** |
| **Scan workspaces (PR #2)** | health · architecture · vulnerability · updates · improvements | Lives on `cursor/system-health-brain-scan-d12d` — not in `main` yet |
| **Brodmann / 3D cortex (PR #3)** | Plasticity + human brain viz + health conductor | Lives on `cursor/swiftguide-brain-map-0f2c` — overlaps connectome viz |
| **Agent teams (PR #4 / this)** | AGI Research Scan · Capability · Information + sLM/DL | This branch |

## Parallel cloud-agent branches (same environment)

| Agent | Branch | PR | Role |
|---|---|---|---|
| Assistant (foundation) | `cursor/personal-assistant-foundation-ba29` | #1 merged | Base connectome |
| Brain map system intelligence | `cursor/system-health-brain-scan-d12d` | [#2 open](https://github.com/afidurko/Personal-Assistant/pull/2) | Continuous workspace scanners + neural mesh UI |
| Brain map swiftguide concepts | `cursor/swiftguide-brain-map-0f2c` | [#3 draft](https://github.com/afidurko/Personal-Assistant/pull/3) | Brodmann 3D + plasticity + system-health conductor |
| Cam AI research agents | `cursor/cam-brain-agi-scan-teams-bded` | [#4 draft](https://github.com/afidurko/Personal-Assistant/pull/4) | Daily AGI scan teams + sLM/DL cortex |

**Conflict note:** PR #4 ↔ PR #2 = low (README only). PR #4 ↔ PR #3 = **high** on `config/connectome/*`, `visualizations/connectome/app.js`, `scripts/connectome-route.py`. Merge order matters.

## End-to-end workflow (target)

```text
Aaron (sole task-giver / kill / enhance-approve)
        │
        ▼
┌─────────────────── Cam chief ───────────────────┐
│  Capability team  → finish tasks (unlimited subagents)
│  Information team → vault → mesh → web citations
│  AGI Research Scan (daily) → propose enhancements
│  sLM / DL cortex → local assists (not schedulers)
└───────────────┬─────────────────────────────────┘
                │
                ▼
   Connectome: sense → center → switch → motor
                │
                ▼
┌──────── scan workspaces (PR#2 when merged) ─────┐
│  health · architecture · vulnerability · updates │
│  improvements (synthesizes the above)            │
│  + agi_research (this branch registry)           │
└───────────────┬─────────────────────────────────┘
                │
                ▼
 mesh (nulltickets) + vault distillates + persistence bundle
                │
                ▼
 integrations (Jarvis / vision / AvatarTalk / second brain)
```

### Daily AGI path (this branch — confirmed working)

1. `sense.clock.daily` → `center.agi_scan` → `switch.research_scan` → `motor.web_fetch`
2. `python3 scripts/agi-research-scan.py` writes vault + mesh proposals
3. Functionality apply waits on Aaron: `switch.cam_enhance` / `cam-enhance-propose.py --aaron-approve`

### Cross-checkout path (persistence)

1. Export: `python3 scripts/persist-export.py --out /tmp/cam-persistence.zip`
2. New workspace: clone → `persist-import` → `git submodule update --init --recursive`
3. Confirm mesh-seed has `daily_agi_research_scan` + team configs

## Integration status checklist

| Integration | Config present | Code checkout | Runtime |
|---|---|---|---|
| Jarvis | `config/integrations/jarvis.md` | empty submodule | needs init |
| PaddleDetection | `config/integrations/paddledetection.md` | empty submodule | needs init |
| LLMAvatarTalk | `config/integrations/llmavatartalk.md` | empty submodule | needs init |
| smart-second-brain | `config/integrations/smart-second-brain.md` | empty submodule | needs Obsidian enable |
| iOS / Tailscale converse | docs + companions | companions present | machine-local |
| Null stack (nullclaw/tickets/boiler/hub) | architecture only | not vendored here | future |
| Scan workspace server (PR#2) | registry stub here | full TS on PR#2 | merge then `npm` |
| SwiftGuide / Brodmann viz (PR#3) | — | on PR#3 | merge carefully |

## Suggested merge / update order

1. **Keep PR #4 focused** on teams + AGI scan + sLM/DL + persistence completeness (this doc + export fix).
2. **Merge PR #2** next for continuous health/arch/vuln/updates workspaces + mesh UI — then add `agi_research` as a sixth `WorkspaceKind`.
3. **Rebase PR #3** onto the result — viz/plasticity should adopt AGI/sLM/DL nodes from #4 rather than the other way around.
4. After merges: init submodules; run `scripts/workspace-integration-check.py`.

## Commands

```bash
python3 scripts/workspace-integration-check.py
python3 scripts/agi-research-scan.py --dry-run
python3 scripts/connectome-check.py
python3 scripts/persist-export.py --out /tmp/cam-persistence.zip
```

Registry: `config/workspaces/registry.json`
