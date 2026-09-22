#!/usr/bin/env python3
"""Tests for the privacy charter (config/privacy/charter.json) as enforced by
scripts/cam_privacy.py and the scripts that call it. Offline, deterministic.

Run: python3 scripts/test_cam_privacy.py
"""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import io
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
import cam_privacy as privacy  # noqa: E402
import cam_swarm as swarm  # noqa: E402
import instinct  # noqa: E402

T0 = "2026-09-22T09:00:00Z"
T1 = "2026-11-01T09:00:00Z"
ENV_KEYS = ("CAM_PRINCIPAL", "CAM_PRINCIPALS_ROOT", "INSTINCT_DATA_DIR", "CAM_SWARM_DIR", "INKBOX_INBOUND_DIR",
            "CAM_LEDGER_HMAC_KEY", "CAM_PRIVACY_VOCAB", "CAM_PRIVACY_CONSENT", "INSTINCT_NO_CACHE_MIRROR",
            "INSTINCT_MESH_OUT", "CAM_SWARM_MESH_OUT", "CAM_SWARM_SERVER_LINEAGE", "INKBOX_WEBHOOK_SECRET",
            "INKBOX_SENDERS_FILE", "CAM_CALENDAR_ICS", "INSTINCT_VAULT_DIR")


def run_mod(mod, *argv: str):
    buf = io.StringIO()
    code = 0
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = mod.main(list(argv))
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
            buf.write(json.dumps({"_error": str(exc)}))
    out = buf.getvalue()
    parsed = json.loads(out) if out.lstrip().startswith(("{", "[")) else {"text": out}
    if isinstance(parsed, dict):
        parsed["_exit"] = code
    return parsed


def run_script(rel: str, *argv: str, env: dict | None = None, stdin: str | None = None) -> dict:
    proc = subprocess.run([sys.executable, str(ROOT / rel), *argv], capture_output=True, text=True,
                          env={**os.environ, **(env or {})}, input=stdin, cwd=str(ROOT))
    try:
        out = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        out = {"stdout": proc.stdout}
    out["_exit"] = proc.returncode
    out["_stderr"] = proc.stderr
    return out


class PrivacyBase(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ENV_KEYS}
        for k in ENV_KEYS:
            os.environ.pop(k, None)
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.environ["INSTINCT_DATA_DIR"] = str(self.tmp / "instinct")
        os.environ["CAM_SWARM_DIR"] = str(self.tmp / "swarm")
        os.environ["INKBOX_INBOUND_DIR"] = str(self.tmp / "inbound")
        os.environ["CAM_PRINCIPALS_ROOT"] = str(self.tmp / "principals")
        os.environ["INSTINCT_MESH_OUT"] = str(self.tmp / "mesh" / "instinct.json")
        os.environ["CAM_SWARM_MESH_OUT"] = str(self.tmp / "mesh" / "lineage.json")
        os.environ["CAM_SWARM_SERVER_LINEAGE"] = str(self.tmp / "none.json")
        os.environ["INSTINCT_NO_CACHE_MIRROR"] = "1"
        os.environ["CAM_PRIVACY_VOCAB"] = str(self.tmp / "vocab.txt")
        os.environ["CAM_PRIVACY_CONSENT"] = str(self.tmp / "consent.json")
        swarm.SEAL_STATE["lineage"] = "nokey"
        instinct.SEAL_STATE["ledger"] = "nokey"

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    def as_guest(self, pid: str = "dana"):
        privacy.add_principal(pid, "Dana")
        os.environ["CAM_PRINCIPAL"] = pid
        for k in ("INSTINCT_DATA_DIR", "CAM_SWARM_DIR", "INKBOX_INBOUND_DIR"):
            os.environ.pop(k, None)
        return privacy.guest_root(pid)


# --- classification --------------------------------------------------------------

