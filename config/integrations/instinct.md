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
| Follows up on dropped threads | Every Aaron ask is tracked until answered (`--reply-to` or job completion); `scan` surfaces all asks unanswered past `reply_hours` |
| Proactive outreach | `scan --write` drafts follow-up nudges (with job context) into `data/instinct/outbox/` |
| Finishes jobs, doesn't re-ask | Follow-up cadence respects `last_followup`; jobs escalate `needs_aaron` after `max_followups` drafted nudges and surface in Needs Attention sweeps |
| Ticket / restock monitoring | Monitor jobs (`job add --monitor HOURS`) — recurring watch nudges, never escalate |
| Priorities and texture of life | `--priority high/normal/low` halves/doubles the stale window; `job snooze --until` parks a job |
| Connected senses feed it | `sync` folds event drops from `data/instinct/inbox/*.json` (Inkbox, calendar, loops — any sense writes drops; the engine never fetches) |
| Persistent cloud computer | Nightly L1 loop `instinct-followups` + schedule `cam-nightly-instinct-scan` run the scan unattended |
| Text-first interface | Thread `ingest` from any Cam surface; MCP tools `instinct_scan` / `instinct_report` / `instinct_brief`; no new UI |
| Daily texture summaries | `brief` renders a markdown daily brief (`data/instinct/briefs/YYYY-MM-DD.md`) |

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

- Engine: `scripts/instinct.py` (ingest / sync / job / scan / report / brief / thread / doctor)
- Tests: `scripts/test_instinct.py` (`python3 -m unittest scripts.test_instinct`)
- Check: `scripts/instinct-check.py`
- Sense: `sense.instinct.followup` → `center.ops`
- Motor: `motor.instinct` under `switch.autonomy` (+ `switch.kill`)
- Outbound handoff: drafts only; `motor.inkbox` under `switch.outbound`
  (`instinct_followup_draft_only` trajectory policy strips violations)
- Loop: `instinct-followups` L1 pattern (`scripts/loop-run.py --pattern instinct-followups`)
- Schedule: `cam-nightly-instinct-scan` (03:00 UTC, report/draft-only)
- MCP: `instinct_scan` / `instinct_report` / `instinct_brief` in `scripts/cam-mcp-server.py`
- Needs Attention: `needs_aaron` escalations land in `data/instinct/needs-attention.json`
  and surface through `scripts/needs-attention.py` sweeps (aaron_gate, never auto-clear)
- State: `data/instinct/` (ledger, spikes, outbox, inbox, briefs) — gitignored; never commit PII
- Tests isolate state via `INSTINCT_DATA_DIR`

## Ops

- Nightly loop drafts follow-ups; Aaron reviews the outbox before anything sends.
- `brief --write` produces the daily markdown brief; distill durable outcomes to mesh/vault.
- Senses integrate by dropping event JSON into `data/instinct/inbox/`:
  `{"from","text"[,"ts","job","due","priority","reply_to"]}` — then `sync` folds them in.
