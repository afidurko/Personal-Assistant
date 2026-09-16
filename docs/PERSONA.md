# Cam persona — face & voice

Goal: Aaron recognizes **Cam** by face and voice. Only Aaron may task / approve.

## Stack choice

Aaron’s repo [LLMAvatarTalk](https://github.com/afidurko/LLMAvatarTalk-An-Interactive-AI-Assistant) is now the **full presence** path:

```text
Aaron speaks → RIVA ASR → Cam (nullclaw team) → RIVA TTS → Audio2Face → (optional Metahuman)
```

Submodule: `integrations/llmavatartalk`  
Details: `config/integrations/llmavatartalk.md`

Everyday / low-resource mode stays simpler:

```text
Still portrait (identity/persona/cam-face.png) + light TTS (config/persona/voice.json)
```

## Modes

| Mode | Face | Voice | When |
|---|---|---|---|
| Simple | Still portrait | Cloud/local TTS | Default chat |
| Full presence | Audio2Face (+ UE Metahuman) | NVIDIA RIVA TTS | Desk avatar / rich talk |
| Live bridge | Same as active mode | Same | Text / call / FaceTime `[gate]` |

## Recommended bring-up order

1. **Simple face** — generate or set `identity/persona/cam-face.png` (chat/UI)
2. **RIVA + AvatarTalk studio** — follow upstream RIVA / Audio2Face tutorials on Aaron’s GPU machine
3. **Point TTS voice id** in `config/persona/voice.json` at the RIVA voice Cam should use
4. **Bridge** AvatarTalk I/O to Cam (nullclaw) so AvatarTalk is not a second brain
5. **Optional** Metahuman in Unreal for full-body presence
6. Wire call/FaceTime to the same voice (and face if video)

## Voice defaults (editable)

```json
{
  "provider": "nvidia_riva",
  "voice_id": "English-US.Female-1",
  "locale": "en-US"
}
```

Aaron can change voice id anytime; Cam must not clone Aaron’s voice unless Aaron asks.

## Privacy

- Aaron-only control
- No always-on listen while Aaron is away
- Outbound spoken / FaceTime still `[gate]`
- Raw audio not committed to git

## Status

- LLMAvatarTalk submodule: **added**
- Operator lock: Aaron-only
- Simple portrait file: still optional polish
- Full presence: requires Aaron’s RIVA/Audio2Face machine setup
- Production Cam↔AvatarTalk bridge (skip embedded LLM): next implementation step