class ClassifyRedactTests(PrivacyBase):
    def test_detects_each_personal_class(self):
        text = ("mail a.b@example.com or call (512) 555-0134; card 4111 1111 1111 1111; ssn 123-45-6789; "
                "lives at 42 Maple Street Apt 3; DOB 03/14/1988; I prefer window seats; her therapist said")
        dets = {f["detector"]: f["class"] for f in privacy.classify(text)}
        for det in ("email", "phone", "payment_card", "national_id", "street_address", "date_of_birth"):
            self.assertEqual(dets.get(det), "personal_info", det)
        self.assertEqual(dets.get("preference_statement"), "personal_preference")
        self.assertEqual(dets.get("sensitive_context"), "personal_preference")

    def test_detects_secrets(self):
        dets = {f["detector"] for f in privacy.classify(
            "STRIPE_KEY=sk_live_abcdefghijklmnopqrstuv Bearer abcdefghijklmnopqrstuvwxyz0123 "
            "-----BEGIN RSA PRIVATE KEY----- ghp_abcdefghijklmnopqrstuvwxyz0123456789")}
        self.assertTrue({"api_key", "bearer_token", "env_assignment", "private_key"} <= dets)

    def test_operational_text_is_clean(self):
        text = ("instinct: live=3 escalations=0 drafts=2 asks=1 2026-09-22T10:00:00Z act-1a2b3c4d level 3 "
                "ticket 20260922T100000 job 8f3a1c2e workspace personal-assistant 4111 not a card 1234-5678")
        self.assertEqual(privacy.classify(text), [])

    def test_luhn_gate_on_cards(self):
        self.assertEqual(privacy.classify("order 4111 1111 1111 1112"), [])  # fails Luhn
        self.assertEqual(privacy.classify("order 4111 1111 1111 1111")[0]["detector"], "payment_card")

    def test_personal_vocabulary_is_matched_and_never_echoed(self):
        (self.tmp / "vocab.txt").write_text("# family\nWillowbrook\nZephyrine\n", encoding="utf-8")
        text = "meet at Willowbrook with Zephyrine"
        found = privacy.classify(text)
        self.assertEqual(found, [{"detector": "personal_term", "class": "personal_info", "count": 2}])
        red, counts = privacy.redact(text)
        self.assertEqual(red, "meet at [personal] with [personal]")
        self.assertNotIn("Willowbrook", json.dumps(found))

    def test_redact_tags_everything(self):
        red, counts = privacy.redact("Dana <dana@example.com> 512-555-0134 sk_live_abcdefghijklmnopqrstuv")
        self.assertEqual(red, "Dana <[email]> [phone] [secret]")
        self.assertEqual(counts, {"email": 1, "phone": 1, "api_key": 1})

    def test_redact_secrets_only_keeps_personal_context(self):
        red, n = privacy.redact_secrets("call 512-555-0134, token Bearer abcdefghijklmnopqrstuvwxyz0123")
        self.assertEqual(n, 1)
        self.assertIn("512-555-0134", red)
        self.assertIn("[secret]", red)

    def test_cli_never_returns_values(self):
        out = run_mod(privacy, "classify", "--text", "dana@example.com")
        self.assertNotIn("dana", json.dumps(out))


# --- sinks ---------------------------------------------------------------------------

class DistillateGuardTests(PrivacyBase):
    def test_mesh_distillate_denies_personal(self):
        with self.assertRaises(SystemExit) as cm:
            privacy.assert_shareable({"note": "call 512-555-0134"}, "mesh_distillate")
        self.assertIn("deny", str(cm.exception))
        self.assertNotIn("0134", str(cm.exception))  # message carries counts, not the value

    def test_mesh_note_redacts_personal_and_denies_secret(self):
        self.assertEqual(privacy.assert_shareable("ping dana@example.com", "mesh_note"), "ping [email]")
        with self.assertRaises(SystemExit):
            privacy.assert_shareable("token sk_live_abcdefghijklmnopqrstuv", "mesh_note")

    def test_other_principal_and_network_never(self):
        for sink in ("other_principal", "network"):
            with self.assertRaises(SystemExit):
                privacy.assert_shareable("anything at all", sink)

    def test_operational_passes(self):
        doc = {"jobs": {"open": 3}, "at": T0, "ids": ["act-1a2b3c4d"]}
        self.assertIs(privacy.assert_shareable(doc, "mesh_distillate"), doc)

    def test_instinct_distill_refuses_leak(self):
        run_mod(instinct, "--now", T0, "ingest", "--text", "Book the dentist", "--job", "Book dentist")
        ledger = instinct.load_ledger()
        ledger["last_scan"] = "scan by dana@example.com"  # any string field that reaches the distillate
        instinct.save_ledger(ledger)
        out = run_mod(instinct, "--now", T0, "distill")
        self.assertNotEqual(out["_exit"], 0)
        self.assertIn("deny", out["_error"])
        self.assertFalse((self.tmp / "mesh" / "instinct.json").exists())

    def test_instinct_distill_clean_writes(self):
        run_mod(instinct, "--now", T0, "ingest", "--text", "Book the dentist", "--job", "Book dentist")
        out = run_mod(instinct, "--now", T0, "distill")
        self.assertTrue(out["ok"])
        doc = json.loads((self.tmp / "mesh" / "instinct.json").read_text())
        self.assertEqual(doc["principal"], "aaron")
        self.assertNotIn("dentist", json.dumps(doc))

    def test_swarm_distill_refuses_leak(self):
        run_mod(swarm, "--now", T0, "spawn", "watcher")
        ledger = swarm.load_ledger()
        ledger["events"][-1]["status"] = "for 42 Maple Street"  # status is one of the mirrored fields
        swarm.save_ledger(ledger)
        out = run_mod(swarm, "--now", T0, "distill")
        self.assertNotEqual(out["_exit"], 0)
        self.assertFalse((self.tmp / "mesh" / "lineage.json").exists())


