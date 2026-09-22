#!/usr/bin/env python3
"""Validate Cam Sentinel (Muse pattern): taint, grants, guardrails, journal contract."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_inproc  # noqa: E402
import cam_journal as cj  # noqa: E402
import cam_sentinel as cs  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    pol = cs.load_policy()
    errors: list[str] = []
    demos: list[dict] = []

    if pol.get("status") != "applied" or not pol.get("enforce"):
        errors.append("sentinel_policy_not_applied_or_not_enforced")
    if pol.get("sole_operator") != "Aaron":
        errors.append("sole_operator_must_be_aaron")

    # Every motor in motor.json must have a class (fail-closed otherwise)
    motors = json.loads((ROOT / "config/connectome/motor.json").read_text(encoding="utf-8"))
    unclassified = [e["id"] for e in motors["effectors"] if cs.class_of(e["id"], pol) is None]
    if unclassified:
        errors.append(f"unclassified_motors:{','.join(unclassified)}")
    demos.append({"case": "all_motors_classified", "unclassified": unclassified})

    # Clean Aaron chat: unchanged behaviour, nothing pending
    r_chat = cam_inproc.route(sense="sense.chat.aaron", goal="system smoke")
    if r_chat.get("motor_pending"):
        errors.append("clean_chat_should_not_pend")
    if "motor.mesh" not in (r_chat.get("motor_plan") or []):
        errors.append("clean_chat_lost_mesh")
    demos.append({"case": "clean_chat", "motor_plan": r_chat.get("motor_plan"), "pending": r_chat.get("motor_pending")})

    # Lethal trifecta: email thread → outbound text/inkbox must ask, mesh still allowed
    r_mail = cam_inproc.route(sense="sense.email.thread", goal="reply to landlord")
    pend = set(r_mail.get("motor_pending") or [])
    if not {"motor.text", "motor.inkbox"} <= pend:
        errors.append("tainted_email_egress_not_pending")
    if "motor.text" in (r_mail.get("motor_plan") or []):
        errors.append("tainted_text_leaked_into_plan")
    if "motor.mesh" not in (r_mail.get("motor_plan") or []):
        errors.append("tainted_plan_lost_read_motor")
    if not (r_mail.get("sentinel") or {}).get("taint", {}).get("tainted"):
        errors.append("email_not_marked_tainted")
    demos.append({"case": "email_tainted_egress", "motor_plan": r_mail.get("motor_plan"), "pending": r_mail.get("motor_pending")})

    # Listing-derived job submit asks; Aaron-approved enhance on clean chat still allowed
    r_jobs = cam_inproc.route(sense="sense.careers.listing", goal="watch roles")
    if "motor.jobs" not in (r_jobs.get("motor_pending") or []):
        errors.append("listing_job_submit_not_pending")
    r_enh = cam_inproc.route(sense="sense.chat.aaron", goal="apply enhance", hotspot="hotspot.cam_enhance", enhance=True)
    if "motor.enhance" not in (r_enh.get("motor_plan") or []):
        errors.append("aaron_enhance_switch_not_honoured_as_grant")
    demos.append({"case": "jobs_pending_enhance_allowed", "jobs_pending": r_jobs.get("motor_pending"), "enhance_plan": r_enh.get("motor_plan")})

    # Kill → deny everything
    r_kill = cam_inproc.route(sense="sense.email.thread", goal="reply", kill=True)
    if r_kill.get("motor_plan") or r_kill.get("motor_pending"):
        errors.append("kill_left_motor_or_pending")

    # Grants: scoped, Aaron-only, taint-aware, expiring — in an isolated runtime dir
    with tempfile.TemporaryDirectory() as tmp:
        real_root, real_journal = cs.ROOT, cj.JOURNAL_DIR
        cs.ROOT, cj.JOURNAL_DIR = Path(tmp), Path(tmp) / "journal"
        cs._GRANTS_CACHE = None
        try:
            state = dict(r_mail.get("switch_state") or {})
            plan = ["motor.inkbox", "motor.mesh"]
            base = dict(sense="sense.email.thread", pathway=r_mail.get("pathway") or [], switch_state=state)
            try:
                cs.grant("motor.inkbox", "perpetual", by="Cline")
                errors.append("non_aaron_grant_accepted")
            except PermissionError:
                pass
            v0 = cs.evaluate(plan, task="reply", **base)
            if v0["decisions"]["motor.inkbox"]["decision"] != "ask":
                errors.append("tainted_inkbox_should_ask_before_grant")
            if "perpetual" in v0["decisions"]["motor.inkbox"].get("grant_options", []):
                errors.append("tainted_ask_offered_perpetual")
            cs.grant("motor.inkbox", "perpetual", by="Aaron")  # clean-only grant
            v1 = cs.evaluate(plan, task="reply", **base)
            if v1["decisions"]["motor.inkbox"]["decision"] != "ask":
                errors.append("clean_grant_covered_tainted_egress")
            cs.grant("motor.inkbox", "task", by="Aaron", task="reply", covers_tainted=True)
            v2 = cs.evaluate(plan, task="reply", **base)
            v3 = cs.evaluate(plan, task="other", **base)
            if v2["decisions"]["motor.inkbox"]["decision"] != "allow":
                errors.append("task_grant_not_applied")
            if v3["decisions"]["motor.inkbox"]["decision"] != "ask":
                errors.append("task_grant_leaked_to_other_task")
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            cs.revoke(all_grants=True)
            cs.grant("motor.inkbox", "until", by="Aaron", until=past, covers_tainted=True)
            v4 = cs.evaluate(plan, task="reply", **base)
            if v4["decisions"]["motor.inkbox"]["decision"] != "ask":
                errors.append("expired_until_grant_still_active")
            cs.revoke(all_grants=True)

            # Guardrail: a write to the rules Cam runs under offers only a one-time grant
            v5 = cs.evaluate(["motor.cline", "motor.mesh"], sense="sense.chat.aaron", switch_state=state, task="edit rules", paths=[".clinerules"])
            row = v5["decisions"]["motor.cline"]
            if row["decision"] != "ask" or row.get("grant_options") != ["once"]:
                errors.append("guardrail_write_not_once_only")
            v6 = cs.evaluate(["motor.cline"], sense="sense.chat.aaron", switch_state=state, task="edit", paths=["src/App.tsx"])
            if v6["decisions"]["motor.cline"]["decision"] != "allow":
                errors.append("ordinary_write_should_allow")

            # Journal contract: intent before effect, approval chain, deterministic export
            rec = cs.record(v0, sense="sense.email.thread", goal="reply", session_id="check", day="2026-01-01")
            if len(rec["pending"]) != 1 or rec["intents"] != [k for k in rec["intents"] if k.startswith("motor.mesh:")]:
                errors.append("journal_record_shape")
            pend_id = rec["pending"][0]
            try:
                cs.approve(pend_id, scope="perpetual", by="Aaron", day="2026-01-01")
                errors.append("approve_accepted_unoffered_scope")
            except ValueError:
                pass
            try:
                cs.approve(pend_id, scope="once", by="Cline", day="2026-01-01")
                errors.append("non_aaron_approve_accepted")
            except PermissionError:
                pass
            res = cs.approve(pend_id, scope="once", by="Aaron", day="2026-01-01")
            if res["intent"]["payload"]["policy_decision"] != "allow:aaron:once":
                errors.append("approve_intent_stamp")
            if cs.load_grants():
                errors.append("once_approval_persisted_grant")
            if cs.pending("2026-01-01"):
                errors.append("approved_request_still_pending")
            kinds = [r["kind"] for r in cj.read("2026-01-01")]
            last_intent = len(kinds) - 1 - kinds[::-1].index("side_effect_intent")
            if kinds[:1] != ["proposed"] or kinds.index("decision_applied") > last_intent:
                errors.append("journal_order_decision_before_intent")
            e1, e2 = cj.export("2026-01-01"), cj.export("2026-01-01")
            if json.dumps(e1, sort_keys=True) != json.dumps(e2, sort_keys=True):
                errors.append("export_not_deterministic")
            if cj.redact("Authorization: Bearer abcdefghijklmnop") == "Authorization: Bearer abcdefghijklmnop":
                errors.append("redaction_missed_bearer")
            demos.append({"case": "journal", "kinds": kinds, "open_approvals": e1["open_approvals"], "unconfirmed": e1["unconfirmed_intents"]})
        finally:
            cs.ROOT, cj.JOURNAL_DIR = real_root, real_journal
            cs._GRANTS_CACHE = None

    report = {
        "ok": not errors,
        "errors": errors,
        "policy": "config/connectome/sentinel-policy.json",
        "classes": list((pol.get("classes") or {}).keys()),
        "untrusted_senses": len((pol.get("taint") or {}).get("untrusted_senses") or []),
        "demos": demos,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"sentinel-check: {'PASS' if report['ok'] else 'FAIL'}")
        for e in errors:
            print(f"  HARD {e}")
        print(f"  classes={report['classes']} untrusted_senses={report['untrusted_senses']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
