# LLMAvatarTalk integration — Cam’s talking face & voice

Source: [afidurko/LLMAvatarTalk-An-Interactive-AI-Assistant](https://github.com/afidurko/LLMAvatarTalk-An-Interactive-AI-Assistant)  
Path: [`integrations/llmavatartalk`](../../integrations/llmavatartalk) (git submodule)

## Role in the team

LLMAvatarTalk is Cam’s **presence runtime**: speech in → Cam reply → speech out → animated face.

| Piece | Tech (upstream) |
|---|---|
| Hear Aaron | NVIDIA RIVA ASR |
| Think | **nullclaw / Cam** (not AvatarTalk’s own LLM loop in production) |
| Speak | NVIDIA RIVA TTS |
| Face motion | NVIDIA Audio2Face |
| Optional body | Unreal Engine Metahuman |

**Important:** In this Personal-Assistant architecture, AvatarTalk must **not** become a second brain.  
Upstream `main.py` runs its own LangChain/NIM LLM loop for demos. For Cam:

1. ASR transcript → Cam / nullclaw (Aaron-only gated team)
2. Cam text reply → TTS
3. TTS audio → Audio2Face / Metahuman

## When to use which face/voice path

| Mode | Use when | Stack |
|---|---|---|
| **Simple** | Everyday chat, no GPU studio | Still portrait + light TTS (`config/persona/voice.json`) |
| **Full Cam presence** | Desk avatar / call presence | LLMAvatarTalk + RIVA + Audio2Face (+ UE optional) |

Prefer simple unless Aaron starts a presence session.

## Prerequisites (Aaron’s machine)

Documented upstream:

- NVIDIA NIM API key (`.env` → `NVIDIA_API_KEY`) — mainly for demo LLM; Cam production uses nullclaw providers
- NVIDIA Riva server (`config.py` `URI`, default port `50051`)
- Audio2Face (Omniverse)
- Optional: Unreal Engine Metahuman + Live Link

Tutorials in submodule: `docs/RIVA`, `docs/Audio2Face`, `docs/UE`.

## Cam-specific config

Mirror Cam prefs into AvatarTalk before launch:

- Language: `en-US` (Aaron / EST)
- RIVA voice: start with `English-US.Female-1` unless Aaron picks another — stored in `config/persona/voice.json`
- Approver: only Aaron may start a live avatar session or approve outbound spoken content

```bash
git submodule update --init --recursive
cd integrations/llmavatartalk
cp .env.sample .env   # fill secrets locally — never commit
# set URI in config.py to your Riva host
pip install -r requirements.txt
# demo loop (uses embedded LLM — for studio bring-up only):
python main.py
```

Production bridge (target): Cam emits reply text → `modules/tts.py` → `modules/audio2face.py` without calling AvatarTalk’s `LLMService`.

## Mesh / persistence

- Presence session events → task run events + `mesh/prefs` persona keys
- Do not store raw audio in git; distill “spoke with Aaron at …” notes into mesh
- Secrets stay local

## Privacy / gates

- Aaron-only tasking and approval
- Starting avatar listen/speak session is Aaron-initiated
- Outbound calls/FaceTime still `[gate]` even if avatar is running
- No continuous monitoring while Aaron is away unless Aaron explicitly enables a session