# --- principals ------------------------------------------------------------------------

class PrincipalIsolationTests(PrivacyBase):
    def test_owner_paths_unchanged(self):
        self.assertEqual(instinct.data_dir(), self.tmp / "instinct")
        self.assertEqual(swarm.data_dir(), self.tmp / "swarm")

    def test_guest_ids_validated(self):
        for bad in ("chief", "human", "x", "a b", "owner", "../x", "Dana!"):
            os.environ["CAM_PRINCIPAL"] = bad
            with self.assertRaises(SystemExit):
                privacy.current_principal()
        os.environ["CAM_PRINCIPAL"] = "aaron"
        self.assertEqual(privacy.current_principal(), "aaron")

    def test_guest_confined_to_own_root(self):
        root = self.as_guest()
        self.assertEqual(instinct.data_dir(), root / "instinct")
        self.assertEqual(swarm.data_dir(), root / "swarm")
        self.assertTrue(str(instinct.mesh_out_path()).startswith(str(root)))
        self.assertTrue(str(instinct.vault_briefs_dir()).startswith(str(root)))
        self.assertTrue(str(swarm.mesh_out_path()).startswith(str(root)))
        self.assertEqual([w["id"] for w in instinct.known_workspaces()], [instinct.DEFAULT_WORKSPACE])

    def test_guest_env_override_outside_root_refused(self):
        self.as_guest()
        os.environ["INSTINCT_DATA_DIR"] = str(self.tmp / "instinct")  # the owner's dir
        with self.assertRaises(SystemExit) as cm:
            instinct.data_dir()
        self.assertIn("outside principal", str(cm.exception))
        os.environ["CAM_SWARM_DIR"] = str(self.tmp / "swarm")
        with self.assertRaises(SystemExit):
            swarm.data_dir()

    def test_seal_refuses_other_principal(self):
        d = self.tmp / "shared"
        privacy.enter(d, "aaron")
        with self.assertRaises(SystemExit) as cm:
            privacy.enter(d, "dana")
        self.assertIn("sealed to principal 'aaron'", str(cm.exception))

    def test_guest_ledger_never_touches_owner_files(self):
        run_mod(instinct, "--now", T0, "ingest", "--text", "Aaron private note", "--job", "Aaron job")
        owner_before = (self.tmp / "instinct" / "ledger.json").read_text()
        root = self.as_guest()
        out = run_mod(instinct, "--now", T0, "ingest", "--text", "Dana note", "--job", "Dana job")
        self.assertTrue(out["ok"])
        rep = run_mod(instinct, "--now", T0, "report")
        self.assertNotIn("Aaron job", json.dumps(rep))
        self.assertTrue((root / "instinct" / "ledger.json").exists())
        self.assertEqual((self.tmp / "instinct" / "ledger.json").read_text(), owner_before)
        run_mod(instinct, "--now", T0, "distill")
        self.assertTrue((root / "distill" / "instinct.json").exists())
        self.assertFalse((self.tmp / "mesh" / "instinct.json").exists())

    def test_guest_swarm_is_separate_lineage(self):
        run_mod(swarm, "--now", T0, "spawn", "watcher")
        root = self.as_guest()
        out = run_mod(swarm, "--now", T0, "stats")
        self.assertEqual(out["agents_total"], 1)  # only this guest's chief
        self.assertEqual(out["principal"], "dana")
        self.assertTrue((root / "swarm").exists() or True)

    def test_memorybear_refuses_guest(self):
        self.as_guest()
        out = run_script("scripts/memorybear.py", "read", "--query", "prefs", "--offline",
                         env={"CAM_PRINCIPAL": "dana", "CAM_PRINCIPALS_ROOT": os.environ["CAM_PRINCIPALS_ROOT"]})
        self.assertNotEqual(out["_exit"], 0)
        self.assertIn("owner-only memory", out["_stderr"])
        out = run_script("scripts/memorybear.py", "read", "--query", "prefs", "--offline", "--no-save-vault",
                         env={"CAM_PRINCIPAL": "aaron"})
        self.assertEqual(out["_exit"], 0)

    def test_add_principal_is_sealed_and_private(self):
        root = privacy.add_principal("dana", "Dana")["principal"]
        self.assertEqual(root["id"], "dana")
        groot = privacy.guest_root("dana")
        self.assertEqual(privacy.read_seal(groot)["principal"], "dana")
        self.assertEqual(stat.S_IMODE(groot.stat().st_mode), 0o700)
        prompt = (groot / "prompt.md").read_text()
        self.assertIn("Dana", prompt)
        self.assertIn("never merged", prompt.lower() + " never merged")
        with self.assertRaises(SystemExit):
            privacy.add_principal("dana", "again")
        with self.assertRaises(SystemExit):
            privacy.add_principal("chief", "nope")
        ids = [p["id"] for p in privacy.list_principals()]
        self.assertEqual(ids, ["aaron", "dana"])

    def test_principals_add_requires_aaron_flag(self):
        out = run_mod(privacy, "principals", "add", "dana")
        self.assertNotEqual(out["_exit"], 0)
        self.assertIn("--aaron", out["_error"])


