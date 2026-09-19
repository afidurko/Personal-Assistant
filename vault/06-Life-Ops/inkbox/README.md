# Inkbox — Cam agent identity

Source: [afidurko/inkbox](https://github.com/afidurko/inkbox) · [inkbox.ai](https://inkbox.ai)

Cam uses Inkbox for persistent agent identity (email, phone, vault, tunnels)
via `motor.inkbox` under `switch.outbound`. Live credentials stay in local
`INKBOX_API_KEY` — never commit.

See: `config/integrations/inkbox.md` · `identity/persistence/INKBOX.md`
