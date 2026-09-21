# Muse → Cam: Sentinel research + implementation

Research dive into Meta's Muse assistant (Sep 2026) and what carried over into Cam.
Applied: [[Connectome]] motor boundary now has a Sentinel. Doc: `docs/MUSE_CAM_PATTERNS.md`.

## What Muse is (open filings)

- Personal AI agent on **Muse Spark**; each user gets a **Muse Secure VM** — an isolated Linux box with a browser, code execution, subagents and cron.
- **Sentinel** lives *outside* the VM and is the only thing that can talk to connectors or the network. The agent proposes; Sentinel returns allow / deny / ask.
- Real credentials never enter the VM: the agent uses **surrogate tokens**, Sentinel swaps in the real one at egress.
- **Tainted egress**: once a process reads user data (an email body, a doc), it loses automatic network permission; any later outbound action needs a human yes. This is Meta's answer to the "lethal trifecta" (private data + untrusted input + a way to exfiltrate).
- **Muse Code** (dev harness) ships the same philosophy as recipes: append-only audit log written *before* effects, deterministic replay, staged approvals for compound shell, contained execution that probes its own sandbox, and **immutable guardrails** — the agent can edit its rules file only with a one-time grant, never a standing one.

Sources: research.meta.ai blog "Security and safety for AI agents: our approach with Muse"; `meta-models/meta-model-cookbook/04_muse_code`.

## Mapping to Cam

| Muse | Cam already had | Cam gained |
|---|---|---|
| Sentinel | switches (hold/act), trajectory policies (OCL/CPV) | explicit allow / ask / deny per motor, `motor_pending` |
| Tainted egress | — | taint bit from untrusted senses; standing grants stop covering tainted plans |
| Scoped approvals | switch flips | grants: once / session / task / until / perpetual, Aaron only |
| Audit log before effect | activity feed (after the fact) | `data/runtime/journal/*.jsonl` — proposed → approval.requested → decision_applied → side_effect_intent → effect.terminal |
| Immutable guardrails | Cline denylist | guardrail paths only get `once` |
| Crash-safe resume | — | `idempotency_key` + `resume-check` |

## Not carried over (on purpose)

Muse Spark model · hosted VM · surrogate tokens (no live third-party creds in Cam yet) · LLM-judge approvals · `/goal` `/plan` skills (nulltickets + loops cover it).

## Files

- `config/connectome/sentinel-policy.json`
- `scripts/cam_sentinel.py` · `scripts/cam_journal.py` · `scripts/cam-sentinel.py`
- `scripts/sentinel-check.py` · `scripts/test_cam_sentinel.py`
- `server/core/sentinel.ts` · `server/core/sentinel.test.ts`
- wired: `connectome-route.py`, `cam_reason.py`, `cam-mcp-server.py`, `connectome-kernel.ts`, `motor-executor.ts`

## Aaron's loop

```bash
python3 scripts/cam-sentinel.py pending
python3 scripts/cam-sentinel.py approve <id> --scope once
python3 scripts/cam-sentinel.py ledger
```

## Open questions for Aaron

- Which switches should stop being "standing grants" and always ask? (`switch.careers_submit` is the obvious candidate once Jobs goes live.)
- Do we want a session to rotate on every Cam restart (`new-session`), or on Aaron's say?
- When Inkbox holds real OAuth tokens, adopt surrogate credentials at `motor.inkbox`.