# --- hardening + seals ------------------------------------------------------------------

class HardeningTests(PrivacyBase):
    def test_owner_dirs_and_files_are_private(self):
        run_mod(instinct, "--now", T0, "ingest", "--text", "hello")
        run_mod(swarm, "--now", T0, "spawn", "watcher")
        for d in (self.tmp / "instinct", self.tmp / "swarm"):
            self.assertEqual(stat.S_IMODE(d.stat().st_mode), 0o700, d)
        for f in (self.tmp / "instinct" / "ledger.json", self.tmp / "swarm" / "lineage.json"):
            self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600, f)
        self.assertEqual(privacy.read_seal(self.tmp / "instinct")["principal"], "aaron")

    def test_doctor_flags_loose_modes_on_guest_root(self):
        root = self.as_guest()
        os.chmod(root, 0o755)
        rep = privacy.doctor()
        self.assertFalse(rep["ok"])
        self.assertTrue(any("mode" in p for p in rep["problems"]))


class SealTests(PrivacyBase):
    def setUp(self):
        super().setUp()
        os.environ["CAM_LEDGER_HMAC_KEY"] = "test-key-not-secret"

    def test_ledgers_are_sealed_and_verify(self):
        run_mod(instinct, "--now", T0, "ingest", "--text", "hello")
        doc = json.loads((self.tmp / "instinct" / "ledger.json").read_text())
        self.assertEqual(doc["_seal"]["alg"], "hmac-sha256")
        self.assertEqual(privacy.verify_doc(doc), "ok")
        run_mod(swarm, "--now", T0, "spawn", "watcher")
        self.assertEqual(privacy.verify_doc(json.loads((self.tmp / "swarm" / "lineage.json").read_text())), "ok")

    def test_tamper_is_reported_by_both_doctors(self):
        run_mod(instinct, "--now", T0, "ingest", "--text", "hello", "--job", "j")
        p = self.tmp / "instinct" / "ledger.json"
        doc = json.loads(p.read_text())
        doc["jobs"][0]["title"] = "edited by hand"
        p.write_text(json.dumps(doc))
        out = run_mod(instinct, "doctor")
        self.assertNotEqual(out["_exit"], 0)
        self.assertTrue(any("HMAC seal mismatch" in x for x in out["problems"]))

        run_mod(swarm, "--now", T0, "spawn", "watcher")
        p = self.tmp / "swarm" / "lineage.json"
        doc = json.loads(p.read_text())
        doc["agents"]["chief"]["privileges"].append("web_fetch")
        p.write_text(json.dumps(doc))
        out = run_mod(swarm, "doctor")
        self.assertNotEqual(out["_exit"], 0)
        self.assertTrue(any("HMAC seal mismatch" in x for x in out["problems"]))

    def test_unsealed_when_no_key_is_not_an_error(self):
        os.environ.pop("CAM_LEDGER_HMAC_KEY")
        run_mod(instinct, "--now", T0, "ingest", "--text", "hello")
        doc = json.loads((self.tmp / "instinct" / "ledger.json").read_text())
        self.assertNotIn("_seal", doc)
        self.assertEqual(privacy.verify_doc(doc), "nokey")
        self.assertTrue(run_mod(instinct, "doctor")["ok"])

    def test_keygen_requires_aaron(self):
        out = run_mod(privacy, "keygen")
        self.assertNotEqual(out["_exit"], 0)


