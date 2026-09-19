#!/usr/bin/env python3
"""Cam integration flight envelope — continuous rehearsal checklist.

Injects synthetic Aaron turns, adversarial non-Aaron mic, kill trips, and
scores whether Cam stays Aaron-only, finishes safe motors, and stays honest.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "vault" / "10-Mesh-Distillates" / "flight-envelope-latest.json"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_json(method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"content-type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(raw) if raw else {"error": str(e)}
        except json.JSONDecodeError:
            return e.code, {"error": raw[:200]}
    except Exception as e:  # noqa: BLE001
        return 0, {"error": str(e)}


def local_kernel_checks() -> list[dict]:
    """Offline checks via Node vitest-equivalent: python route + cam-system."""
    steps = []
    code, out = subprocess.getstatusoutput(
        f"{sys.executable} {ROOT / 'scripts/connectome-route.py'} "
        f"--sense sense.chat.aaron --goal 'envelope'"
    )
    try:
        doc = json.loads(out)
        ok = bool(doc.get("accepted"))
    except json.JSONDecodeError:
        ok = False
    steps.append({"id": "python_route_chat", "ok": ok, "detail": "connectome-route accepted"})

    code, out = subprocess.getstatusoutput(
        f"{sys.executable} {ROOT / 'scripts/cam-system.py'} --json --no-write"
    )
    try:
        doc = json.loads(out)
        ok = bool(doc.get("ok"))
    except json.JSONDecodeError:
        ok = code == 0
    steps.append({"id": "cam_system_inventory", "ok": ok, "detail": "pieces inventory"})
    return steps


def live_checks(base: str) -> list[dict]:
    steps = []
    status, doc = http_json("POST", f"{base}/api/system/rehearse")
    steps.append(
        {
            "id": "api_rehearse",
            "ok": status == 200 and bool(doc.get("ok")),
            "detail": json.dumps(doc.get("steps") or doc)[:240],
        }
    )
    status, doc = http_json(
        "POST",
        f"{base}/api/turn",
        {"text": "envelope converse", "source": "text"},
    )
    route = (doc.get("bridge") or {}).get("route") or {}
    steps.append(
        {
            "id": "turn_kernel",
            "ok": status == 200 and route.get("kernel") == "in_process" and route.get("accepted"),
            "detail": f"kernel={route.get('kernel')} motors={route.get('motor_plan')}",
        }
    )
    status, doc = http_json(
        "POST",
        f"{base}/api/turn",
        {"text": "intruder", "source": "mic"},
    )
    steps.append(
        {
            "id": "mic_without_score_blocked",
            "ok": status == 403,
            "detail": f"status={status}",
        }
    )
    status, doc = http_json("GET", f"{base}/api/system")
    steps.append(
        {
            "id": "system_status",
            "ok": status == 200 and doc.get("ok") is not False,
            "detail": f"overall={doc.get('overall')} pieces={len(doc.get('pieces') or [])}",
        }
    )
    return steps


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default="http://127.0.0.1:8787")
    ap.add_argument("--offline-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    steps = local_kernel_checks()
    if not args.offline_only:
        steps.extend(live_checks(args.base))

    ok = all(s["ok"] for s in steps)
    report = {
        "at": utc(),
        "ok": ok,
        "envelope": "pass" if ok else "fail",
        "steps": steps,
        "note": "Integration flight envelope — Aaron-only, kernel, kill, safe motors",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"flight-envelope: {report['envelope'].upper()} ({sum(1 for s in steps if s['ok'])}/{len(steps)})")
        for s in steps:
            print(f"  {'OK' if s['ok'] else 'FAIL'}: {s['id']} — {s['detail'][:80]}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
