# Personal-Assistant — Cam for Aaron

Cam is Aaron’s always-on Argentine assistant (32, blue eyes, brown hair, soft airy voice)
for life automation, source-backed research, documents, LinkedIn/Indeed jobs, and
talking presence — with a smart second brain over Aaron’s notes.

## Design

- **Brain:** nullclaw + [smart-second-brain](https://github.com/afidurko/smart-second-brain)
- **Vault:** [`vault/`](vault/) starter Obsidian vault (open this folder in Obsidian)
- **Tasks/mesh:** nulltickets · **Orchestration:** nullboiler · **Control:** Aaron only
- **Presence:** [LLMAvatarTalk](https://github.com/afidurko/LLMAvatarTalk-An-Interactive-AI-Assistant) (RIVA + Audio2Face)
- **Tools:** Jarvis · Cline · PaddleDetection · LinkedIn/Indeed
- **Autonomy:** Aaron assigns; Cam finishes without mid-task interference; 24/7 available

Face: [`identity/persona/cam-face.jpg`](identity/persona/cam-face.jpg)  
Persona: [docs/PERSONA.md](docs/PERSONA.md) · Persistence: [docs/PERSISTENCE.md](docs/PERSISTENCE.md) · Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Connectome architecture (brain map)

Cam is wired like a nervous system — see [docs/CONNECTOME_ARCHITECTURE.md](docs/CONNECTOME_ARCHITECTURE.md):

```text
Aaron → sensory → higher centers → circuit switches → motor effectors
```

```bash
# Example: route a careers spike to motor plan
python3 scripts/connectome-route.py --sense sense.careers.listing --goal "watch roles"
# Kill switch silences motors
python3 scripts/connectome-route.py --sense sense.chat.aaron --kill
# Live brain + spinal cord visualization (all repos)
bash scripts/serve-connectome-viz.sh
# open http://127.0.0.1:8765/visualizations/connectome/
```

## Open the vault (2 minutes)

1. Install [Obsidian](https://obsidian.md)
2. **Open folder as vault** → choose `vault/` in this repo
3. Community plugins → install **Smart Second Brain** → Enable
4. Start at [[Welcome]] (`vault/Welcome.md`)

Cam is already pointed at `vault` via `config/persona/vault.json`.

## Submodules

```bash
git submodule update --init --recursive
bash scripts/cam-avatar-hint.sh
python3 scripts/persist-export.py --seed-only
```

## Status

Persona locked. Starter vault created. Always-on autonomy set.
Cline wired as shared coding effector for all agents and future workspaces.
Next: enable Smart Second Brain in Obsidian + RIVA/Audio2Face studio + live Null stack.
