#!/usr/bin/env python3
"""Print Cam converse URL for Tailscale (or override).

Reads config/network/tailscale.json. Fill MagicDNS names to match `tailscale status`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "network" / "tailscale.json"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="", help="override MagicDNS / IP")
    p.add_argument("--port", type=int, default=0)
    args = p.parse_args()
    data = json.loads(CFG.read_text(encoding="utf-8"))
    c = data.get("converse") or {}
    host = args.host or c.get("cam_host_tailscale_ip") or c.get("cam_host_magicdns") or "cam-host"
    port = args.port or int(c.get("port") or 8787)
    url = f"http://{host}:{port}"
    print(
        json.dumps(
            {
                "enabled": data.get("enabled", False),
                "via": c.get("via"),
                "cam_host": host,
                "port": port,
                "url": url,
                "iphone_open": url,
                "hint": "On Cam Mac: python3 scripts/cam-converse-server.py --host 0.0.0.0",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
