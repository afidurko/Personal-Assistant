#!/usr/bin/env python3
"""Probe VoiceStudio local backend health for Cam.

Default target: http://localhost:3900/health (see config/integrations/voicestudio.json).
Does not start the app or download models. Exit 0 when healthy, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "integrations" / "voicestudio.json"


def load_cfg() -> dict:
    if not CFG.exists():
        return {}
    return json.loads(CFG.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=None, help="Override backend base URL")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    cfg = load_cfg()
    backend = cfg.get("backend") or {}
    base = (args.base_url or backend.get("base_url") or "http://localhost:3900").rstrip("/")
    health_path = backend.get("health_path") or "/health"
    url = f"{base}{health_path}"

    report: dict = {
        "ok": False,
        "url": url,
        "integration": "voicestudio",
        "config": str(CFG.relative_to(ROOT)),
        "submodule": "integrations/voicestudio",
        "error": None,
        "body": None,
        "status": None,
    }

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            report["status"] = getattr(resp, "status", 200)
            try:
                report["body"] = json.loads(raw)
            except json.JSONDecodeError:
                report["body"] = raw.strip()[:500]
            report["ok"] = 200 <= int(report["status"]) < 300
    except urllib.error.HTTPError as exc:
        report["status"] = exc.code
        report["error"] = f"http_{exc.code}"
    except urllib.error.URLError as exc:
        report["error"] = f"unreachable:{exc.reason}"
    except Exception as exc:  # noqa: BLE001
        report["error"] = str(exc)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status = "OK" if report["ok"] else "DOWN"
        print(f"voicestudio-health: {status} {url}")
        if report["error"]:
            print(f"  error={report['error']}")
        elif report["body"] is not None:
            print(f"  body={report['body']!r}"[:240])
        print("  docs=config/integrations/voicestudio.md")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
