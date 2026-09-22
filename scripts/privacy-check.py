#!/usr/bin/env python3
"""Confirm the privacy charter is wired everywhere it must be (offline).

Static: charter, team, roles, privileges (disclose_personal is Aaron-only),
kernel guards present in every script that stores or shares data, MCP guest
gate, loop action, git-ignore coverage of private paths, no tracked private
files, and the repository never carries the operator's identifying details
beyond the first-name label.
Runtime: `cam_privacy.py doctor` + `audit` (seals, modes, distillate scan).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_privacy as privacy  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []
    soft: list[str] = []

    # --- files ------------------------------------------------------------
    for rel in ("config/privacy/charter.json", "config/privacy/guest-prompt-template.md",
                "config/teams/privacy.json", "config/connectors/inbound-policy.json",
                "scripts/cam_privacy.py", "scripts/privacy-check.py", "scripts/inkbox-webhook-drop.py",
                "scripts/test_cam_privacy.py", "docs/PRIVACY_CHARTER.md"):
        if not (ROOT / rel).exists():
            errors.append(f"missing {rel}")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, indent=2))
        return 1

    charter = load(ROOT / "config/privacy/charter.json")
    team = load(ROOT / "config/teams/privacy.json")
    privs = load(ROOT / "config/swarm/privileges.json")

    # --- charter shape ----------------------------------------------------
    for sink in ("mesh_distillate", "mesh_note", "other_principal", "network", "outbox_draft", "vault"):
        if sink not in charter["sinks"]:
            errors.append(f"charter missing sink {sink}")
    for sink in ("mesh_distillate", "other_principal", "network"):
        pol = charter["sinks"].get(sink) or {}
        for cls in ("personal_info", "personal_preference", "secret"):
            if pol.get(cls) != "deny":
                errors.append(f"charter sink {sink} must deny {cls}")
    for sink, pol in charter["sinks"].items():
        if pol.get("secret") != "deny":
            errors.append(f"charter sink {sink} must deny secrets")
    if (charter["sinks"].get("vault") or {}).get("scope") != "owner_only":
        errors.append("vault must be owner-only")
    if "disclose_personal" not in privs["privilege_catalog"]["aaron_only"]:
        errors.append("privileges.aaron_only must include disclose_personal")
    for role, entry in privs["role_defaults"].items():
        if "disclose_personal" in entry["privileges"]:
            errors.append(f"role default {role} carries disclose_personal")
    if not charter["principals"].get("guest_tools"):
        errors.append("charter.principals.guest_tools empty")
    owner_only_tools = {"vault_search", "mesh_search", "mesh_put", "memorybear_read", "memorybear_write",
                        "list_workspaces", "choose_workspace", "ticket_list", "needs_attention", "calendar_sync",
                        "connectors_list", "privacy_audit", "instinct_workspaces", "loop_run"}
    leaked = owner_only_tools & set(charter["principals"]["guest_tools"])
    if leaked:
        errors.append(f"guest_tools must not include owner-reaching tools: {sorted(leaked)}")

    # --- team + roles -----------------------------------------------------
    members = {m["role"] for m in team.get("members") or []}
    for role in ("privacy-officer", "redactor", "boundary-auditor", "memory-steward", "consent-keeper"):
        if role not in members:
            errors.append(f"team.privacy missing member {role}")
        if not (ROOT / "config/roles" / f"{role}.md").exists():
            errors.append(f"missing role prompt {role}")
        entry = privs["role_defaults"].get(role)
        if not entry:
            errors.append(f"privileges.role_defaults missing {role}")
            continue
        if entry.get("team") != "team.privacy":
            errors.append(f"{role} must belong to team.privacy")
        for forbidden in ("web_fetch", "outbound_draft", "outbound_send", "careers_draft", "careers_submit"):
            if forbidden in entry["privileges"]:
                errors.append(f"{role} must not hold {forbidden} (nothing the privacy team touches leaves the machine)")
    centers = load(ROOT / "config/connectome/centers.json")
    if "team.privacy" not in (centers.get("teams") or []):
        errors.append("centers.teams missing team.privacy")
    prims = load(ROOT / "config/swarm/primitives.json")
    chans = next((p.get("channels") or [] for p in prims["primitives"] if p["id"] == "synapse.broadcast"), [])
    if "team.privacy" not in chans:
        errors.append("synapse.broadcast channels missing team.privacy")
    if "privacy-officer" not in text("config/roles.md"):
        errors.append("config/roles.md roster missing privacy roles")

    # --- kernel guards in every storing / sharing script ---------------------
    for rel, needles in (
        ("scripts/cam_swarm.py", ("privacy.scoped_dir", "privacy.enter", "privacy.seal_doc", "assert_shareable",
                                  "ledger_says_killed", "def gc(")),
        ("scripts/instinct.py", ("privacy.scoped_dir", "privacy.enter", "privacy.seal_doc", "assert_shareable",
                                 "redact_secrets", "consent_allows", "apply_source_update")),
        ("scripts/inkbox-inbound.py", ("privacy.scoped_dir", "sender_tier", "verify_drop", "require_signed")),
        ("scripts/inkbox-webhook-drop.py", ("O_EXCL", "verify_signature")),
        ("scripts/calendar-sync.py", ("PinnedRedirects", "host_is_private", "update_ref")),
        ("scripts/memorybear.py", ("require_owner_memory",)),
        ("scripts/cam-mcp-server.py", ("tool_visible", "guest_tool_allowlist", '"privacy_status"', '"privacy_redact"',
                                       'assert_shareable(note, "mesh_note")', "--principal")),
        ("scripts/loop-run.py", ("privacy_audit",)),
        ("scripts/cam-system.py", ("privacy-check",)),
    ):
        body = text(rel)
        for needle in needles:
            if needle not in body:
                errors.append(f"{rel} missing guard {needle}")
    mcp = text("scripts/cam-mcp-server.py")
    for banned in ("consent grant", "principals add", "\"privacy_consent_grant\"", "\"privacy_add_principal\""):
        if f'"name": "{banned}"' in mcp or banned.strip('"') in re.findall(r'"name": "([^"]+)"', mcp):
            errors.append(f"MCP must not expose Aaron-only privacy action {banned}")

    # --- loop + registries ---------------------------------------------------
    pats = load(ROOT / "config/loops/patterns.json")
    pat = next((p for p in pats.get("patterns") or [] if p.get("id") == "instinct-followups"), {})
    if "privacy_audit" not in (pat.get("actions") or []):
        errors.append("instinct-followups loop missing privacy_audit action")
    tools = load(ROOT / "config/tools/registry.json")
    tool_ids = {t.get("id") for t in tools.get("tools") or []}
    for tid in ("tool.privacy.kernel", "tool.privacy.check", "tool.inkbox.webhook_drop"):
        if tid not in tool_ids:
            errors.append(f"tools registry missing {tid}")
    reg = load(ROOT / "config/connectors/registry.json")
    if not any(c.get("id") == "privacy" for c in reg.get("connectors") or []):
        errors.append("connectors registry missing privacy entry")

    # --- git hygiene ----------------------------------------------------------
    gitignore = text(".gitignore")
    for needle in ("data/principals/", "identity/aaron/local/", "data/instinct/", "data/swarm/", "data/inkbox/"):
        if needle not in gitignore:
            errors.append(f".gitignore missing {needle}")
    tracked = privacy.git_tracked(["data/principals", "identity/aaron/local", "data/instinct", "data/swarm",
                                   "data/inkbox"])
    for t in tracked:
        errors.append(f"private path tracked by git: {t}")

    # --- the operator's identity stays a first-name label ----------------------
    # Tracked text files must not carry emails / phone numbers / cards / SSNs
    # (fixtures use example.com + 555 numbers, which the detectors ignore below).
    try:
        files = subprocess.run(["git", "ls-files", "--", "config", "docs", "scripts", "AGENTS.md", ".clinerules"],
                               cwd=str(ROOT), capture_output=True, text=True, timeout=30).stdout.split()
    except Exception:
        files = []
    allow = charter.get("tracked_file_allowlist") or {}
    ok_domains = [d.lower() for d in allow.get("email_domains") or []]
    ok_phone = allow.get("phone_contains") or ["555"]

    def email_ok(addr: str) -> bool:
        dom = addr.rsplit("@", 1)[-1].lower()
        for d in ok_domains:
            if d.startswith("*.") and (dom.endswith(d[1:]) or dom == d[2:]):
                return True
            if dom == d:
                return True
        return False

    leaks = []
    for rel in files:
        p = ROOT / rel
        if p.suffix not in (".md", ".json", ".py", ".txt", "") or not p.is_file():
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for f in privacy.classify(body):
            if f["detector"] not in ("email", "phone", "payment_card", "national_id", "iban"):
                continue
            if f["detector"] == "email" and all(email_ok(m) for m in privacy._EMAIL.findall(body)):
                continue
            if f["detector"] == "phone" and all(any(tok in m.group(0) for tok in ok_phone)
                                                 for m in privacy._PHONE.finditer(body)):
                continue
            leaks.append(f"{rel}: {f['detector']} x{f['count']}")
    for leak in leaks:
        errors.append(f"tracked file carries an identifier: {leak}")

    # --- runtime -----------------------------------------------------------------
    doc = privacy.doctor()
    for p in doc["problems"]:
        errors.append(f"privacy doctor: {p}")
    aud = privacy.audit()
    for f in aud["findings"]:
        (errors if f["severity"] == "high" else soft).append(f"privacy audit: {json.dumps(f, sort_keys=True)}")
    soft.extend(doc.get("notes") or [])

    report = {
        "ok": not errors,
        "errors": errors,
        "soft_warnings": soft,
        "principal": doc["principal"],
        "principals": [p["id"] for p in doc["principals"]],
        "hmac_key": doc["hmac_key"],
        "charter": "config/privacy/charter.json",
        "team": "team.privacy",
        "invariants": [i["id"] for i in charter["invariants"]],
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