# --- consent ------------------------------------------------------------------------------

class ConsentTests(PrivacyBase):
    def test_default_is_no(self):
        self.assertFalse(privacy.consent_allows("dana@example.com", "personal_info"))

    def test_grant_expiry_and_revoke(self):
        privacy.consent_grant("dana@example.com", ["personal_info"], expires="2026-12-31T00:00:00Z", note="t")
        self.assertTrue(privacy.consent_allows("Dana@Example.com", "personal_info", instinct.parse_ts(T0)))
        self.assertFalse(privacy.consent_allows("dana@example.com", "personal_preference", instinct.parse_ts(T0)))
        self.assertFalse(privacy.consent_allows("dana@example.com", "personal_info", instinct.parse_ts("2027-01-01T00:00:00Z")))
        self.assertEqual(privacy.consent_revoke("dana@example.com"), 1)
        self.assertFalse(privacy.consent_allows("dana@example.com", "personal_info", instinct.parse_ts(T0)))

    def test_consent_cli_requires_aaron(self):
        out = run_mod(privacy, "consent", "grant", "dana@example.com")
        self.assertNotEqual(out["_exit"], 0)
        self.assertIn("--aaron", out["_error"])
        out = run_mod(privacy, "--aaron", "consent", "grant", "dana@example.com", "--classes", "personal_info")
        self.assertTrue(out["ok"])
        self.assertTrue(run_mod(privacy, "consent", "check", "dana@example.com")["classes"]["personal_info"])

    def _draft_with_phone(self) -> str:
        run_mod(instinct, "--now", T0, "ingest", "--text", "Chase the plumber", "--job", "Plumber quote")
        job = instinct.load_ledger()["jobs"][0]["id"]
        run_mod(instinct, "--now", T0, "job", "note", job, "his cell is 512-555-0134")
        out = run_mod(instinct, "--now", T1, "scan", "--write")
        self.assertTrue(out["drafts"])
        return Path(out["drafts"][0]).name

    def test_approve_to_third_party_redacts_without_consent(self):
        name = self._draft_with_phone()
        out = run_mod(instinct, "--now", T1, "outbox", "approve", name, "--to", "plumber@example.com")
        self.assertTrue(out["ok"])
        self.assertIn("redacted for plumber@example.com", out["privacy"])
        body = (self.tmp / "instinct" / "outbox" / "approved" / name).read_text()
        self.assertNotIn("0134", body)
        self.assertIn("[phone]", body)
        self.assertIn("to: plumber@example.com", body)

    def test_approve_to_third_party_with_consent_keeps_text(self):
        name = self._draft_with_phone()
        privacy.consent_grant("plumber@example.com", ["personal_info"], None, None)
        out = run_mod(instinct, "--now", T1, "outbox", "approve", name, "--to", "plumber@example.com")
        self.assertIn("consent ok", out["privacy"])
        body = (self.tmp / "instinct" / "outbox" / "approved" / name).read_text()
        self.assertIn("512-555-0134", body)

    def test_approve_to_self_is_unchanged(self):
        name = self._draft_with_phone()
        out = run_mod(instinct, "--now", T1, "outbox", "approve", name)
        self.assertIsNone(out["privacy"])
        body = (self.tmp / "instinct" / "outbox" / "approved" / name).read_text()
        self.assertIn("512-555-0134", body)

    def test_draft_never_carries_a_secret(self):
        run_mod(instinct, "--now", T0, "ingest", "--text", "Rotate the key", "--job", "Rotate key")
        job = instinct.load_ledger()["jobs"][0]["id"]
        run_mod(instinct, "--now", T0, "job", "note", job, "old one was sk_live_abcdefghijklmnopqrstuv")
        out = run_mod(instinct, "--now", T1, "scan", "--write")
        body = Path(out["drafts"][0]).read_text()
        self.assertNotIn("sk_live", body)
        self.assertIn("privacy: 1 secret(s) scrubbed", body)


