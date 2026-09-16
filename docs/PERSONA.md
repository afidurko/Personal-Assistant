# Cam persona — face & voice

Goal: Cam is not a nameless bot. Aaron should recognize Cam’s **face** and **voice**
in chat, calls, and FaceTime-style sessions — with Aaron as sole approver.

## How we do it (three layers)

```text
1) Face  → still portrait + optional talking-head later
2) Voice → TTS for Cam speaking; STT for Aaron talking back
3) Live  → phone / FaceTime / voice-call bridge (gated)
```

Keep it simple: ship face + TTS first; add live call video avatar only if needed.

### Layer 1 — Face (now)

| Option | Effort | Notes |
|---|---|---|
| **A. Generated portrait** (recommended first) | Low | Create `identity/persona/cam-face.png`; use in README, nullhub, chat UI |
| B. Photo you provide | Low | You upload a reference; we derive a consistent avatar |
| C. Animated / talking head | Medium | Lip-sync or realtime avatar for calls later |

### Layer 2 — Voice (now)

| Option | Effort | Notes |
|---|---|---|
| **A. Cloud TTS** (OpenAI / similar) | Low | Stable “Cam” voice id in `config/persona/voice.json` |
| B. Local TTS (macOS `say`, Piper, etc.) | Low–Med | Private, works offline; quality varies |
| C. Cloned / premium voice (ElevenLabs-class) | Med | More “human”; needs API key + consent policy |

Pair with STT (Whisper / provider STT) so Aaron can talk to Cam hands-free.

### Layer 3 — Live talk (next)

- Text / call / FaceTime already granted with `[gate]`
- Bridge via nullclaw channels + OpenClaw-style phone/macOS companion for FaceTime
- On call: Cam uses TTS voice; optional face overlay or companion video later
- Never analyze call video unless Aaron asks that session

## Recommended path for this repo

1. Aaron picks face style + voice style (below)
2. Generate/store Cam face under `identity/persona/`
3. Save voice profile in `config/persona/voice.json`
4. Wire TTS into comms role for spoken replies / call scripts
5. Later: live FaceTime/call bridge using that same face+voice

## Privacy

- Face/voice assets are Cam’s brand — not Aaron’s likeness unless Aaron opts in
- No voice-cloning of Aaron without explicit ask
- Outbound spoken messages still `[gate]`

## Status

- Operator lock: Aaron-only — done
- Face file: awaiting style pick
- Voice profile: stub ready, awaiting provider pick
