# Personal-Assistant — Cam for Aaron

Cam is Aaron’s always-on Argentine assistant (32, blue eyes, brown hair, soft airy voice)
for life automation, source-backed research, documents, LinkedIn/Indeed jobs, and
talking presence — with a smart second brain over Aaron’s notes.

## Design

- **Brain:** nullclaw + [smart-second-brain](https://github.com/afidurko/smart-second-brain)
- **Tasks/mesh:** nulltickets · **Orchestration:** nullboiler · **Control:** Aaron only
- **Presence:** [LLMAvatarTalk](https://github.com/afidurko/LLMAvatarTalk-An-Interactive-AI-Assistant) (RIVA + Audio2Face)
- **Tools:** Jarvis · PaddleDetection · LinkedIn/Indeed
- **Autonomy:** Aaron assigns; Cam finishes without mid-task interference; 24/7 available

Face: [`identity/persona/cam-face.jpg`](identity/persona/cam-face.jpg)  
Persona: [docs/PERSONA.md](docs/PERSONA.md) · Persistence: [docs/PERSISTENCE.md](docs/PERSISTENCE.md) · Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Stack

```text
Aaron (sole task-giver) → Cam team
  → nulltickets mesh + smart-second-brain vault
  → Jarvis / PaddleDetection / LinkedIn+Indeed
  → LLMAvatarTalk presence
```

## Submodules

```bash
git submodule update --init --recursive
bash scripts/cam-avatar-hint.sh
python3 scripts/persist-export.py --seed-only
```

Set Obsidian vault path in `config/persona/vault.json` when ready.

## Status

Persona locked. Face created. Always-on autonomy set. smart-second-brain added.
Next: vault path + RIVA/Audio2Face studio bring-up + live Null stack.