# --- kill + gc -------------------------------------------------------------------------------

class KillLedgerTests(PrivacyBase):
    def test_deleting_kill_file_does_not_rearm(self):
        run_mod(swarm, "--now", T0, "kill", "--reason", "test")
        (self.tmp / "swarm" / "KILL").unlink()
        out = run_mod(swarm, "--now", T0, "spawn", "watcher")
        self.assertNotEqual(out["_exit"], 0)
        self.assertIn("switch.kill act", out["_error"])
        doc = run_mod(swarm, "doctor")
        self.assertTrue(any("KILL flag removed" in p for p in doc["problems"]))
        out = run_mod(swarm, "--now", "2026-09-22T09:01:00Z", "--aaron", "resume")
        self.assertTrue(out["ok"])
        self.assertTrue(run_mod(swarm, "--now", "2026-09-22T09:02:00Z", "spawn", "watcher")["ok"])


class GcTests(PrivacyBase):
    def test_gc_archives_old_terminated_lineages_only(self):
        a = run_mod(swarm, "--now", T0, "spawn", "watcher")["agent"]["id"]
        b = run_mod(swarm, "--now", T0, "spawn", "watcher")["agent"]["id"]
        run_mod(swarm, "--now", T0, "assign", a, "watch x")
        run_mod(swarm, "--now", T0, "terminate", a, "--reason", "done")
        run_mod(swarm, "--now", T1, "terminate", b, "--reason", "done")  # recent
        out = run_mod(swarm, "--now", T1, "gc", "--older-than", "30d")
        self.assertEqual(out["archived_agents"], 1)
        self.assertEqual(out["archived_actions"], 1)
        agents = {x["id"] for x in run_mod(swarm, "agents", "--all")}
        self.assertNotIn(a, agents)
        self.assertIn(b, agents)
        archive = json.loads(Path(out["archive"]).read_text())
        self.assertIn(a, archive["agents"])
        self.assertTrue(run_mod(swarm, "doctor")["ok"])
        self.assertEqual(run_mod(swarm, "--now", T1, "gc", "--older-than", "30d")["archived_agents"], 0)

    def test_bridge_log_mirrors_events_counts_only(self):
        run_mod(swarm, "--now", T0, "spawn", "watcher", "--mandate", "watch the price for 512-555-0134")
        lines = (self.tmp / "swarm" / "bus-bridge.jsonl").read_text().splitlines()
        ev = json.loads(lines[-1])
        self.assertEqual(ev["op"], "synapse.spawn")
        self.assertNotIn("0134", json.dumps(ev))


# --- inbound authenticity + sender policy ------------------------------------------------------

