#!/usr/bin/env python3
"""workspace_orchestrator — lease mesh namespaces across Cam workspaces.

Forceps-minor analog: max concurrent leases from mesh-params.workspace_leases.
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "config" / "connectome" / "mesh-params.json"
STORE = ROOT / "vault" / "10-Mesh-Distillates" / "workspace-leases.json"
EVENTS = ROOT / "vault" / "10-Mesh-Distillates" / "activity-events.jsonl"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_params() -> dict:
    if not PARAMS.exists():
        return {"workspace_leases": {"max_concurrent": 3, "lease_ttl_s": 3600}}
    return json.loads(PARAMS.read_text(encoding="utf-8"))


def load_store() -> dict:
    if not STORE.exists():
        return {"version": 1, "leases": []}
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "leases": []}


def save_store(data: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def emit(reason: str, intensity: float = 0.7) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": utc(),
                    "neuron": "neuron.workspace_orchestrator",
                    "kind": "agent",
                    "area": "area.dlpfc",
                    "intensity": intensity,
                    "tracts": ["tract.forceps_minor", "tract.mesh_callosal"],
                    "reason": reason,
                    "source": "workspace_orchestrator",
                }
            )
            + "\n"
        )


def prune(leases: list[dict], now: float) -> list[dict]:
    return [L for L in leases if float(L.get("expires_at_epoch", 0)) > now]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["acquire", "release", "list", "prune"])
    ap.add_argument("--workspace", default="default", help="workspace id")
    ap.add_argument("--ns", default="mesh/*", help="mesh namespace pattern")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    params = load_params().get("workspace_leases") or {}
    max_c = int(params.get("max_concurrent") or 3)
    ttl = int(params.get("lease_ttl_s") or 3600)
    store = load_store()
    now = time.time()
    store["leases"] = prune(store.get("leases") or [], now)

    result: dict
    if args.action == "list" or args.action == "prune":
        save_store(store)
        result = {"ok": True, "leases": store["leases"], "max": max_c}
        emit(f"{args.action}:{len(store['leases'])}", 0.4)
    elif args.action == "release":
        before = len(store["leases"])
        store["leases"] = [L for L in store["leases"] if L.get("workspace") != args.workspace]
        save_store(store)
        result = {"ok": True, "released": before - len(store["leases"]), "leases": store["leases"]}
        emit(f"release:{args.workspace}")
    else:  # acquire
        existing = [L for L in store["leases"] if L.get("workspace") == args.workspace]
        if existing:
            # renew
            existing[0]["expires_at_epoch"] = now + ttl
            existing[0]["renewed_at"] = utc()
            save_store(store)
            result = {"ok": True, "renewed": True, "lease": existing[0]}
            emit(f"renew:{args.workspace}")
        elif len(store["leases"]) >= max_c:
            result = {
                "ok": False,
                "error": "lease_limit",
                "max": max_c,
                "holders": [L.get("workspace") for L in store["leases"]],
            }
            emit("lease_blocked", 0.95)
        else:
            lease = {
                "id": str(uuid.uuid4())[:8],
                "workspace": args.workspace,
                "ns": args.ns,
                "acquired_at": utc(),
                "expires_at_epoch": now + ttl,
                "bus": "tract.forceps_minor",
            }
            store["leases"].append(lease)
            save_store(store)
            result = {"ok": True, "lease": lease}
            emit(f"acquire:{args.workspace}")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
