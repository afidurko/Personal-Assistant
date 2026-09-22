# Privacy quickstart — keep *your* personal information out of your repositories

This is the operator-agnostic guide to the personal-information safeguards in this
repository. It works for anyone: a solo developer, a team, or another personal
assistant project. Nothing in the stack knows who you are; the only two facts about
you that ever live in a tracked file are a short **handle** and a **display name**.

Everything else — your full name, address, employer, phone, timezone, family names,
device names, health or financial details, photos, voice, biometrics — stays in
**private memory**: an encrypted, permission-tight store outside git that the guard
reads to *block* those values wherever they appear.

```text
what you type ──► pre-commit hook ──► pre-push hook ──► CI on push / PR ──► PR text scan
                       │                                                 │
                 refuses commits carrying                         fails the build when
                 personal data / secrets                          anything slipped through
                       │
             private memory (encrypted, 0700/0600, never in git)
             holds the real values + your protected terms
```

---

## 1. Ten-minute setup (this repository)

```bash
# 1. one command: handle, display name, gitignore, hooks, sealed store, protected terms
python3 scripts/privacy-init.py --operator sam --name "Sam" \
    --protect "<your full legal name>" --protect "<your street address>" \
    --protect-file ~/private-facts.txt        # optional: one fact per line

# 2. any time later — add more facts (never printed, never written to git)
python3 scripts/private-memory.py protect --value "<employer>"          # employer
python3 scripts/private-memory.py protect --value "<your doctor's name>" # doctor
python3 scripts/private-memory.py protected                              # count only

# 3. store values the runtime needs, referenced by key, and protect them in one go
python3 scripts/private-memory.py put identity.sam.timezone --value "Region/City" --protect
python3 scripts/private-memory.py get identity.sam.timezone

# 4. what the hooks and CI enforce
python3 scripts/pii-guard.py --all
python3 scripts/private-memory.py doctor
```

`privacy-init` is idempotent — run it again after cloning on a new machine or when
you change your handle. The private-memory key (`<store>/.key`) is generated `0600`;
back it up in a password manager, records are unrecoverable without it.

### What "protect" does

`protect` seals a list of your own facts under the key `privacy.personal_terms`.
From then on:

- `pii-guard` blocks every commit, push, or scanned text that contains any of them
  (case-insensitive, whitespace-flexible, whole-word) and reports the rule
  `personal_term` **without printing the value**;
- every redaction path (`privacy.redact`, `privacy.scrub_obj`, journals,
  distillates, activity streams) replaces them with `[REDACTED:personal_term]`;
- the list itself never leaves the store — `protected` shows a count, `--reveal` is
  for your local terminal only.

CI runners have no store, so the protected-terms rule is enforced by the **local
hooks**; the pattern rules (emails, phones, addresses, IDs, cards, IPs, secrets,
home paths, timezones, descriptions, media refs, private paths) are enforced
everywhere.

---

## 2. Bring it to any other repository

```bash
# from this repository
python3 scripts/privacy-kit.py manifest
python3 scripts/privacy-kit.py export ~/src/my-project --operator sam --name Sam

# inside ~/src/my-project
python3 scripts/privacy-init.py --operator sam --name Sam --protect "<your full legal name>"
git add config/privacy scripts/privacy.py scripts/pii-guard.py scripts/private_memory.py \
        scripts/private-memory.py scripts/privacy-init.py scripts/privacy-kit.py \
        scripts/install-git-hooks.sh scripts/test_privacy.py .githooks .github \
        docs/PRIVACY_QUICKSTART.md docs/PRIVACY_SAFEGUARDS.md .gitignore
git commit -m "Add personal-information safeguards"
```

The kit is Python 3.10+ standard library plus `cryptography` *or* `openssl` for the
store. It ships: the policy (`config/privacy/pii-guard.json`), the guard, the store,
the init and kit scripts, the hooks, the GitHub Action, the PR template with its
privacy checklist, the unit tests (Cam-specific classes skip themselves), and these
docs. `privacy-kit.py diff <repo>` tells you when a copy has drifted.

Existing repositories: run `python3 scripts/pii-guard.py --all` first. Every finding
is a location + rule; move the value to private memory (`put`), reference it by key,
protect it, and re-run. To scrub history afterwards see `scripts/purge-git-history.sh`.

---

## 3. Tune the policy without leaking anything

`config/privacy/pii-guard.json` is public, so it holds **patterns**, never values.

| You want to … | Do this |
|---|---|
| Block a value that only you know (name, street, plate, school) | `private-memory.py protect --value "…"` — never edit the JSON |
| Rename the operator | `privacy-init.py --operator <handle> --name <Name>`; `{handle}` / `{display_name}` expand in every path and pattern |
| Keep a directory private | add it to `private_paths` (e.g. `notes/private/`) |
| Allow a documented false positive on one line | append `# pii-guard: allow` to that line (reviewers should question every use) |
| Skip a vendored tree | add it to `skip_paths` |
| Add a new pattern | add a rule `{id, severity, label, pattern, paths?, exclude?, allow?, validator?}`; run `scripts/test_privacy.py` |

Validators already stop the common false positives: Luhn for cards, RFC 5737 /
private ranges for IPs, `.example` / `example.com` / `.test` for mail, the fictional
`555` range for phones, and `/api/home/...` route segments for home paths.

---

## 4. Daily habits that make the layers redundant (in a good way)

- Put facts in private memory **first**, then write the code that references the key.
- Use placeholders in tracked files: `operator_local`, `<your-city>`, `Region/City`.
- Never commit with `--no-verify`; never use the pragma for a real value.
- Keep private memory off cloud VMs and CI; copy it between your own machines out of
  band (encrypted disk, AirDrop), with the key separately.
- Turn on GitHub secret scanning + push protection and require the `privacy-guard`
  check on your default branch.

Full policy, threat model, and incident response: [`PRIVACY_SAFEGUARDS.md`](PRIVACY_SAFEGUARDS.md).
