#!/usr/bin/env python3
"""Higgsfield dry-run / gated train planner for Cam.

Default is dry-run: validate experiment source + inventory, emit a plan JSON.
Never SSH, allocate GPUs, or spend cloud credits unless:
  --live  AND  CAM_HIGGSFIELD_LIVE=1  AND  enhance switch is act (via --enhance)

Live mode still only prints the launch intent in this phase — no remote exec yet.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config" / "integrations" / "higgsfield.json"
DEFAULT_EXPERIMENT = ROOT / "scripts" / "testdata" / "sample-higgsfield-experiment.py"
DEFAULT_NODES = ROOT / "config" / "integrations" / "higgsfield-nodes.example.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_cfg() -> dict:
    if CFG.is_file():
        return json.loads(CFG.read_text(encoding="utf-8"))
    return {}


def find_experiments(path: Path) -> list[dict]:
    """AST-scan for @experiment(...) without importing torch/deepspeed."""
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    found: list[dict] = []

    def deco_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Call):
            return deco_name(node.func)
        return None

    def deco_args(node: ast.AST) -> tuple[str | None, dict]:
        if not isinstance(node, ast.Call):
            return None, {}
        name = None
        if node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                name = a0.value
        kwargs = {}
        for kw in node.keywords:
            if kw.arg and isinstance(kw.value, ast.Constant):
                kwargs[kw.arg] = kw.value.value
        return name, kwargs

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if deco_name(d) != "experiment":
                continue
            exp_name, kwargs = deco_args(d)
            found.append(
                {
                    "function": node.name,
                    "experiment": exp_name or node.name,
                    "lineno": node.lineno,
                    "kwargs": kwargs,
                }
            )
    return found


def inventory_ok(sub: Path) -> dict:
    required = [
        "higgsfield/experiment.py",
        "higgsfield/internal/experiment/decorator.py",
        "README.md",
        "pyproject.toml",
    ]
    missing = [r for r in required if not (sub / r).exists()]
    return {
        "path": str(sub.relative_to(ROOT)) if sub.is_relative_to(ROOT) else str(sub),
        "populated": sub.exists() and any(p.name != ".git" for p in sub.iterdir()) if sub.exists() else False,
        "missing_files": missing,
        "ok": not missing and sub.exists(),
    }


def load_nodes(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {"nodes": [], "source": None, "ok": True, "note": "no node inventory (dry-run ok)"}
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data.get("nodes") if isinstance(data, dict) else data
    if not isinstance(nodes, list):
        return {"nodes": [], "source": str(path), "ok": False, "error": "nodes must be a list"}
    cleaned = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        cleaned.append(
            {
                "id": n.get("id") or n.get("host") or n.get("name"),
                "host": n.get("host"),
                "gpus": n.get("gpus"),
                "user": n.get("user"),
            }
        )
    return {"nodes": cleaned, "source": str(path), "ok": True, "count": len(cleaned)}


def litserve_handoff(experiment: str, dry_run: bool) -> dict:
    """Stub handoff plan: after train, optional adapter load into LitServe."""
    return {
        "target": "integrations/litserve",
        "motor": "motor.dl",
        "status": "planned" if dry_run else "pending_aaron",
        "adapter_hint": f"checkpoints/{experiment}",
        "notes": "Do not auto-load weights; Aaron confirms path + switch.dl_local",
    }


def build_plan(args: argparse.Namespace) -> dict:
    cfg = load_cfg()
    sub = ROOT / (cfg.get("path") or "integrations/higgsfield")
    exp_path = Path(args.experiment)
    if not exp_path.is_absolute():
        exp_path = (ROOT / exp_path).resolve()

    errors: list[str] = []
    warnings: list[str] = []
    experiments = []
    if not exp_path.is_file():
        errors.append(f"missing experiment file: {exp_path}")
    else:
        experiments = find_experiments(exp_path)
        if not experiments:
            errors.append("no @experiment decorator found")

    inv = inventory_ok(sub)

    nodes_path = Path(args.nodes) if args.nodes else None
    if nodes_path and not nodes_path.is_absolute():
        nodes_path = ROOT / nodes_path
    if nodes_path is None and DEFAULT_NODES.exists():
        nodes_path = DEFAULT_NODES
    nodes = load_nodes(nodes_path)
    if not nodes.get("ok"):
        errors.append(nodes.get("error") or "bad nodes inventory")

    enhance = bool(args.enhance)
    live_env = os.environ.get("CAM_HIGGSFIELD_LIVE", "").strip() in {"1", "true", "yes"}
    want_live = bool(args.live)
    live_allowed = want_live and live_env and enhance
    live_blocked_reason = None
    if want_live and not live_allowed:
        reasons = []
        if not live_env:
            reasons.append("CAM_HIGGSFIELD_LIVE!=1")
        if not enhance:
            reasons.append("need --enhance (switch.cam_enhance act)")
        live_blocked_reason = "; ".join(reasons) or "live blocked"
        errors.append(f"live mode refused: {live_blocked_reason}")

    mode = "live_intent" if live_allowed else "dry_run"
    if not inv["ok"]:
        inv_msg = f"submodule inventory incomplete: {inv['missing_files']}"
        # Empty checkout is expected until `git submodule update --init`.
        # Dry-run / doctor must stay green; live intent still requires sources.
        if mode == "live_intent":
            errors.append(inv_msg)
        else:
            warnings.append(inv_msg)
            inv = {
                **inv,
                "soft": True,
                "note": "empty checkout is dry-run ok; init submodule before live train",
            }
    primary = experiments[0]["experiment"] if experiments else "unknown"

    plan = {
        "ok": not errors,
        "mode": mode,
        "integration": "higgsfield",
        "motor": "motor.higgsfield",
        "hotspot": "hotspot.higgsfield",
        "at": utc_now(),
        "experiment_file": str(exp_path.relative_to(ROOT)) if exp_path.is_relative_to(ROOT) else str(exp_path),
        "experiments": experiments,
        "inventory": inv,
        "nodes": nodes,
        "enhance": enhance,
        "live_requested": want_live,
        "live_env": live_env,
        "live_allowed": live_allowed,
        "live_blocked_reason": live_blocked_reason,
        "spend": {
            "gpu_spend": False if mode == "dry_run" else "intent_only",
            "ssh": False,
            "remote_exec": False,
            "notes": "Phase-1 runner never opens SSH; live only records intent",
        },
        "litserve_handoff": litserve_handoff(primary, dry_run=(mode == "dry_run")),
        "errors": errors,
        "warnings": warnings,
        "next": (
            "pack with scripts/pack-higgsfield-result.py"
            if not errors
            else "fix errors then re-run dry-run"
        ),
    }
    return plan


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--experiment",
        default=str(DEFAULT_EXPERIMENT.relative_to(ROOT)),
        help="path to experiment .py (default: sample fixture)",
    )
    p.add_argument("--nodes", help="optional nodes inventory JSON")
    p.add_argument("--enhance", action="store_true", help="Aaron flipped switch.cam_enhance")
    p.add_argument(
        "--live",
        action="store_true",
        help="request live intent (also needs CAM_HIGGSFIELD_LIVE=1 + --enhance)",
    )
    p.add_argument("--out", help="write plan JSON to file")
    p.add_argument("--doctor", action="store_true", help="alias for dry-run on sample fixture")
    args = p.parse_args()

    if args.doctor:
        args.experiment = str(DEFAULT_EXPERIMENT.relative_to(ROOT))
        args.live = False

    plan = build_plan(args)
    text = json.dumps(plan, indent=2) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if plan.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
