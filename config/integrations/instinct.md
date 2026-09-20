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
| Daily texture summaries | `brief` renders a markdown daily brief (`data/instinct/briefs/`, `--vault` distills to `vault/06-Life-Ops/instinct/briefs/`) |
| Human-in-the-loop send review | `outbox list/show/approve/discard` — Aaron's review lane; approve stages a draft for the gated comms pathway, never sends |
| Assistant scorecard | `stats` — done rate, avg time-to-done, follow-ups drafted, ask answer rate |
| Recall across the thread | `find` — case-insensitive search over thread, job titles, and notes |
| Natural time expressions | `--due` / `--until` accept relative durations: `+12h`, `+3d`, `+2w` |

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

## Cross-workspace (all coding workspaces)

Instinct is the follow-through ledger for every workspace in
`config/workspaces/registry.json`, not just Personal-Assistant:

- **Every job has a workspace.** `--workspace <id>` is validated against the registry;
  when omitted, the shared chooser (`cam_workspaces.choose_workspace`) routes by title —
  the same brain `run-cline.py` uses. `--coding` marks work as dispatchable.
- **run-cline hook.** `scripts/run-cline.py` drops every Cline run (any workspace) into the
  thread via `instinct.track_cline_run`; failed/timeout runs open a high-priority coding
  job in that workspace. Bookkeeping never breaks the run.
- **Needs Attention both ways.** `attention-sync` imports the queue distillate
  (`vault/10-Mesh-Distillates/needs-attention/latest.json`) as attention jobs — idempotent by
  item id, severity → priority, auto-closed when the item clears upstream. Instinct's own
  `needs_aaron` escalations flow back into the sweep carrying their workspace.
- **`workspaces`** — per-workspace rollup (connectivity, open/waiting/monitors, escalations,
  drafts); the brief gets a "By workspace" section.
- **`dispatch`** — print-only `run-cline.py --workspace-id …` plan for coding/attention jobs,
  priority-ordered. It never executes; `motor.cline` still fires only under `switch.autonomy`
  with the pattern's human gates (`instinct-check` fails if the engine ever imports subprocess).
- **`distill`** — sanitized mesh distillate (counts per workspace, no message text) to
  `vault/10-Mesh-Distillates/instinct/latest.json` plus a mesh note in the cline session cache.
- **Nightly loop** runs `instinct_sync` → `instinct_scan` → `instinct_distill`.
- **Policy propagation.** `.clinerules`, the `install-cline-rules.py` bundle (AGENTS snippet +
  Cursor rule), and `.cursor/rules/cam-cline.mdc` tell every workspace where open work lives;
  chooser signals route "instinct" / "follow-through" goals to Personal-Assistant.

## Agents, subagent spawns, connectors (round 5)

Instinct is now the ledger of a real team, not a single script:

- **Team** `team.follow-through` (`config/teams/follow-through.json`): `follow-through-lead`, `scheduler`, `inbox-triage`, `errand-runner`, `negotiator`, `watcher`, `qa`. Role prompts in `config/roles/`. Privilege defaults in `config/swarm/privileges.json` — no specialist default carries `outbound_send`; `inbox-triage` has no `web_fetch`.
- **Spawn runtime** `scripts/cam_swarm.py`: file-backed `synapse.spawn` / `assign_task` / `resolve_task` / `send_message` / `broadcast` / `terminate_lineage`. Child level = parent + 1, privileges ⊆ parent, Aaron-only never granted, unlimited depth/count, Aaron `kill`/`resume`.
- **Per-job subagent** `instinct delegate <job>`: picks the role (coding → `task-executor`, attention → `attention-triage`, life → `negotiator` / `scheduler` / `watcher` / `errand-runner` by title), spawns under `chief`, assigns the job, pins `delegation` on the job and sets it `waiting` on the subagent. `job done` resolves the action and retires the agent. Monitors stay `open` so the scan keeps firing.
- **Connectors in**: `scripts/calendar-sync.py` (ICS → prep jobs, read-only) and `scripts/inkbox-inbound.py` (email / SMS / missed call → thread, data only). Both run as `connectors_pull` before `instinct_sync` in the nightly loop. Registry of everything Cam can reach: `config/connectors/registry.json` (`scripts/connectors-check.py`, MCP `connectors_list`).
- **Still draft-only**: nothing above sends. Every outbound path ends in the outbox for Aaron.

## Ops

- `python3 scripts/instinct.py delegate <job-id> [--role R]` — spawn a subagent for a job · `python3 scripts/cam_swarm.py tree`
- `python3 scripts/calendar-sync.py --write` · `python3 scripts/inkbox-inbound.py --write` · `python3 scripts/connectors-check.py`
- Tests: `python3 scripts/test_instinct.py` · `python3 scripts/test_cam_swarm.py` · `python3 scripts/test_connectors.py`

- Nightly loop drafts follow-ups; Aaron reviews with `outbox list` → `outbox show <draft>`
  → `outbox approve|discard <draft>`. Approved drafts move to `data/instinct/outbox/approved/`
  where the gated comms pathway (`motor.inkbox` under `switch.outbound`) picks them up.
  **Approving is not sending** — and approval is Aaron-only CLI, not exposed over MCP.
- `brief --write` produces the daily markdown brief; `brief --vault` distills it to
  `vault/06-Life-Ops/instinct/briefs/` for durable memory.
- `stats` is the follow-through scorecard; `find` searches the whole ledger.
- Senses integrate by dropping event JSON into `data/instinct/inbox/`:
  `{"from","text"[,"ts","job","due","priority","reply_to"]}` — then `sync` folds them in.
  Due dates are validated at creation; malformed events are skipped and rolled back.
- Ledger writes are atomic (temp file + rename); a corrupt ledger fails with a clear
  message instead of a traceback.