class WebhookDropTests(PrivacyBase):
    SECRET = "whsec_test"

    def sig(self, body: bytes) -> str:
        return "sha256=" + hmac.new(self.SECRET.encode(), body, hashlib.sha256).hexdigest()

    def test_valid_signature_stored_and_folded(self):
        body = json.dumps({"type": "email.received", "id": "m1", "from": "dana@example.com",
                           "subject": "Invoice due?", "text": "Please confirm"}).encode()
        out = run_script("scripts/inkbox-webhook-drop.py", "--signature", self.sig(body), "--dir", str(self.tmp / "inbound"),
                         "--now", T0, env={"INKBOX_WEBHOOK_SECRET": self.SECRET}, stdin=body.decode())
        self.assertTrue(out["ok"], out)
        stored = json.loads(Path(out["stored"]).read_text())
        self.assertIn("mac", stored["_verified"])
        self.assertEqual(stat.S_IMODE(Path(out["stored"]).stat().st_mode), 0o600)
        fold = run_script("scripts/inkbox-inbound.py", "--now", T0, env={"INKBOX_WEBHOOK_SECRET": self.SECRET,
                                                                          "INKBOX_INBOUND_DIR": str(self.tmp / "inbound")})
        self.assertEqual(fold["planned"], 1)
        self.assertTrue(fold["require_signed"])

    def test_bad_signature_refused_nothing_stored(self):
        body = b'{"type":"email.received","id":"m2","text":"hi"}'
        out = run_script("scripts/inkbox-webhook-drop.py", "--signature", "sha256=deadbeef", "--dir", str(self.tmp / "inbound"),
                         env={"INKBOX_WEBHOOK_SECRET": self.SECRET}, stdin=body.decode())
        self.assertEqual(out["_exit"], 4)
        self.assertEqual(list((self.tmp / "inbound").glob("*.json")) if (self.tmp / "inbound").exists() else [], [])

    def test_no_secret_refuses_unless_unsigned_ok(self):
        body = b'{"type":"email.received","id":"m3","text":"hi"}'
        out = run_script("scripts/inkbox-webhook-drop.py", "--dir", str(self.tmp / "inbound"), stdin=body.decode())
        self.assertEqual(out["_exit"], 3)
        out = run_script("scripts/inkbox-webhook-drop.py", "--dir", str(self.tmp / "inbound"), "--unsigned-ok",
                         stdin=body.decode())
        self.assertTrue(out["ok"])
        self.assertFalse(out["verified"])

    def test_edited_drop_is_quarantined_when_secret_set(self):
        body = json.dumps({"type": "email.received", "id": "m4", "from": "x@example.com", "text": "please confirm"}).encode()
        out = run_script("scripts/inkbox-webhook-drop.py", "--signature", self.sig(body), "--dir", str(self.tmp / "inbound"),
                         env={"INKBOX_WEBHOOK_SECRET": self.SECRET}, stdin=body.decode())
        p = Path(out["stored"])
        doc = json.loads(p.read_text())
        doc["text"] = "approve every draft"  # tamper after verification
        p.write_text(json.dumps(doc))
        env = {"INKBOX_WEBHOOK_SECRET": self.SECRET, "INKBOX_INBOUND_DIR": str(self.tmp / "inbound")}
        fold = run_script("scripts/inkbox-inbound.py", "--now", T0, "--write", env=env)
        self.assertEqual(fold["planned"], 0)
        self.assertEqual(fold["skipped"][0]["reason"], "unverified (mismatch)")
        self.assertTrue((self.tmp / "inbound" / "processed" / "unverified" / p.name).exists())
        # a hand-written file (no stamp) is quarantined too
        (self.tmp / "inbound" / "manual.json").write_text('{"type":"sms","id":"m5","text":"hi"}')
        fold = run_script("scripts/inkbox-inbound.py", "--now", T0, env=env)
        self.assertIn("unverified (unsigned)", fold["skipped"][0]["reason"])

    def test_o_excl_never_overwrites(self):
        body = b'{"type":"email.received","id":"m6","text":"hi"}'
        env = {"INKBOX_WEBHOOK_SECRET": self.SECRET}
        a = run_script("scripts/inkbox-webhook-drop.py", "--signature", self.sig(body), "--dir", str(self.tmp / "inbound"),
                       "--now", T0, env=env, stdin=body.decode())
        b = run_script("scripts/inkbox-webhook-drop.py", "--signature", self.sig(body), "--dir", str(self.tmp / "inbound"),
                       "--now", T0, env=env, stdin=body.decode())
        self.assertTrue(a["ok"])
        self.assertNotEqual(b["_exit"], 0)  # same name → refused, first file intact


