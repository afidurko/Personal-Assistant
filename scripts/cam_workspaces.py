#!/usr/bin/env python3
"""Shared Cam workspace registry helpers for Cline motor integration."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "workspaces" / "registry.json"
SCHEDULES_PATH = ROOT / "config" / "workspaces" / "schedules.json"
TICKETS_DIR = ROOT / "identity" / "persistence" / "tickets"
CLINE_CACHE = ROOT / "identity" / "persistence" / "cline-session-cache.json"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def expand_path(raw: str, base: Path | None = None) -> Path:
    expanded = os.path.expanduser(raw)
    path = Path(expanded)
    if not path.is_absolute():
        path = (base or ROOT) / path
    return path.resolve()


def load_registry() -> dict[str, Any]:
    reg = load_json(REGISTRY_PATH)
    if not reg.get("workspaces"):
        raise FileNotFoundError(f"workspace registry missing or empty: {REGISTRY_PATH}")
    return reg


def list_workspaces(reg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    reg = reg or load_registry()
    return list(reg.get("workspaces") or [])


def get_workspace(workspace_id: str, reg: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = reg or load_registry()
    for ws in list_workspaces(reg):
        if ws["id"] == workspace_id:
            return ws
    raise KeyError(f"unknown workspace id: {workspace_id}")


def resolve_workspace_path(ws: dict[str, Any], base: Path | None = None) -> Path:
    return expand_path(ws["path"], base or ROOT)


def resolve_data_dir(ws: dict[str, Any]) -> Path:
    raw = ws.get("cline_data_dir") or f"~/.cline/data/workspaces/{ws['id']}"
    return expand_path(raw)


def workspace_exists(ws: dict[str, Any]) -> bool:
    path = resolve_workspace_path(ws)
    if not path.exists():
        return False
    # Empty submodule dirs only contain .git or nothing useful
    if path.is_dir():
        entries = [p for p in path.iterdir() if p.name not in {".git", ".gitignore"}]
        return bool(entries)
    return True


def score_workspace(ws_id: str, goal: str, signals: list[dict[str, Any]]) -> int:
    g = (goal or "").lower()
    score = 0
    for sig in signals:
        if sig.get("id") != ws_id:
            continue
        for token in sig.get("match_any") or []:
            if token.lower() in g:
                score += 2 + len(token.split())
    return score


def choose_workspace(
    goal: str = "",
    workspace_id: str | None = None,
    explicit_path: str | None = None,
    role: str | None = None,
    reg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pick a workspace for motor.cline. Explicit path/id always wins."""
    reg = reg or load_registry()
    workspaces = list_workspaces(reg)

    if explicit_path:
        path = expand_path(explicit_path)
        for ws in workspaces:
            try:
                if resolve_workspace_path(ws) == path:
                    return {
                        "workspace": ws,
                        "path": str(path),
                        "reason": "explicit_path_matched_registry",
                        "score": 100,
                    }
            except OSError:
                continue
        return {
            "workspace": {
                "id": "ad-hoc",
                "label": "Ad-hoc path",
                "path": str(path),
                "cline_data_dir": str(
                    expand_path(f"~/.cline/data/workspaces/ad-hoc-{abs(hash(str(path))) % 10_000_000}")
                ),
                "roles_allowed": ["*"],
                "rules": [".clinerules"],
            },
            "path": str(path),
            "reason": "explicit_path_ad_hoc",
            "score": 100,
        }

    if workspace_id:
        ws = get_workspace(workspace_id, reg)
        return {
            "workspace": ws,
            "path": str(resolve_workspace_path(ws)),
            "reason": "explicit_workspace_id",
            "score": 100,
        }

    signals = (reg.get("chooser") or {}).get("signals") or []
    scored: list[tuple[int, dict[str, Any]]] = []
    for ws in workspaces:
        allowed = ws.get("roles_allowed") or ["*"]
        if role and "*" not in allowed and role not in allowed:
            continue
        s = score_workspace(ws["id"], goal, signals)
        if ws.get("primary"):
            s += 1
        if workspace_exists(ws):
            s += 1
        scored.append((s, ws))
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        default_id = reg.get("default_workspace_id") or workspaces[0]["id"]
        ws = get_workspace(default_id, reg)
        return {
            "workspace": ws,
            "path": str(resolve_workspace_path(ws)),
            "reason": "fallback_default",
            "score": 0,
        }

    best_score, best = scored[0]
    if best_score <= 1:
        default_id = reg.get("default_workspace_id") or best["id"]
        ws = get_workspace(default_id, reg)
        return {
            "workspace": ws,
            "path": str(resolve_workspace_path(ws)),
            "reason": "default_low_signal",
            "score": best_score,
            "alternates": [
                {"id": w["id"], "score": s} for s, w in scored[1:4]
            ],
        }

    return {
        "workspace": best,
        "path": str(resolve_workspace_path(best)),
        "reason": "goal_signal_match",
        "score": best_score,
        "alternates": [{"id": w["id"], "score": s} for s, w in scored[1:4]],
    }


def mesh_projects_doc(reg: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = reg or load_registry()
    projects = []
    for ws in list_workspaces(reg):
        projects.append(
            {
                "id": ws["id"],
                "label": ws.get("label"),
                "path": ws.get("path"),
                "remote": ws.get("remote"),
                "default_branch": ws.get("default_branch"),
                "cline_data_dir": ws.get("cline_data_dir"),
                "roles_allowed": ws.get("roles_allowed"),
                "exists": workspace_exists(ws),
                "resolved_path": str(resolve_workspace_path(ws)),
            }
        )
    return {
        "namespace": "mesh/projects",
        "source": "config/workspaces/registry.json",
        "default_workspace_id": reg.get("default_workspace_id"),
        "projects": projects,
    }


def mesh_cline_workspaces_doc(reg: dict[str, Any] | None = None) -> dict[str, Any]:
    projects = mesh_projects_doc(reg)
    cache = load_json(CLINE_CACHE)
    return {
        "namespace": "mesh/cline",
        "workspaces": projects["projects"],
        "last_session": cache.get("last_session"),
        "schedules": cache.get("schedules") or [],
        "notes": cache.get("notes") or [],
        "cross_workspace": True,
        "effector": "cline",
    }


_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def slugify(text: str) -> str:
    s = _SLUG_RE.sub("-", (text or "run").strip().lower()).strip("-")
    return (s[:48] or "run")
