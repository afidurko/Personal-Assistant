# Privacy safeguards — keeping Aaron's personal information out of public view

**Authorized by:** Aaron · **Date:** 2026-09-22 · **Status:** enforced · **Owner:** Cam (Sentinel-gated)

This repository is **public**. It may describe *how Cam works*; it may never describe
*who Aaron is*. Everything personal lives in **private memory** on Aaron's host and is
referenced from tracked files by key. Seven independent layers enforce that, so a
single mistake — by Aaron, by Cam, by a Cline session, or by a Cloud Agent — cannot
publish personal data.

> The human needs to be safe. Protecting Aaron from information leaks, hackers, and
> accidental disclosure is a standing goal that outranks convenience.

**For any operator.** Nothing in the stack is specific to Aaron: the policy expands an
`operator.handle` / `operator.display_name` pair into its paths and patterns, and the
operator's own facts (full name, street, employer, …) are sealed as **protected terms**
in private memory that the guard blocks everywhere. `scripts/privacy-init.py` sets it
up for a new person in one command; `scripts/privacy-kit.py export <repo>` carries the
whole stack into another repository. Start with
[`PRIVACY_QUICKSTART.md`](PRIVACY_QUICKSTART.md).

---

## 1. Data classification

| Class | Examples | Where it lives | May appear in git / PRs / logs? |
|---|---|---|---|
| **Public** | How Cam is built, setup steps, connectome configs, persona of *Cam* (fictional), scripts, docs | repo | yes |
| **Internal** | Runtime state, distillates, QA results, sentinel ledger | `data/runtime/` (gitignored) or `vault/10-Mesh-Distillates/` after scrubbing | only after `privacy.scrub_obj` |
| **Private (personal information)** | Anything describing Aaron or another real person: full name, contact details, **timezone / location**, device names, **physical or biometric descriptions**, photos, voice/face samples or vectors, health, finances, employment specifics, relationships, calendar contents, message contents, home paths, IPs | **private memory** (`scripts/private-memory.py`) + `identity/aaron/local/` | **never** |
| **Secret** | API keys, tokens, OAuth, passwords, private keys, `.env` | host keychain / env vars / private memory | **never** |

"Aaron" (first name) and the fact that Aaron is the sole operator are public by design.
Nothing else about Aaron is.

### Keys currently held in private memory

| Key | Content | Public stub |
|---|---|---|
| `identity.aaron.visual_profile` | face-recognition notes (traits, source photos, third-party notes) | `identity/aaron/VISUAL_PROFILE.md` |
| `identity.aaron.enroll_index` | enrollment index with source refs, labels, confidence | `identity/aaron/enroll-index.json` |
| `identity.aaron.timezone` | operator timezone | `operator_local` placeholder in configs; runtime reads `CAM_OPERATOR_TZ` |
| `privacy.personal_terms` | the operator's **protected terms** — facts the guard must block wherever they appear | none; `private-memory.py protected` prints a count only |

Add new facts the same way: `put` the value (add `--protect` so the guard also blocks
it), reference the key, never paste the value. Facts that have no runtime use — a
surname, a street, an employer, a school — go straight to
`private-memory.py protect --value "…"`.

---

## 2. The layers

```text
 Aaron / Cam / Cline / Cloud Agent writes something
        │
 L1  .gitignore ─────────── private paths, media, keys, journals never become candidates
        │
 L2  pre-commit hook ────── scripts/pii-guard.py --staged   (content + path rules)
        │
 L2' pre-push hook ──────── scripts/pii-guard.py --diff     (re-scan every outgoing commit)
        │
 L3  private memory ─────── sealed store (Fernet / AES-256) · 0700/0600 · key-referenced
        │
 L4  CI ─────────────────── .github/workflows/privacy-guard.yml + ci-static-gate step
        │                    (tree, PR diff, PR title/body, private-path tracking check)
 L5  runtime redaction ──── cam_journal / sentinel.ts / activity_emit / sync-cline-session
        │                    strip PII before anything is journaled or distilled
 L6  Sentinel ───────────── plans touching private paths: DENY for egress / spend /
        │                    self_modify / motor.cline — no grant scope offered
 L7  agent rules + health ─ .clinerules, AGENTS.md, .cursor rules, MCP privacy_scan,
                             neuron.privacy_guard, piece.privacy in cam-system
```

Each layer is independently sufficient for the common case; together they cover
force-adds, `--no-verify`, branches pushed from other machines, PR descriptions,
runtime logs, and autonomous agents.

### L1 — `.gitignore`

`identity/aaron/local/`, `**/private-memory/`, media under `identity/aaron/`,
embeddings, `*.pem` / `*.key` / `*.p12`, `.env*`, `secrets/`, `credentials/`,
`data/runtime/journal/`, converse transcripts, vault attachments and `vault/08-People/*`.

