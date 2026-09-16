# Cam live converse (mic + camera + speak)

## What this adds
Cam can hold a **voice conversation** through a companion:

| Piece | Path | Role |
|---|---|---|
| Web companion | `companions/web/` | Browser mic + camera (`getUserMedia`) + speech recognition + Cam TTS |
| Converse server | `scripts/cam-converse-server.py` | Accepts turns / spikes; replies as Cam; logs to vault |
| Launch | `scripts/serve-cam-converse.sh` | Starts server on `:8787` |
| iOS native | `companions/ios/` | Same capabilities — Xcode app still to be generated |

## Run on Aaron’s Mac / phone (required for real mic)

Cloud Agent VMs have **no microphone**. Run locally:

```bash
python3 scripts/cam-converse-server.py
# open http://127.0.0.1:8787
# on iPhone (same Wi‑Fi): http://<mac-lan-ip>:8787
```

1. Tap **Enable mic & talk** → allow Microphone  
2. Optionally **Enable camera** → allow Camera  
3. Speak; Cam replies in text + browser soft TTS  

## API
- `GET /api/health`
- `POST /api/turn` `{ "text"|"transcript", "source": "mic"|"text" }`
- `POST /api/spike/mic` · `POST /api/spike/camera`
- `GET /api/session`

## Connectome
Mic → `sense.ios.mic` · Camera → `sense.ios.camera` · Chat fallback → `sense.chat.aaron`

## Logs
`vault/10-Mesh-Distillates/converse/*.jsonl`
