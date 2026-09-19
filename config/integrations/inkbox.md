# Inkbox integration — agent identity & outbound channels

Source: [afidurko/inkbox](https://github.com/afidurko/inkbox)  
Path: [`integrations/inkbox`](../../integrations/inkbox) (git submodule)  
Product: [inkbox.ai](https://inkbox.ai)

## Role in the team

Inkbox is Cam’s **agent identity + communication infrastructure** — email (custom
domains), phone/SMS/iMessage, encrypted credential vault, and outbound tunnels.
It is **not** the brain and **not** a free-send path from Cline.

| Concern | Owner |
|---|---|
| Thinking / planning / subagents | nullclaw (Cam) |
| Task queue / mesh truth | nulltickets |
| Local deterministic chores | Jarvis |
| Coding edits | Cline (`motor.cline`) |
| Presence (face/voice) | LLMAvatarTalk |
| Agent email / phone / identity / vault / tunnels | **Inkbox** (`motor.inkbox`) |

**Comms** owns live send/call under `switch.outbound`. Other roles may use Inkbox
for SDK/CLI work in the coding workspace, or read/list under autonomy — never
bypass outbound gates from Cline.

## Connectome

```text
sense.inkbox.event → center.comms → switch.outbound
                   → motor.inkbox (+ motor.text / motor.call when channel matches)
```

Config: [`inkbox.json`](inkbox.json)  
Hotspot: `hotspot.inkbox`  
Motor: `motor.inkbox` (requires `switch.outbound` + `switch.kill`)

## Runtime surface

| Piece | Path |
|---|---|
| Integration config | `config/integrations/inkbox.json` |
| Policy | `config/integrations/inkbox.md` |
| Wiring check | `scripts/inkbox-check.py` |
| SDK / CLI / skills | `integrations/inkbox` (submodule) |
| Coding workspace id | `inkbox` in `config/workspaces/registry.json` |
| Mesh namespace | `mesh/comms` (+ `mesh/tools` for SDK notes) |
| Credential | `INKBOX_API_KEY` in local `.env` only — never commit |

## Enable

```bash
git submodule update --init integrations/inkbox
# optional: pip install inkbox  /  npm i -g @inkbox/cli
export INKBOX_API_KEY=ApiKey_...   # from https://inkbox.ai/console
python3 scripts/inkbox-check.py
python3 scripts/choose-workspace.py --goal "inkbox sdk identity"
```

## How agents use it

1. Aaron tasks Cam (or a standing outbound goal is active).
2. `connectome-route.py` may select `hotspot.inkbox` / `hotspot.email`.
3. Live send/call/SMS goes through `motor.inkbox` only when `switch.outbound` is act.
4. Kill switch silences Inkbox motors with all other outbound effectors.
5. Coding on the Inkbox SDK itself uses workspace id `inkbox` via `motor.cline`.
6. Log every outbound attempt to nulltickets / `mesh/runs`; fail closed if recipient unsure.

## Boundaries

- Do **not** send email/SMS/calls from Cline — hand to `motor.inkbox` / `comms`
- Never commit `INKBOX_API_KEY`, phone numbers, or raw vault secrets
- Prefer Jarvis for local non-network chores; prefer Inkbox for agent email/phone identity
- Prefer LLMAvatarTalk for face/voice presence; Inkbox for addressable identity channels
- Spending (number provisioning, domains) stays under Aaron-gated outbound autonomy

## Cross-workspace checklist

1. `persist-import` (brings mesh-seed + integration config)
2. `git submodule update --init integrations/inkbox`
3. Set `INKBOX_API_KEY` locally when live calls are needed
4. `python3 scripts/inkbox-check.py` and `python3 scripts/workspace-integration-check.py`