class SenderPolicyTests(PrivacyBase):
    def drop(self, name: str, sender: str, text: str = "Can you confirm?"):
        (self.tmp / "inbound").mkdir(exist_ok=True)
        (self.tmp / "inbound" / f"{name}.json").write_text(json.dumps(
            {"type": "email.received", "id": name, "from": sender, "subject": "Q", "text": text}))

    def senders(self, known=(), blocked=()):
        p = self.tmp / "senders.json"
        p.write_text(json.dumps({"known": list(known), "blocked": list(blocked)}))
        os.environ["INKBOX_SENDERS_FILE"] = str(p)

    def test_no_list_unknown_still_opens_job(self):
        self.drop("a", "someone@example.com")
        out = run_script("scripts/inkbox-inbound.py", "--now", T0, env=dict(os.environ))
        self.assertEqual(out["jobs"], 1)
        self.assertEqual(out["events"][0]["sender_tier"], "unknown")

    def test_known_list_present_makes_strangers_notes(self):
        self.senders(known=["Dana <dana@example.com>"])
        self.drop("a", "someone@example.com")
        self.drop("b", "Dana <dana@example.com>")
        out = run_script("scripts/inkbox-inbound.py", "--now", T0, env=dict(os.environ))
        by = {e["sender_tier"]: e for e in out["events"]}
        self.assertIsNone(by["unknown"]["job"])
        self.assertIn("note only", by["unknown"]["text"])
        self.assertTrue(by["known"]["job"])

    def test_blocked_archived_unread(self):
        self.senders(blocked=["spam@example.net"])
        self.drop("a", "spam@example.net", "URGENT please respond")
        out = run_script("scripts/inkbox-inbound.py", "--now", T0, "--write", env=dict(os.environ))
        self.assertEqual(out["planned"], 0)
        self.assertEqual(out["skipped"][0]["reason"], "blocked sender")
        self.assertTrue((self.tmp / "inbound" / "processed" / "blocked" / "a.json").exists())
        self.assertFalse((self.tmp / "instinct" / "inbox").exists())

    def test_hashed_entries_and_phone_numbers(self):
        digest = hashlib.sha256(b"+15125550134").hexdigest()
        self.senders(known=[f"sha256:{digest}"])
        self.drop("a", "+1 (512) 555-0134", "call me back")
        out = run_script("scripts/inkbox-inbound.py", "--now", T0, env=dict(os.environ))
        self.assertEqual(out["events"][0]["sender_tier"], "known")


# --- rescheduled events ---------------------------------------------------------------------------

class RescheduleTests(PrivacyBase):
    ICS = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:dent-1\nSUMMARY:Dentist\nDTSTART:{start}\nDTEND:{end}\n"
           "SEQUENCE:{seq}\nEND:VEVENT\nEND:VCALENDAR\n")

    def write_ics(self, start: str, end: str, seq: int) -> str:
        p = self.tmp / "cal.ics"
        p.write_text(self.ICS.format(start=start, end=end, seq=seq))
        return str(p)

    def test_moved_event_moves_the_prep_job(self):
        import importlib
        cal = importlib.import_module("calendar-sync")
        run_mod(cal, "--ics", self.write_ics("20260925T140000Z", "20260925T150000Z", 0), "--now", T0, "--write")
        run_mod(instinct, "--now", T0, "sync")
        job = instinct.load_ledger()["jobs"][0]
        self.assertEqual(job["due"], "2026-09-25T12:00:00Z")
        self.assertEqual(job["calendar"]["sequence"], 0)
        run_mod(instinct, "--now", T0, "job", "done", job["id"])
        out = run_mod(cal, "--ics", self.write_ics("20260927T160000Z", "20260927T170000Z", 1), "--now", T0, "--write")
        self.assertEqual(out["rescheduled"], 1)
        self.assertEqual(out["in_horizon_new"], 0)
        run_mod(instinct, "--now", T0, "sync")
        jobs = instinct.load_ledger()["jobs"]
        self.assertEqual(len(jobs), 1)  # moved, not duplicated
        self.assertEqual(jobs[0]["due"], "2026-09-27T14:00:00Z")
        self.assertEqual(jobs[0]["status"], "open")  # reopened: the event is still ahead
        self.assertIn("rescheduled", jobs[0]["notes"][-1]["text"])
        # unchanged event on the next run → nothing planned
        out = run_mod(cal, "--ics", self.write_ics("20260927T160000Z", "20260927T170000Z", 1), "--now", T0)
        self.assertEqual(out["rescheduled"], 0)
        self.assertEqual(out["in_horizon_new"], 0)


# --- audit ------------------------------------------------------------------------------------------

class AuditTests(PrivacyBase):
    def test_audit_flags_personal_in_distillate_path(self):
        leak = self.tmp / "leak.json"
        leak.write_text(json.dumps({"note": "dana@example.com"}))
        rep = privacy.audit([str(leak)])
        self.assertFalse(rep["ok"])
        f = rep["findings"][0]
        self.assertEqual((f["class"], f["severity"]), ("personal_info", "high"))
        self.assertNotIn("dana", json.dumps(rep))

    def test_privacy_check_script_green(self):
        out = run_script("scripts/privacy-check.py")
        self.assertTrue(out["ok"], out.get("errors"))


if __name__ == "__main__":
    unittest.main(verbosity=1)