### L2 — `pii-guard` (hooks)

```bash
bash scripts/install-git-hooks.sh          # once per clone (cloud-agent-install does it)
python3 scripts/pii-guard.py --staged      # what pre-commit runs
python3 scripts/pii-guard.py --diff origin/main
python3 scripts/pii-guard.py --all
python3 scripts/pii-guard.py --text -  < draft-pr-body.md
```

Rules live in `config/privacy/pii-guard.json` (block: email, phone, SSN, payment card
with Luhn, street / postal address, public IP, private key, API tokens, JWT, secret
assignment, home-directory path, operator timezone, physical description vocabulary,
enrollment-media filenames, government IDs, date of birth; warn: tailnet IPs). One
more rule, `personal_term`, is built at run time from the operator's protected terms
in private memory — it exists only on hosts that hold the store, and its pattern is
never written to disk or printed.
Path rules block private directories, media, key material, and images outside the
persona/asset folders — even when force-added. Output is **location + rule only**;
`--show-snippets` is local-only.

Escape hatch: a line containing `pii-guard: allow` is skipped. It is for false
positives in code, never for real personal data, and reviewers should question it.

### L3 — private memory

```bash
python3 scripts/private-memory.py doctor
python3 scripts/private-memory.py put identity.aaron.timezone --value "Region/City"
python3 scripts/private-memory.py get identity.aaron.timezone
python3 scripts/private-memory.py list          # keys and sizes only
python3 scripts/private-memory.py protect --value "…" --value "…"   # your own facts → blocked everywhere
python3 scripts/private-memory.py protected     # count only
```

