#!/usr/bin/env python3
"""Validate config/connectors/registry.json against the connectome.

Hard errors (exit 1): unknown sense / motor / switch ids, missing scripts or
configs, MCP tools the server does not register, act-mode connectors that
reach humans without switch.outbound, a role list that names an unknown role.

Soft findings (exit 0, reported): credentials not present in the environment,
`via_brain` connectors (nothing to check locally).

    python3 scripts/connectors-check.py            # human summary
    python3 scripts/connectors-check.py --json     # machine readable
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/connectors/registry.json"
HUMAN_REACHING_MOTORS = {"motor.text", "motor.call", "motor.facetime", "motor.speak",
                         "motor.inkbox", "motor.voicestudio"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ids_of(doc: dict) -> set[str]:
    for value in doc.values():
        if isinstance(value, list) and value and isinstance(value[0], dict) and "id" in value[0]:
            return {x["id"] for x in value}
    return set()


def known_roles() -> set[str]:
    roles = {p.stem for p in (ROOT / "config/roles").glob("*.md")}
    roles |= {"chief", "aaron"}
    return roles


def mcp_tool_names() -> set[str]:
    src = (ROOT / "scripts/cam-mcp-server.py").read_text(encoding="utf-8")
    return set(re.findall(r'"name":\s*"([a-z_]+)"', src))


def check(registry: dict) -> tuple[list[str], list[str], list[dict]]:
    errors: list[str] = []
    findings: list[str] = []
    rows: list[dict] = []

    senses = ids_of(load(ROOT / "config/connectome/sensory.json"))
    motors = ids_of(load(ROOT / "config/connectome/motor.json"))
    switches = ids_of(load(ROOT / "config/connectome/switches.json"))
    roles = known_roles()
    tools = mcp_tool_names()
    modes = set(registry.get("modes") or {})

    seen: set[str] = set()
    for c in registry.get("connectors") or []:
        cid = c.get("id") or "<no id>"
        if cid in seen:
            errors.append(f"{cid}: duplicate id")
        seen.add(cid)
        if c.get("mode") not in modes:
            errors.append(f"{cid}: mode {c.get('mode')!r} not in registry.modes")
        if c.get("sense") and c["sense"] not in senses:
            errors.append(f"{cid}: unknown sense {c['sense']}")
        if c.get("motor") and c["motor"] not in motors:
            errors.append(f"{cid}: unknown motor {c['motor']}")
        if c.get("switch") not in switches:
            errors.append(f"{cid}: unknown switch {c.get('switch')}")
        if c.get("mode") == "act" and c.get("motor") in HUMAN_REACHING_MOTORS \
                and c.get("switch") != "switch.outbound":
            errors.append(f"{cid}: human-reaching motor {c['motor']} must be gated by switch.outbound")
        for rel in c.get("scripts") or []:
            if not (ROOT / rel).exists():
                errors.append(f"{cid}: missing script {rel}")
        if c.get("config") and not (ROOT / c["config"]).exists():
            errors.append(f"{cid}: missing config {c['config']}")
        for tool in c.get("mcp_tools") or []:
            if tool not in tools:
                errors.append(f"{cid}: MCP tool {tool} not registered in scripts/cam-mcp-server.py")
        if c.get("roles") != "all":
            for r in c.get("roles") or []:
                if r not in roles:
                    errors.append(f"{cid}: unknown role {r}")
        creds = c.get("credential_env") or []
        present = {k: bool(os.environ.get(k)) for k in creds}
        if creds and not all(present.values()):
            findings.append(f"{cid}: credential(s) not in env: "
                            f"{[k for k, ok in present.items() if not ok]} (local .env only — never commit)")
        if c.get("mode") == "via_brain":
            findings.append(f"{cid}: handled by nullclaw — nothing to check locally")
        rows.append({
            "id": cid, "mode": c.get("mode"), "status": c.get("status"), "switch": c.get("switch"),
            "sense": c.get("sense"), "motor": c.get("motor"),
            "credentials_present": present, "roles": c.get("roles"),
            "mcp_tools": c.get("mcp_tools") or [],
        })
    return errors, findings, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Cam connectors registry")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not REGISTRY.exists():
        print(f"missing {REGISTRY}", file=sys.stderr)
        return 1
    registry = load(REGISTRY)
    errors, findings, rows = check(registry)
    by_mode: dict[str, int] = {}
    for r in rows:
        by_mode[r["mode"]] = by_mode.get(r["mode"], 0) + 1
    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "findings": findings,
                          "connectors": rows, "by_mode": by_mode}, indent=2))
    else:
        for e in errors:
            print(f"ERROR: {e}")
        for f in findings:
            print(f"note: {f}")
        state = "OK" if not errors else "FAIL"
        print(f"{state}: {len(rows)} connectors — {by_mode}; {len(errors)} errors, {len(findings)} notes")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
