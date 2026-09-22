# Cam privacy charter

> Aaron's personal information and preferences exist inside Cam for exactly
> one purpose: to help Aaron. They are never released to any other person,
> agent, service, distillate or channel. Other people may have their own
> individual prompts and memory; memory is never shared, transmitted,
> revealed, compared or used across people. Secrecy of personal information
> is a moral obligation here, not a configuration default.

Authorized by Aaron, 2026-09-22. Machine-readable form:
[`config/privacy/charter.json`](../config/privacy/charter.json). Enforced by
[`scripts/cam_privacy.py`](../scripts/cam_privacy.py) (the kernel) and
checked by `python3 scripts/privacy-check.py` (part of `cam-system --smoke`)
and `python3 scripts/test_cam_privacy.py`.

## The four commitments

1. **Sole purpose.** Personal information and preferences are stored only to
   help the person they belong to. Nothing in this repository sells, syncs,
   trains on, or "anonymises and shares" them. There is no analytics sink.
2. **Nobody else, ever.** Not another person, not another agent's memory,
   not a mesh distillate, not a Slack channel, not a webhook. The only
   sanctioned external memory (MemoryBear) is keyed to Aaron's own account and
   is unreachable from any other principal.
3. **Individual people, individual memory.** Another person may use Cam with
   their own prompt and their own memory. Each person is a *principal* with a
   sealed root directory. No process serves two people; no tier merges,
   compares or embeds across people.
4. **Consent is explicit, narrow and Aaron's alone.** Sharing a class of
   personal information with a named recipient requires a consent entry
   Aaron writes at the CLI. Agents can read consent and never write it.
   Default answer is no.

## How it is built

### One process, one principal

`CAM_PRINCIPAL` (default `aaron`, the owner) names the person a process
serves. Every store goes through `cam_privacy.scoped_dir()`:

| store | owner | guest `<id>` |
|---|---|---|
| Instinct ledger / outbox / briefs | `data/instinct/` | `data/principals/<id>/instinct/` |
| swarm lineage | `data/swarm/` | `data/principals/<id>/swarm/` |
| Inkbox inbound drops | `data/inkbox/inbound/` | `data/principals/<id>/inkbox/inbound/` |
| counts-only distillates | `vault/10-Mesh-Distillates/…` | `data/principals/<id>/distill/` |
| vault briefs | `vault/06-Life-Ops/…` | `data/principals/<id>/instinct/vault-briefs/` |
| MemoryBear | Aaron's `end_user_id` | **refused** |
| workspaces registry, cline cache, Needs Attention, calendar sources | read | **not consulted** |

A guest's environment overrides (`INSTINCT_DATA_DIR`, `CAM_SWARM_DIR`,
`INKBOX_INBOUND_DIR`) are honoured only inside that guest's root; pointing a
guest at the owner's directory is refused by the kernel.

Every data directory is **sealed** to its principal at first touch
(`.principal`). A script that opens a directory sealed to someone else exits.
Directories are `chmod 700`, files `600`.

### Enrolling another person (Aaron only)

```
python3 scripts/cam_privacy.py --aaron principals add dana --label "Dana"
CAM_PRINCIPAL=dana python3 scripts/cam-mcp-server.py      # or --principal dana
```

This creates `data/principals/dana/` (sealed, 700) with `profile.json`, an
individual `prompt.md` from
[`config/privacy/guest-prompt-template.md`](../config/privacy/guest-prompt-template.md),
and empty `instinct/ swarm/ inkbox/inbound/ distill/`. The guest MCP process
exposes only `charter.principals.guest_tools`; everything that reaches the
owner's data or configuration is absent from `tools/list` and refused by
`tools/call`. An unenrolled id refuses to start.

Recommended host hardening: give each additional person their own OS user.
Because the owner's roots are `700`, that user cannot read Aaron's data even
by accident, and the seal/scoping checks become defence in depth rather
than the only wall.

### Classes and sinks

The kernel classifies text into `personal_info` (email, phone, street
address, national id, payment card, IBAN, date of birth, terms from the
owner's private vocabulary), `personal_preference` (preference statements,
health / finance / relationship / location context), `secret` (API keys,
bearer tokens, env assignments, private keys) and `operational` (counts,
ids, timestamps). Findings are always **class + count + location — never the
value**.

`charter.sinks` says what each destination may hold:

| sink | personal_info | personal_preference | secret | scope |
|---|---|---|---|---|
| local ledger / brief / outbox draft | allow | allow | deny | same principal |
| vault | allow | allow | deny | owner only |
| mesh distillate | **deny** | **deny** | deny | owner only |
| mesh note (cline cache) | redact | redact | deny | owner only |
| MCP response | allow | allow | deny | same principal |
| other principal | deny | deny | deny | never |
| network | deny | deny | deny | never |

