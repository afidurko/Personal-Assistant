# Inkbox — agent identity & outbound channels

Source: https://github.com/afidurko/inkbox  
Product: https://inkbox.ai  
Motor: `motor.inkbox` · Sense: `sense.inkbox.event` · Hotspot: `hotspot.inkbox`  
Config: `config/integrations/inkbox.json`  
Credential: `INKBOX_API_KEY` (local `.env` only)

Inkbox gives Cam persistent agent identity (email, phone, vault, tunnels).
Live send/call/SMS goes through `motor.inkbox` under `switch.outbound`.
Cline must not fire outbound Inkbox sends — hand to gated motors / `comms`.
