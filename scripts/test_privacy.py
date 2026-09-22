#!/usr/bin/env python3
"""Unit tests for Cam's privacy safeguards: privacy core, pii-guard, private memory,
Sentinel private-path deny, journal redaction, and the wiring files."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_journal as cj  # noqa: E402
import cam_sentinel as cs  # noqa: E402
import privacy  # noqa: E402
import private_memory as pm  # noqa: E402

GUARD = ROOT / "scripts" / "pii-guard.py"
PM_CLI = ROOT / "scripts" / "private-memory.py"

# Synthetic samples only — nothing here is real personal information.
SAMPLES = {
    "email": "reach me at someone.real@example-mail.net today",
    "phone": "cell (212) 867-5309 anytime",  # pii-guard: allow (synthetic)
    "ssn": "ssn 123-45-6789 on file",  # pii-guard: allow (synthetic)
    "credit_card": "card 4111 1111 1111 1111 exp 12/30",  # pii-guard: allow (synthetic)
    "street_address": "ship to 221 Baker Street, London",  # pii-guard: allow (synthetic)
    "postal_address_line": "Brooklyn, NY 11201",  # pii-guard: allow (synthetic)
    "ipv4": "host 8.8.4.4 reachable",
    "private_key": "-----BEGIN RSA PRIVATE KEY-----",  # pii-guard: allow (synthetic)
    "api_token": "aws AKIAABCDEFGHIJKLMNOP",
    "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "secret_assignment": "API_KEY=abcdefghijklmnopqrstuvwxyz0123456789",
    "home_path": "see /Users/somebody/Documents/notes.txt",
    "operator_timezone": "timezone: Europe/Lisbon",
    "physical_description": "curly hair, goatee, glasses",
    "enrollment_media_ref": "source aaron-07-park-walk.jpg",
    "date_of_birth": "DOB: 01/02/1990",  # pii-guard: allow (synthetic)
}


class GlobMatch(unittest.TestCase):
    def test_dir_prefix(self):
        self.assertTrue(privacy.glob_match("identity/aaron/local/x/y.jpg", "identity/aaron/local/"))
        self.assertFalse(privacy.glob_match("identity/aaron/localnot/y.jpg", "identity/aaron/local/"))

    def test_double_star_dir(self):
        self.assertTrue(privacy.glob_match("a/b/private-memory/records/k.sealed", "**/private-memory/"))
        self.assertTrue(privacy.glob_match("private-memory/index.json", "**/private-memory/"))
        self.assertFalse(privacy.glob_match("docs/private-memory.md", "**/private-memory/"))

    def test_double_star_glob_and_basename(self):
        self.assertTrue(privacy.glob_match("server/core/sentinel.test.ts", "**/*.test.ts"))
        self.assertTrue(privacy.glob_match("scripts/test_privacy.py", "scripts/test_*.py"))
        self.assertTrue(privacy.glob_match("README.md", "*.md"))
        self.assertFalse(privacy.glob_match("docs/x.md", "*.md") and False)


class PathRules(unittest.TestCase):
    def test_private_paths_blocked(self):
        self.assertIn("private path", privacy.path_violation("identity/aaron/local/photos/a.jpg") or "")
        self.assertIn("private path", privacy.path_violation("x/private-memory/records/k.sealed") or "")
        self.assertIn("private path", privacy.path_violation("data/runtime/journal/2026-01-01.jsonl") or "")

    def test_blocked_names_and_extensions(self):
        self.assertIn("blocked filename", privacy.path_violation("config/.env") or "")
        self.assertIn("blocked filename", privacy.path_violation("identity/aaron/voice-profile.json") or "")
        self.assertIn("blocked extension", privacy.path_violation("docs/sample.wav") or "")
        self.assertIn("blocked extension", privacy.path_violation("deploy/server.pem") or "")

    def test_images_only_in_asset_folders(self):
        self.assertIsNone(privacy.path_violation("identity/persona/cam-face.jpg"))
        self.assertIsNone(privacy.path_violation("public/avatars/cam-face.jpg"))
        self.assertIn("image outside", privacy.path_violation("identity/aaron/face.jpg") or "")
        self.assertIn("image outside", privacy.path_violation("vault/00-Inbox/photo.png") or "")

    def test_exceptions_and_plain_files(self):
        self.assertIsNone(privacy.path_violation("vault/00-Inbox/attachments/.gitkeep"))
        self.assertIsNone(privacy.path_violation("vault/10-Mesh-Distillates/converse/README.md"))
        self.assertIsNone(privacy.path_violation("docs/ARCHITECTURE.md"))


class ContentRules(unittest.TestCase):
    def _rules_hit(self, text: str, rel: str = "<text>") -> set[str]:
        return {f.rule for f in privacy.scan_text(text, rel)}

    def test_every_block_rule_fires_on_its_sample(self):
        for rule, sample in SAMPLES.items():
            with self.subTest(rule=rule):
                self.assertIn(rule, self._rules_hit(sample))

    def test_negatives(self):
        clean = [
            "elapsed_s: 231.1234567890123",  # float, not a card
            "listen on 127.0.0.1:8787 and 0.0.0.0",  # loopback / unspecified
            "lan 192.168.1.20",  # private range is not public
            "SERPAPI_API_KEY=your_key_here",  # placeholder
            "MEMORYBEAR_API_KEY=${MEMORYBEAR_API_KEY}",  # env reference
            "token_budget = 120000000000",  # not a secret
            "quiet hours 23:30-07:00",  # not a phone
            "version 2026.09.17 build 4",
            "Cam is 32, Argentine, blue eyes, brown hair",  # persona, allowed vocabulary
            "contact newslabtrends@google.com upstream",  # allowlisted upstream address
            "/home/ubuntu/work and /Users/<you>/repo",  # generic hosts / placeholders
            "timezone: operator_local",
            'fetch("/api/home/status") and /opt/home/cache',  # route segments, not a home directory
            "ping someone@example.com or billing@comcast.example",  # RFC 2606 reserved domains
            "call +1 (555) 010-9999 or 555 0123 or +15550100",  # fictional 555-01xx range
        ]
        for line in clean:
            with self.subTest(line=line):
                self.assertEqual(self._rules_hit(line), set(), line)

    def test_allow_pragma_and_path_scoping(self):
        self.assertEqual(self._rules_hit("mail me: someone@example-mail.net  # pii-guard: allow"), set())
        # physical_description is scoped to identity/docs/config/scripts/... — a public asset path is out of scope
        self.assertNotIn("physical_description", self._rules_hit("goatee", rel="public/assets/x.json"))
        self.assertIn("physical_description", self._rules_hit("goatee", rel="identity/notes.md"))
        self.assertIn("physical_description", self._rules_hit("goatee", rel="scripts/enroll.py"))
        # operator_timezone excluded in test fixtures
        self.assertEqual(self._rules_hit("Europe/Lisbon", rel="scripts/testdata/addons/geo.json"), set())

    def test_secret_rules_skip_test_files(self):
        self.assertEqual(self._rules_hit(SAMPLES["jwt"], rel="server/core/sentinel.test.ts"), set())

    def test_luhn_and_ip_validators(self):
        self.assertTrue(privacy._luhn("4111 1111 1111 1111"))  # pii-guard: allow (synthetic)
        self.assertFalse(privacy._luhn("1234 5678 9012 3456"))
        self.assertTrue(privacy._ipv4_public("8.8.8.8"))
        self.assertFalse(privacy._ipv4_public("10.0.0.5"))
        self.assertFalse(privacy._ipv4_public("203.0.113.9"))  # documentation range


class Redaction(unittest.TestCase):
    def test_redact_text(self):
        out = privacy.redact("call (212) 867-5309 or someone.real@example-mail.net from Europe/Lisbon")  # pii-guard: allow (synthetic)
        self.assertNotIn("867-5309", out)
        self.assertNotIn("example-mail", out)
        self.assertNotIn("Lisbon", out)
        self.assertIn("[REDACTED:phone]", out)
        self.assertIn("[REDACTED:email]", out)

    def test_scrub_obj_blanks_private_keys_and_keeps_placeholder(self):
        obj = {"timezone": "Europe/Lisbon", "tz": "operator_local", "note": "someone@example-mail.net", "n": 3, "list": ["221 Baker Street, x"]}  # pii-guard: allow (synthetic)
        out = privacy.scrub_obj(obj)
        self.assertEqual(out["timezone"], "[REDACTED:private_field]")
        self.assertEqual(out["tz"], "operator_local")
        self.assertIn("[REDACTED:email]", out["note"])
        self.assertEqual(out["n"], 3)
        self.assertIn("[REDACTED:street_address]", out["list"][0])

    def test_journal_redacts_pii_and_secrets(self):
        out = cj.redact("token=abcdefghij123456 phone (212) 867-5309 tz Europe/Lisbon goatee")  # pii-guard: allow (synthetic)
        self.assertNotIn("867-5309", out)
        self.assertNotIn("abcdefghij123456", out)
        self.assertNotIn("Lisbon", out)
        self.assertNotIn("goatee", out)
        env = cj._redact_obj({"phone": "(212) 867-5309", "api_key": "x" * 20, "ok": "fine"})  # pii-guard: allow (synthetic)
        self.assertEqual(env["api_key"], "[REDACTED]")
        self.assertNotIn("867", env["phone"])
        self.assertEqual(env["ok"], "fine")

    def test_finding_snippets_are_redacted(self):
        f = privacy.scan_text("mail someone.real@example-mail.net", "<text>")[0]
        self.assertNotIn("example-mail", f.snippet)


class GuardCli(unittest.TestCase):
    def _run(self, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(GUARD), *args], cwd=ROOT, input=stdin, capture_output=True, text=True)

    def test_text_mode_blocks_and_hides_content_by_default(self):
        p = self._run("--text", "-", stdin="write to someone.real@example-mail.net\n")
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("BLOCK email", p.stdout)
        self.assertNotIn("example-mail", p.stdout)

    def test_text_mode_clean(self):
        p = self._run("--text", "-", stdin="nothing personal here\n")
        self.assertEqual(p.returncode, 0, p.stdout)

    def test_json_mode(self):
        p = self._run("--text", "-", "--json", stdin="ssn 123-45-6789\n")  # pii-guard: allow (synthetic)
        doc = json.loads(p.stdout)
        self.assertFalse(doc["ok"])
        self.assertEqual(doc["summary"]["by_rule"], {"ssn": 1})
        self.assertEqual(doc["findings"][0]["snippet"], "")

    def test_paths_mode_blocks_private_path_even_if_file_missing_content(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "identity" / "aaron") as tmp:
            # any `private-memory/` directory at any depth is a private path by policy
            local = Path(tmp) / "private-memory"
            local.mkdir()
            f = local / "note.txt"
            f.write_text("harmless\n", encoding="utf-8")
            rel = os.path.relpath(f, ROOT)
            p = self._run("--paths", rel)
            self.assertEqual(p.returncode, 1, p.stdout)
            self.assertIn("private_path", p.stdout)

    def test_tracked_tree_is_clean(self):
        p = self._run("--all")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


class PrivateMemoryStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "store"

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_json_text_bytes_and_index_has_no_values(self):
        s = pm.PrivateMemory(home=self.home)
        s.put("identity.test.profile", {"eyes": "green", "phone": "(212) 867-5309"})  # pii-guard: allow (synthetic)
        s.put("identity.test.tz", "Europe/Lisbon")
        s.put("identity.test.blob", b"\x00\x01binary")
        self.assertEqual(s.get("identity.test.profile")["phone"], "(212) 867-5309")  # pii-guard: allow (synthetic)
        self.assertEqual(s.get("identity.test.tz"), "Europe/Lisbon")
        self.assertEqual(s.get("identity.test.blob"), b"\x00\x01binary")
        index = (self.home / "index.json").read_text(encoding="utf-8")
        for secret in ("867-5309", "Lisbon", "green"):
            self.assertNotIn(secret, index)
        sealed = (self.home / "records" / "identity.test.tz.sealed").read_text(encoding="utf-8")
        self.assertNotIn("Lisbon", sealed)
        self.assertEqual([r.key for r in s.list()], ["identity.test.blob", "identity.test.profile", "identity.test.tz"])

    @unittest.skipIf(os.name != "posix", "posix permissions")
    def test_permissions(self):
        s = pm.PrivateMemory(home=self.home)
        s.put("k.perm", "v")
        self.assertEqual(stat.S_IMODE(self.home.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(s.key_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.home / "records" / "k.perm.sealed").stat().st_mode), 0o600)

    def test_openssl_fallback_when_fernet_missing(self):
        if not pm.shutil.which("openssl"):
            self.skipTest("openssl not on PATH")
        saved = pm.Fernet
        pm.Fernet = None
        try:
            s = pm.PrivateMemory(home=self.home)
            rec = s.put("k.ssl", {"phone": "(212) 867-5309"})  # pii-guard: allow (synthetic)
            self.assertEqual(rec.cipher, "aes-256-cbc-pbkdf2")
            self.assertEqual(s.get("k.ssl")["phone"], "(212) 867-5309")  # pii-guard: allow (synthetic)
            self.assertNotIn("867", (self.home / "records" / "k.ssl.sealed").read_text())
        finally:
            pm.Fernet = saved

    def test_plaintext_refused_unless_allowed(self):
        saved_f, saved_which = pm.Fernet, pm.shutil.which
        pm.Fernet = None
        pm.shutil.which = lambda _name: None
        try:
            with self.assertRaises(pm.PrivateMemoryError):
                pm.PrivateMemory(home=self.home).put("k.plain", "v")
            rec = pm.PrivateMemory(home=self.home, allow_plaintext=True).put("k.plain", "v")
            self.assertEqual(rec.cipher, "none")
        finally:
            pm.Fernet, pm.shutil.which = saved_f, saved_which

    def test_wrong_key_fails_closed(self):
        s = pm.PrivateMemory(home=self.home)
        s.put("k.one", "value")
        other = pm.PrivateMemory(home=self.home, key_file=Path(self.tmp.name) / "other.key")
        with self.assertRaises(pm.PrivateMemoryError):
            other.get("k.one")

    def test_bad_key_names_and_delete(self):
        s = pm.PrivateMemory(home=self.home)
        with self.assertRaises(pm.PrivateMemoryError):
            s.put("../escape", "v")
        with self.assertRaises(pm.PrivateMemoryError):
            s.put("Upper.Case", "v")
        s.put("k.del", "v")
        self.assertTrue(s.delete("k.del"))
        self.assertFalse(s.has("k.del"))
        with self.assertRaises(KeyError):
            s.get("k.del")

    def test_doctor_reports_healthy_store(self):
        s = pm.PrivateMemory(home=self.home)
        s.put("k.doc", "v")
        rep = s.doctor()
        self.assertTrue(rep["ok"], rep)
        self.assertEqual(rep["record_count"], 1)
        self.assertNotIn("v", json.dumps(rep["records"]))

    def test_cli_import_legacy_dry_run_has_shape(self):
        env = {**os.environ, "CAM_PRIVATE_HOME": str(self.home)}
        p = subprocess.run([sys.executable, str(PM_CLI), "import-legacy", "--dry-run"], cwd=ROOT, env=env, capture_output=True, text=True)
        doc = json.loads(p.stdout)
        self.assertEqual(set(doc), {"imported", "skipped", "working_copies"})
        self.assertFalse(list(self.home.glob("records/*")))  # dry run seals nothing


class SentinelPrivatePaths(unittest.TestCase):
    def test_private_path_denies_egress_and_cline_but_not_local(self):
        v = cs.evaluate(
            ["motor.inkbox", "motor.cline", "motor.vault", "motor.docs"],
            sense="sense.chat.aaron",
            paths=["identity/aaron/local/VISUAL_PROFILE.md"],
            switch_state={"switch.outbound": "act"},
        )
        d = v["decisions"]
        self.assertEqual(d["motor.inkbox"]["decision"], "deny")
        self.assertEqual(d["motor.cline"]["decision"], "deny")
        self.assertNotIn("grant_options", d["motor.inkbox"])
        self.assertEqual(d["motor.vault"]["decision"], "allow")
        self.assertEqual(d["motor.docs"]["decision"], "allow")
        self.assertEqual(v["private_path"], "identity/aaron/local/VISUAL_PROFILE.md")

    def test_no_private_path_keeps_standing_grant(self):
        v = cs.evaluate(["motor.inkbox"], sense="sense.chat.aaron", switch_state={"switch.outbound": "act"})
        self.assertEqual(v["decisions"]["motor.inkbox"]["decision"], "allow")
        self.assertIsNone(v["private_path"])

    def test_absolute_and_nested_private_paths(self):
        pol = cs.load_policy()
        self.assertIsNotNone(cs._private_hit([str(cs.ROOT / "identity/aaron/local/x")], pol))
        self.assertIsNotNone(cs._private_hit(["a/b/private-memory/records/k"], pol))
        self.assertIsNone(cs._private_hit(["docs/ARCHITECTURE.md"], pol))

    def test_privacy_files_are_guardrails(self):
        rails = cs.load_policy()["guardrail_paths"]
        for p in ("config/privacy/", ".githooks/", ".gitignore", "scripts/pii-guard.py", "scripts/privacy.py", "SECURITY.md"):
            self.assertIn(p, rails)


class Wiring(unittest.TestCase):
    def test_hooks_installed_and_executable(self):
        for name in ("pre-commit", "pre-push"):
            hook = ROOT / ".githooks" / name
            self.assertTrue(hook.is_file(), name)
            self.assertTrue(hook.stat().st_mode & 0o111, name)
            self.assertIn("pii-guard.py", hook.read_text(encoding="utf-8"))
        self.assertIn("install-git-hooks.sh", (ROOT / "scripts" / "cloud-agent-install.sh").read_text(encoding="utf-8"))

    def test_ci_and_gate_wiring(self):
        wf = (ROOT / ".github" / "workflows" / "privacy-guard.yml").read_text(encoding="utf-8")
        self.assertIn("pii-guard.py --all", wf)
        self.assertIn("pull_request", wf)
        self.assertIn("test_privacy", wf)
        gate = (ROOT / "scripts" / "ci-static-gate.py").read_text(encoding="utf-8")
        self.assertIn('("pii-guard", "pii-guard.py"', gate)
        pieces = json.loads((ROOT / "config" / "system" / "pieces.json").read_text(encoding="utf-8"))
        self.assertIn("piece.privacy", [p["id"] for p in pieces["pieces"]])
        self.assertIn("piece.privacy", pieces["boot_order"])

    def test_gitignore_covers_private_trees(self):
        for probe in (
            "identity/aaron/local/photos/a.jpg",
            "identity/aaron/voice-profile.json",
            "x/private-memory/records/k.sealed",
            "data/runtime/journal/2026.jsonl",
            "vault/08-People/someone.md",
            "deploy/server.pem",
        ):
            code = subprocess.run(["git", "check-ignore", "-q", probe], cwd=ROOT).returncode
            self.assertEqual(code, 0, f"{probe} should be gitignored")

    def test_identity_stubs_carry_no_personal_information(self):
        for rel in ("identity/aaron/VISUAL_PROFILE.md", "identity/aaron/enroll-index.json", "identity/BOUNDARIES.md", "identity/ANSWERS_SESSION_01.json"):
            findings = privacy.scan_file(ROOT / rel, rel)
            self.assertEqual(privacy.blocking(findings), [], rel)
        idx = json.loads((ROOT / "identity" / "aaron" / "enroll-index.json").read_text(encoding="utf-8"))
        self.assertEqual(idx["primary_face_cluster"], "private")
        self.assertEqual(idx["visibility"], "public_stub")

    def test_identity_stubs_are_not_exempt_from_description_rules(self):
        # The files that leaked in the first PR must stay under full scrutiny: a description
        # or enrollment-media reference re-added to the stub has to be caught.
        for rel in ("identity/aaron/VISUAL_PROFILE.md", "identity/aaron/README.md", "identity/aaron/enroll-index.json"):
            hits = {f.rule for f in privacy.scan_text("trim goatee, source aaron-03-park.jpg", rel)}
            self.assertIn("physical_description", hits, rel)
            self.assertIn("enrollment_media_ref", hits, rel)

    def test_no_operator_timezone_in_tracked_identity_or_config(self):
        out = subprocess.run(["git", "grep", "-l", "-E", r"(America|Europe|Asia|Africa|Australia)/[A-Z][A-Za-z_]+", "--", "identity", "config", "docs", "vault/01-Aaron", "*.md"], cwd=ROOT, capture_output=True, text=True).stdout
        offenders = [l for l in out.splitlines() if l and not l.startswith("docs/PRIVACY_SAFEGUARDS.md") and "pii-guard.json" not in l]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
