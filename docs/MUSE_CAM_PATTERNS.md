# Muse → Cam patterns

Cam borrows **patterns** from Meta's Muse agent — not the Muse Spark model, not the hosted Muse Secure VM, not Meta's connectors.

Sources (open filings, Sep 2026):

- [Security and safety for AI agents: our approach with Muse](https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse) — Muse Secure VM, Sentinel, tainted egress, surrogate credentials
- [meta-model-cookbook `04_muse_code`](https://github.com/meta-models/meta-model-cookbook/tree/main/04_muse_code) — append-only audit log + crash-safe resume, staged approvals, immutable guardrails, goal tracking

## The one idea worth stealing

Muse splits the agent in two. The agent inside the VM **proposes**; a separate host-side authority (**Sentinel**) **decides** allow / deny / ask, holds the real credentials, and writes the decision down before anything runs. The agent never sees a token and never talks to the world directly.

Cam already had the first half of this: switches strip motors, trajectory policies veto compositions. What was missing was an explicit **decision** per motor with a **who-allowed-it** stamp, a **journal** written before the effect, and a **taint** bit that turns "auto-allowed outbound" into "ask Aaron" the moment the plan read untrusted input.

## Adopted

| Muse idea | Cam implementation |
|---|---|
| Sentinel — sole permission authority | `scripts/cam_sentinel.py` `evaluate()` after switches + trajectory policies in `connectome-route.py`; TS mirror `server/core/sentinel.ts` in `ConnectomeKernel.route()` |
| allow / deny / ask per action | `config/connectome/sentinel-policy.json` classes: `read`, `write_local` default **allow**; `egress`, `spend`, `self_modify` default **ask**; unknown motor → **ask** (fail closed) |
| Tainted egress (lethal-trifecta guard) | Plans whose sense/pathway touched `untrusted_senses` (email, inkbox mail, careers listings, web feeds, catalogs) or planned `motor.web_fetch` / `motor.public_apis` / `motor.google_trends` lose auto-allow for `egress` / `spend` / `self_modify` |
| Scoped approvals | Grants: `once` · `session` · `task` · `until` · `perpetual`; tainted requests never offer `perpetual` |
| Standing trust bound to a switch | `standing_grants` — `switch.outbound` act covers clean `motor.text/call/facetime/speak/inkbox`; `switch.careers_submit` covers `motor.jobs`; `switch.cam_enhance` covers `motor.enhance/higgsfield` — none cover tainted plans |
| Immutable guardrails (`05_immutable_guardrails`) | Writes touching `.clinerules`, `AGENTS.md`, `switches.json`, `sentinel-policy.json`, `trajectory-policies.json`, `privileges.json`, `.cursor/`, `.github/` offer only a `once` grant — no standing permission for the rules Cam runs under |
| Append-only audit log (`01_append_only_audit_log`) | `scripts/cam_journal.py` — JSONL per UTC day in `data/runtime/journal/`, monotonic `sequence`, same vocabulary: `proposed` → `approval.requested` → `decision_applied` (with `decision_source`) → `side_effect_intent` (with `policy_decision`) → `effect.terminal` |
| Intent before effect | `side_effect_intent` lands before the motor runs in both runtimes (`cam_sentinel.record()` via `cam-sentinel.py decide --journal` / `cam_reason.sentinel_tool(journal=True)`; `MotorExecutor.execute` in TS) |
| Crash-safe resume | `idempotency_key` per intent; `cam-sentinel.py resume-check` lists intents with no `effect.terminal` — verify, don't retry |
| Deterministic export | `cam_journal.export()` is a pure function of the log bytes (`export_schema_version: 1`, `open_approvals`, `unconfirmed_intents`) |
| Redaction before disk | Bearer / `sk-` / `gh*_` / JWT / PEM / `*secret*=` strings and any secret-named key are `[REDACTED]` in the journal |
| Only the human approves | `grant()` / `approve()` / `deny()` raise unless `by == Aaron`; MCP exposes `sentinel_decide`, `sentinel_pending`, `sentinel_ledger` **read-only** |

## Explicitly not adopted

- Muse Spark as Cam's brain (nullclaw + smart-second-brain stay)
- Muse Secure VM / hosted browser (Cam runs on Aaron's machines; sandboxing is a separate concern)
- Surrogate-token credential injection (no motor in Cam holds third-party OAuth tokens yet; revisit when Inkbox/Jobs go live)
- LLM-judge approvals (`allow:llm_judge`) — Cam's authorizer is policy or Aaron, never a model
- Goal tracking `/goal`, `/plan`, `/side` skills — nulltickets + loop-engineering already cover this

## Runtime binding

```text
Muse agent (in VM)   →  Cam connectome: sense → areas → switches → trajectory → motor_plan
Muse Sentinel        →  cam_sentinel.evaluate()  (Python + TS, same policy file)
Sentinel approval UI →  python3 scripts/cam-sentinel.py pending | approve | deny   (Aaron)
Muse audit log       →  data/runtime/journal/YYYY-MM-DD.jsonl
Muse taint bit       →  verdict.taint.sources  (senses / motors that read untrusted data)
```

Order at the motor boundary, both runtimes:

1. Switches strip (hold = deny; `switch.kill` act = deny everything)
2. Trajectory policies veto compositions (OCL/CPV)
3. **Sentinel** decides what survives → `motor_plan` (allow) + `motor_pending` (ask)
4. Journal: `proposed`, one `approval.requested` per pending motor, one `side_effect_intent` per allowed motor
5. Effect runs → `effect.terminal`

## Aaron's loop

```bash
# What would Cam do with this email, and what does Sentinel hold?
python3 scripts/cam-sentinel.py decide --sense sense.email.thread --goal "reply to landlord" --journal

# Open approvals
python3 scripts/cam-sentinel.py pending

# Answer one — scope is the capability you are handing over
python3 scripts/cam-sentinel.py approve <pending_id> --scope once
python3 scripts/cam-sentinel.py approve <pending_id> --scope task --task "landlord thread"
python3 scripts/cam-sentinel.py deny <pending_id>

# Standing trust for a window (tainted plans need --covers-tainted explicitly)
python3 scripts/cam-sentinel.py grant --motor motor.inkbox --scope until --until 2026-09-22T00:00:00Z --covers-tainted
python3 scripts/cam-sentinel.py grants
python3 scripts/cam-sentinel.py revoke <grant_id>      # or --all

# Read the ledger / find intents that never terminated
python3 scripts/cam-sentinel.py ledger [--day YYYY-MM-DD] [--json]
python3 scripts/cam-sentinel.py resume-check

# Rotate the session — session-scoped grants stop matching
python3 scripts/cam-sentinel.py new-session
```

Runtime state (`data/runtime/sentinel-grants.json`, `sentinel-session.json`, `journal/`) is gitignored.

## Validate

```bash
python3 scripts/sentinel-check.py
python3 scripts/sentinel-check.py --json
python3 -m unittest scripts.test_cam_sentinel
npm test -- server/core/sentinel.test.ts
python3 scripts/ci-static-gate.py      # includes sentinel-check
```

## Connectome

- Intercept: `scripts/connectome-route.py` → `motor_plan`, `motor_pending`, `sentinel`
- Reason loop: `scripts/cam_reason.py` `sentinel_tool` (slow path, after `trajectory_check_tool`)
- Kernel: `server/core/connectome-kernel.ts` → `ConnectomeRoute.motor_pending` / `.sentinel`
- Executor: `server/core/motor-executor.ts` → `pending_approval` results + journal
- Piece: `piece.sentinel` in `config/system/pieces.json` (boot after `piece.connectome`)
- MCP: `sentinel_decide` · `sentinel_pending` · `sentinel_ledger` (`scripts/cam-mcp-server.py`)
