# Cam Instinct — proactive follow-through engine

Original, local-first module inspired by the behavior model of **Instinct**
(Spear Street Technology, Inc., San Francisco — instinct.com), the invite-only
personal AI assistant you text or call. No code, data, or services are shared
with that product; only the publicly described behavior concepts are
replicated, and Cam's trust model deliberately diverges where Instinct's
launch-week record showed risk.

## What Instinct does (public record, 2026-08)

- One continuous conversation thread — no projects or workspaces to manage.
- A persistent worker that keeps state between messages and keeps working.
- Proactive by design: follows up on dropped threads, reaches out first.
- Finishes jobs: bookings, bill negotiation, inbox triage, vendor coordination.
- Acts with real authority: its ToS appoints it as the user's binding agent.
- Deep device access: email, messaging, screen, audio, location, keystrokes.

## Parity map (what this module replicates)

| Instinct behavior | Cam implementation |
| --- | --- |
| One continuous thread | `data/instinct/ledger.json` `thread[]` — single append-only conversation |
| Persistent worker state | Job ledger survives between invocations (`jobs[]`: open / waiting / done) |
| Follows up on dropped threads | `scan` detects Aaron's unanswered asks past `reply_hours` |
| Proactive outreach | `scan --write` drafts follow-up nudges into `data/instinct/outbox/` |
| Finishes jobs, doesn't re-ask | Jobs escalate `needs_aaron` only after `max_followups` drafted nudges |
| Persistent cloud computer | Cam's own workspace + schedules (`sync-cline-schedules.py`) run the scan |
| Text-first interface | Thread `ingest` from any Cam surface; no new UI |

## Deliberate divergences (the missing 0.08%)

These Instinct behaviors are excluded **by design** per `.clinerules`:

1. **No unattended sends.** Instinct sent an email a user never approved
   (Katie Jacobs Stanton, launch week). Here every follow-up is a draft;
   live send hands off to `motor.inkbox` and requires `switch.outbound` act.
2. **No binding agent authority.** Instinct's ToS lets it enter agreements
   and transactions on your behalf. Cam never spends or commits from Cline.
3. **No perpetual data license / model training on Aaron's data.** Instinct
   trains on user materials by default (go-forward opt-out only). This ledger
   stays in-repo; nothing leaves the workspace; nothing trains on it.
4. **No blanket device capture.** No screen, keystroke, audio, or location
   ingestion. Senses stay the connectome ones Aaron already enabled.
5. **Prompt-injection posture.** Instinct followed instructions mailed into an
   inbox (Alex Cohen's test). This engine ingests only what Aaron or Cam roles
   explicitly `ingest`; scan logic is deterministic, not instruction-following.

## Wiring

- Engine: `scripts/instinct.py` (ingest / job / scan / report / thread / doctor)
- Check: `scripts/instinct-check.py`
- Sense: `sense.instinct.followup` → `center.exec`
- Motor: `motor.instinct` under `switch.autonomy` (+ `switch.kill`)
- Outbound handoff: drafts only; `motor.inkbox` under `switch.outbound`
- State: `data/instinct/` (ledger, spikes, outbox) — never commit PII

## Ops

- Nightly `scan --write` is a natural L1 loop candidate (`daily-triage` sibling).
- `report` feeds STATE.md-style briefs; distill durable outcomes to mesh/vault.
- Escalations (`needs_aaron`) surface via Needs Attention sweeps.
