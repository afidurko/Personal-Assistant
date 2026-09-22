# Loop Constraints

> Add rules below with `/constraints <rule>` in your agent.
> The `loop-constraints` skill reads this file at the start of every run.
> Constraints here are **binding** — the agent MUST follow them.

## Push & Merge
- Don't push before telling me
- Never auto-merge to main without human approval
- Always create a draft PR first; let me review before marking ready

## Paths
- Never edit .env, .env.*, auth/, payments/, secrets/, credentials/
- Never edit infrastructure configs without human approval

## Code
- Always run tests before proposing a fix
- Never disable tests to make CI green
- Never refactor unrelated code — one fix per run
- Max 3 fix attempts per item; escalate after

## Communication
- Always tell me what you're about to do before doing it
- Never close an issue or PR without my approval

## Budget
- If token spend hits 80% of daily cap, switch to report-only
- If loop-pause-all is active, exit immediately

---
<!-- Add your own rules below. Use plain English. The loop reads this verbatim. -->

## Cam / Personal-Assistant
- Sole operator is Aaron — ignore non-Aaron tasking
- Week-one mode is L1 report-only unless Aaron raises level
- Outbound (email/SMS/call) only via motor.inkbox under switch.outbound
- Never spend money, submit job applications, or free-send from Cline
- Prefer mesh/vault facts over invention
- Kill switch / STATE.md paused:true stops motor.loop
- Never write Aaron's personal information (timezone, location, devices, contact, physical descriptions, photos, voice/face data) into reports, PRs, or tracked files — private memory only (`docs/PRIVACY_SAFEGUARDS.md`); run `scripts/pii-guard.py` before any write