- Store: `PRIVATE_MEMORY_HOME` / `CAM_PRIVATE_HOME` (default `identity/<handle>/local/private-memory/`; `~/.cam/private` recommended on Aaron's Mac)
- Key: `CAM_PRIVATE_KEY_FILE` (default `<store>/.key`, generated 0600). Back the key up in Aaron's password manager — records are unrecoverable without it.
- Cipher: Fernet when `cryptography` is installed, else `openssl enc -aes-256-cbc -pbkdf2`. Plaintext requires `CAM_PRIVATE_ALLOW_PLAINTEXT=1` and is reported by `doctor`.
- The metadata index never holds values. Working copies the runtime needs (`identity/aaron/local/VISUAL_PROFILE.md`, `enroll-index.json`) are 0600 inside the gitignored tree.

### L4 — CI

`privacy-guard` runs on every push and PR: full tree, PR diff, PR title + body, unit
tests, and a check that no private path is tracked. `scripts/ci-static-gate.py` runs
`pii-guard --all` first, so the existing gate fails before anything else.

### L5 — runtime redaction

`scripts/privacy.redact()` / `scrub_obj()` and the mirrored patterns in
`server/core/sentinel.ts` run on: intent journal payloads, live-activity reasons,
Cline session distillates. Keys named `timezone`, `phone`, `email`, `address`,
`embedding`, … are blanked regardless of content.

### L6 — Sentinel

`config/connectome/sentinel-policy.json → private_memory`: any motor plan whose paths
touch private memory is **denied** (not asked) for `egress`, `spend`, `self_modify`
classes and for `motor.cline`, `motor.jobs`, `motor.inkbox`, `motor.web_fetch`, …
Local read/write motors still work, so Cam can use the data without ever shipping it.
The privacy policy, guard scripts, hooks, `.gitignore`, `SECURITY.md` are guardrail
paths — a Cline/agent edit gets at most a one-time grant from Aaron.

### L7 — agents and health

- `.clinerules`, `AGENTS.md`, `.cursor/rules/cam-cline.mdc`, `loop-constraints.md`: never write personal information into tracked files or PR text; use private memory.
- MCP tool `privacy_scan` (read-only) lets any agent check text or paths before writing.
- `neuron.privacy_guard` in `system-health-scan.py` turns **critical** when a tracked file fails the guard or a private path is tracked; `piece.privacy` is in `cam-system` boot order and smoke checks.

---

## 3. Operating procedures

### Adding a new personal fact
1. `python3 scripts/private-memory.py put <domain>.<name> --value "…" --protect` (or `--file`, `--json`); facts with no runtime use: `private-memory.py protect --value "…"`
2. Reference it by key in tracked files; use a neutral placeholder such as `operator_local`
3. Runtime resolves via `private_memory.PrivateMemory().get(key)` or an env var Aaron exports on the host

### New machine / new workspace / new operator
1. `python3 scripts/privacy-init.py --operator <handle> --name <Name>` (hooks, gitignore, store, protected terms — idempotent)
2. Copy the private-memory store **out of band** (AirDrop / encrypted disk) — never through git, a PR, chat, or a cloud VM. Copy the key separately.
3. `python3 scripts/private-memory.py doctor`

### Another repository
`python3 scripts/privacy-kit.py export <repo> --operator <handle> --name <Name>`, then
`privacy-init.py` inside it — see [`PRIVACY_QUICKSTART.md`](PRIVACY_QUICKSTART.md).

### Cloud Agents and Cline sessions
- They run in VMs that must **not** hold private memory. The default store path is gitignored and empty there; `doctor` shows `record_count: 0`.
- If a task needs a personal fact, Aaron supplies it in the prompt and the agent stores it only in private memory on Aaron's host later — never in the repo.
- Every agent PR runs `privacy-guard`; the PR template's checklist is mandatory.

### Reviewing a PR
- `privacy-guard` green is required; do not merge on red.
- Question any `pii-guard: allow` pragma and any edit to guardrail paths.

---

## 4. History purge (one-time, Aaron-run)

Redacting HEAD leaves the old files reachable in history and in old PR refs.

```bash
# 1. FIRST recover the data into private memory (needs the old history)
python3 scripts/private-memory.py import-legacy
python3 scripts/private-memory.py list

# 2. Rewrite history (fresh clone recommended; dry-run without --execute)
pip install git-filter-repo
bash scripts/purge-git-history.sh --execute

# 3. Publish the rewrite — Aaron only
git push --force --all origin && git push --force --tags origin
```

Then **make the repository private** *or* contact GitHub Support to purge cached
views and unreachable objects (`refs/pull/*/head` are not rewritten by a force-push).
Re-clone every other checkout; never `git pull` an old clone into the new history.

---

## 5. Repository settings checklist (GitHub, Aaron only)

| Setting | Why |
|---|---|
| **Visibility → Private** (strongest single control) | removes public exposure of history, branches, PR text, forks |
| Code security → **Secret scanning + Push protection** | GitHub-side block for leaked credentials |
| Branch protection on `main`: require `privacy-guard` status check, require PR, no force-push except Aaron | CI cannot be skipped |
| Actions → workflow permissions **read-only**; require approval for fork PRs | no token abuse |
| Two-factor auth on the account; review authorized OAuth apps and deploy keys | account takeover is the biggest leak path |
| Dependabot security updates | supply-chain fixes |
| Review collaborators (currently only Aaron) and forks (currently none) | audit surface |

---

## 6. Threat model (what each layer stops)

| Threat | Stopped by |
|---|---|
| Accidental `git add` of a photo, WAV, embeddings, `.env` | L1, L2 path rules, L4 |
| Pasting a phone number / address / description into a doc or config | L2, L4 |
| `git add -f` or `--no-verify` | L2' pre-push, L4, `neuron.privacy_guard` |
| Push from a machine without hooks | L4 (CI on every push), branch protection |
| Cloud Agent or Cline writes personal data into a PR body | L4 PR-text scan, PR template, L7 rules, `privacy_scan` |
| Runtime logs / journals / distillates capture PII from a conversation | L5 redaction; converse transcripts are gitignored |
| Cam's own plan tries to email / post / commit private-memory content | L6 Sentinel deny; egress taint |
| Stolen laptop / disk image | L3 encryption at rest, 0600 key, key backed up separately |
| Old history on the public remote | §4 purge + private repo |
| Rule tampering by an agent | guardrail paths → one-time grant only; CI file is guardrail too |

### What this does *not* cover (and what does)
- Aaron reading a value aloud on a call, or screen-sharing `private-memory get` — human discipline.
- A compromised host with the key present — full-disk encryption + OS login hygiene.
- Third-party services Cam calls (Inkbox, MemoryBear, VoiceStudio) — their own policies; `switch.outbound` + Sentinel taint keep personal data from being sent automatically.

---

## 7. Incident response

1. **Stop**: `python3 scripts/connectome-route.py --sense sense.chat.aaron --kill` (pauses motors), do not push anything else.
2. **Scope**: `python3 scripts/pii-guard.py --all --show-snippets` locally; `git log -S"<fragment>" --all` to find every commit.
3. **Remove**: redact at HEAD, then `scripts/purge-git-history.sh --execute` and force-push (Aaron).
4. **Evict**: make private / GitHub Support purge; delete stale branches and forks; rotate any secret that leaked.
5. **Learn**: add a rule to `config/privacy/pii-guard.json` so the same class is blocked next time; record the lesson in `vault/03-Projects/` without the data itself.

References: [`SECURITY.md`](../SECURITY.md) · [`config/privacy/pii-guard.json`](../config/privacy/pii-guard.json) · [`docs/safety.md`](safety.md) · [`docs/MUSE_CAM_PATTERNS.md`](MUSE_CAM_PATTERNS.md)
