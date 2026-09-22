#!/usr/bin/env python3
"""Cam Sentinel CLI — decide, approve, grant, and read the intent ledger.

  python3 scripts/cam-sentinel.py decide --sense sense.email.thread --goal "reply to landlord" --journal
  python3 scripts/cam-sentinel.py pending
  python3 scripts/cam-sentinel.py approve <pending_id> --scope task
  python3 scripts/cam-sentinel.py deny <pending_id>
  python3 scripts/cam-sentinel.py grant --motor motor.inkbox --scope until --until 2026-09-22T00:00:00Z --covers-tainted
  python3 scripts/cam-sentinel.py grants | revoke <grant_id> | revoke --all
  python3 scripts/cam-sentinel.py ledger [--day YYYY-MM-DD] [--json]
  python3 scripts/cam-sentinel.py resume-check
  python3 scripts/cam-sentinel.py new-session

Only Aaron approves or grants (--by defaults to Aaron; MCP exposes read/decide only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_inproc  # noqa: E402
import cam_journal as cj  # noqa: E402
import cam_sentinel as cs  # noqa: E402


def cmd_decide(args) -> int:
    doc = cam_inproc.route(
        sense=args.sense,
        goal=args.goal,
        hotspot=args.hotspot or None,
        kill=args.kill,
        enhance=args.enhance,
    )
    sent = doc.get("sentinel") or {}
    if args.path:
        sent = cs.evaluate(
            list(doc.get("motor_plan") or []) + list(doc.get("motor_pending") or []),
            sense=args.sense,
            pathway=doc.get("pathway") or [],
            switch_state=doc.get("switch_state") or {},
            task=args.goal,
            paths=args.path,
            session_id=cs.current_session_id(),
        )
    out = {
        "sense": args.sense,
        "goal": args.goal,
        "hotspot_id": doc.get("hotspot_id"),
        "motor_plan": sent.get("allowed", doc.get("motor_plan")),
        "motor_pending": sent.get("pending", []),
        "sentinel": sent,
    }
    if args.journal:
        out["journal"] = cs.record(sent, sense=args.sense, goal=args.goal, session_id=cs.current_session_id())
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"sentinel: allowed={out['motor_plan']} pending={out['motor_pending']} taint={sent.get('taint')}")
        for motor, row in (sent.get("decisions") or {}).items():
            print(f"  {row['decision']:<5} {motor:<18} {row.get('reason')}")
        if args.journal:
            print(f"  journaled: pending_ids={out['journal']['pending']}")
    return 0


def cmd_pending(args) -> int:
    rows = cs.pending(args.day)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"open approvals: {len(rows)}")
        for r in rows:
            print(f"  {r['pending_id']}  {r['motor']:<18} {r.get('reason')}  options={r.get('grant_options')}")
    return 0


def cmd_approve(args) -> int:
    res = cs.approve(args.pending_id, scope=args.scope, by=args.by, task=args.task, until=args.until, day=args.day)
    print(json.dumps({"approved": args.pending_id, "grant": res["grant"], "intent_seq": res["intent"]["sequence"]}, indent=2))
    return 0


def cmd_deny(args) -> int:
    rec = cs.deny(args.pending_id, by=args.by, day=args.day)
    print(json.dumps({"denied": args.pending_id, "sequence": rec["sequence"]}, indent=2))
    return 0


def cmd_grant(args) -> int:
    g = cs.grant(
        args.motor,
        args.scope,
        by=args.by,
        task=args.task,
        until=args.until,
        covers_tainted=args.covers_tainted,
        reason=args.reason,
    )
    print(json.dumps(g, indent=2))
    return 0


def cmd_grants(_args) -> int:
    print(json.dumps({"session_id": cs.current_session_id(), "grants": cs.load_grants()}, indent=2))
    return 0


def cmd_revoke(args) -> int:
    n = cs.revoke(args.grant_id, all_grants=args.all)
    print(json.dumps({"revoked": n}))
    return 0


def cmd_ledger(args) -> int:
    doc = cj.export(args.day)
    if args.json:
        print(json.dumps(doc, indent=2, sort_keys=True))
    else:
        print(
            f"intent ledger {doc['day']}  ({doc['record_count']} records, "
            f"open_approvals={len(doc['open_approvals'])}, unconfirmed={len(doc['unconfirmed_intents'])})"
        )
        for line in cj.ledger_lines(doc["events"]):
            print(line)
    return 0


def cmd_resume_check(args) -> int:
    rows = cj.read(args.day)
    open_intents = cj.unconfirmed_intents(rows)
    print(json.dumps({"day": args.day or cj.today(), "unconfirmed_intents": [r["payload"] for r in open_intents]}, indent=2))
    return 0


def cmd_new_session(_args) -> int:
    print(json.dumps({"session_id": cs.new_session()}))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("decide")
    d.add_argument("--sense", required=True)
    d.add_argument("--goal", default="")
    d.add_argument("--hotspot", default="")
    d.add_argument("--kill", action="store_true")
    d.add_argument("--enhance", action="store_true")
    d.add_argument("--path", action="append", default=[], help="target path(s) for guardrail check")
    d.add_argument("--journal", action="store_true", help="write intents / approval requests")
    d.add_argument("--json", action="store_true")
    d.set_defaults(fn=cmd_decide)

    pe = sub.add_parser("pending")
    pe.add_argument("--day", default=None)
    pe.add_argument("--json", action="store_true")
    pe.set_defaults(fn=cmd_pending)

    ap = sub.add_parser("approve")
    ap.add_argument("pending_id")
    ap.add_argument("--scope", required=True)
    ap.add_argument("--task", default=None)
    ap.add_argument("--until", default=None)
    ap.add_argument("--by", default="Aaron")
    ap.add_argument("--day", default=None)
    ap.set_defaults(fn=cmd_approve)

    de = sub.add_parser("deny")
    de.add_argument("pending_id")
    de.add_argument("--by", default="Aaron")
    de.add_argument("--day", default=None)
    de.set_defaults(fn=cmd_deny)

    g = sub.add_parser("grant")
    g.add_argument("--motor", required=True)
    g.add_argument("--scope", required=True)
    g.add_argument("--task", default=None)
    g.add_argument("--until", default=None)
    g.add_argument("--covers-tainted", action="store_true")
    g.add_argument("--reason", default="")
    g.add_argument("--by", default="Aaron")
    g.set_defaults(fn=cmd_grant)

    sub.add_parser("grants").set_defaults(fn=cmd_grants)

    rv = sub.add_parser("revoke")
    rv.add_argument("grant_id", nargs="?", default=None)
    rv.add_argument("--all", action="store_true")
    rv.set_defaults(fn=cmd_revoke)

    le = sub.add_parser("ledger")
    le.add_argument("--day", default=None)
    le.add_argument("--json", action="store_true")
    le.set_defaults(fn=cmd_ledger)

    rc = sub.add_parser("resume-check")
    rc.add_argument("--day", default=None)
    rc.set_defaults(fn=cmd_resume_check)

    sub.add_parser("new-session").set_defaults(fn=cmd_new_session)

    args = p.parse_args()
    try:
        return args.fn(args)
    except (PermissionError, ValueError, KeyError) as exc:
        print(f"sentinel: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