`cam_privacy.assert_shareable(obj, sink)` is called before the write in
`instinct distill`, `cam_swarm distill` and MCP `mesh_put`. A distillate that
would carry a personal class is **not written** and the command exits
non-zero — the nightly loop surfaces it, the file stays clean.

Instinct drafts may carry personal context (they are read by their own
principal) but never a credential: `redact_secrets` runs on every draft.
`instinct outbox approve --to <recipient>` for a third party checks
`consent_allows(recipient, class)`; without consent the approved copy is
redacted and stamped `privacy: redacted for <recipient>`.

### Personal vocabulary

`identity/aaron/local/personal-vocabulary.txt` (git-ignored, one term per
line) lets Aaron name what pattern detectors cannot know — family names, the
street, an employer, nicknames. They are matched case-insensitively and
redacted as `[personal]`. The list itself never leaves the machine.

### Consent (Aaron only)

```
python3 scripts/cam_privacy.py --aaron consent grant dentist@example.com --classes personal_info --expires 2026-12-31T00:00:00Z
python3 scripts/cam_privacy.py consent check dentist@example.com
python3 scripts/cam_privacy.py --aaron consent revoke dentist@example.com
```

Records live in `identity/aaron/local/consent.json` (git-ignored, 600).
Grants are per recipient, per class, optionally expiring. There is no
wildcard recipient and no wildcard class.

### Tamper evidence

`python3 scripts/cam_privacy.py --aaron keygen` writes
`identity/aaron/local/ledger.key` (600); `CAM_LEDGER_HMAC_KEY` works too.
With a key present both ledgers are HMAC-sealed on every save and `instinct
doctor` / `cam_swarm doctor` report `HMAC seal mismatch` when a file was
edited outside the scripts. Without a key nothing changes except that the
doctors note the key is missing.

The swarm kill switch is now ledger-derived: deleting `data/swarm/KILL` no
longer re-arms spawning; only `cam_swarm.py --aaron resume` does, and
`doctor` reports a removed flag.

### Privilege

`disclose_personal` is in `privilege_catalog.aaron_only`. No spawn path can
grant it, the chief does not hold it, and both `cam_swarm doctor` and
`privacy-check` assert that.

## The Privacy Team

[`config/teams/privacy.json`](../config/teams/privacy.json) — lead
`privacy-officer`, members `redactor`, `boundary-auditor`, `memory-steward`,
`consent-keeper`, `qa`. No member holds `web_fetch` or any outbound
privilege: nothing the team touches can leave the machine. Prompts in
`config/roles/`. The team's tick is the `privacy_audit` action at the end of
the nightly `instinct-followups` loop (doctor + audit after the distills are
written) and `privacy-check` inside `cam-system --smoke`.

## Invariants (tested)

| id | rule | where |
|---|---|---|
| P1 | no personal class in any mesh distillate | `test_cam_privacy.DistillateGuardTests` |
| P2 | one process, one principal; owner roots unreachable from a guest | `PrincipalIsolationTests`, `test_mcp_guards.PrincipalGuards` |
| P3 | guest MCP exposes only the allowlist | `test_mcp_guards.PrincipalGuards` |
| P4 | MemoryBear and vault are owner-only | `PrincipalIsolationTests.test_memorybear_refuses_guest` |
| P5 | owner dirs 700 / files 600 | `HardeningTests` |
| P6 | HMAC-sealed ledgers, tamper reported | `SealTests` |
| P7 | no agent holds `disclose_personal` | `test_cam_swarm.test_p7_*` |
| P8 | mesh notes redacted; secrets refused everywhere | `test_mcp_guards.test_mesh_put_*` |
| P9 | private paths git-ignored and untracked | `privacy-check` |
| P10 | third-party drafts need consent or are redacted | `ConsentTests` |

## What this does not claim

- Anyone who can run commands as the owner's OS user is the owner. The OS
  user boundary is the real wall; the kernel makes accidental and
  cross-agent leaks impossible and deliberate tampering evident.
- Detectors are patterns plus Aaron's vocabulary. A novel identifier the
  patterns do not know (an unusual id format) passes until Aaron adds it to
  the vocabulary. Counts-only distillates make this moot for the mesh; it
  matters for mesh notes and third-party drafts, which is why those also go
  through Aaron's approval.
- nullclaw's own channels (iMessage, Slack, email inbox) are outside this
  repository. This charter governs everything Cam's scripts store or emit;
  the brain is expected to honour the same rule.
