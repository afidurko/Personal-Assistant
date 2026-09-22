# Security & privacy policy

Cam (Personal-Assistant) is a public repository that describes **how an assistant
is built** — never **who its operator is**. Aaron's personal information is held in
sealed private memory on Aaron's host and is out of scope for this repository.

## Guarantees

- No personal information about Aaron or any other real person is tracked in git,
  in pull requests, or in CI logs. Enforced by `scripts/pii-guard.py` at pre-commit,
  pre-push, `ci-static-gate`, and the `privacy-guard` GitHub Action.
- No secrets are tracked. Credentials come from environment variables or the host
  keychain; the guard blocks tokens, keys, and `.env` files.
- Personal data the runtime needs is stored encrypted at rest
  (`scripts/private-memory.py`) and referenced by key.
- Cam's Sentinel denies any motor plan that would move private-memory content
  off-host (email, post, apply, commit) — no approval scope is offered.
- Runtime journals and distillates are redacted before they are written.

Full policy, layers, runbooks, and threat model: [`docs/PRIVACY_SAFEGUARDS.md`](docs/PRIVACY_SAFEGUARDS.md).

## Reporting a leak or vulnerability

Only Aaron operates this system. If you find personal information or a secret in
this repository, its history, a branch, or a pull request:

1. Do **not** open a public issue quoting the data.
2. Use GitHub's private vulnerability reporting on this repository, or contact the
   repository owner through GitHub.
3. Include the commit / path / line, not the content itself.

Aaron's response runbook is in `docs/PRIVACY_SAFEGUARDS.md → Incident response`.

## Scope for contributors and agents

- Cline sessions, Cloud Agents, and loop automations follow `.clinerules`, `AGENTS.md`
  and `.cursor/rules/cam-cline.mdc`: never write personal information into tracked
  files or PR text; store it with `private-memory.py put` and reference the key.
- `config/privacy/`, `.githooks/`, `.github/`, `.gitignore`, `scripts/pii-guard.py`,
  `scripts/privacy.py`, `scripts/private_memory.py` and this file are Sentinel
  guardrail paths — changes require a one-time grant from Aaron.
- Run `python3 scripts/pii-guard.py --all` before every push; the MCP tool
  `privacy_scan` is available to agents.

## Supported versions

`main` only. Security-relevant fixes land on `main` and are not back-ported.
