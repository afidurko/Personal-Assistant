#!/usr/bin/env python3
"""Cam motor.cline runner — launch Cline in a registered workspace.

Resolves workspace from registry / goal signals, isolates CLINE_DATA_DIR,
optionally binds a nulltickets-shaped ticket, streams --json events, and
records distillates via sync-cline-session.py helpers.

Examples:
  python3 scripts/run-cline.py doctor
  python3 scripts/run-cline.py --goal "fix connectome" --dry-run "echo hi"
  python3 scripts/run-cline.py --workspace-id cline --yolo "run doctor"
  python3 scripts/run-cline.py --team-name cam-mesh --secondary cline,jarvis "coordinate"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import cam_workspaces as cw  # noqa: E402


def find_cline_bin() -> list[str]:
    """Return argv prefix to invoke cline CLI."""
    which = shutil.which("cline")
    if which:
        return [which]
    bun = shutil.which("bun")
    submodule_cli = ROOT / "integrations" / "cline" / "package.json"
    if bun and submodule_cli.exists():
        # Prefer published binary; fall back to source CLI when submodule populated
        return [bun, "run", "--cwd", str(ROOT / "integrations" / "cline"), "cli", "--"]
    return ["cline"]  # hope PATH later; doctor will fail clearly


def write_ticket(
    *,
    ticket_id: str,
    workspace_id: str,
    workspace_path: str,
    prompt: str,
    mode: str,
    status: str,
    events: list[dict],
    exit_code: int | None,
    team_name: str | None,
) -> Path:
    now = datetime.now(timezone.utc).isoformat()
    ticket = {
        "id": ticket_id,
        "namespace": "tickets/cline",
        "source": "scripts/run-cline.py",
        "created_at": now,
        "updated_at": now,
        "status": status,
        "workspace_id": workspace_id,
        "workspace_path": workspace_path,
        "mode": mode,
        "prompt": prompt,
        "team_name": team_name,
        "exit_code": exit_code,
        "events": events[-200:],  # cap
        "nulltickets": {
            "ready_for_put": True,
            "store_keys": ["mesh/cline", "mesh/runs", f"tickets/cline/{ticket_id}"],
        },
    }
    pending = cw.TICKETS_DIR / "pending"
    done = cw.TICKETS_DIR / "done"
    pending.mkdir(parents=True, exist_ok=True)
    done.mkdir(parents=True, exist_ok=True)
    path = (done if status in {"completed", "failed", "killed"} else pending) / f"{ticket_id}.json"
    # remove from pending if moving
    old = pending / f"{ticket_id}.json"
    if path.parent == done and old.exists():
        old.unlink()
    cw.write_json(path, ticket)
    # also drop a mesh/runs distillate
    runs_dir = ROOT / "vault" / "10-Mesh-Distillates" / "cline-runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    cw.write_json(
        runs_dir / f"{ticket_id}.json",
        {
            "namespace": "mesh/runs",
            "ticket_id": ticket_id,
            "workspace_id": workspace_id,
            "status": status,
            "mode": mode,
            "prompt": prompt,
            "exit_code": exit_code,
            "updated_at": now,
            "event_count": len(events),
        },
    )
    return path


def record_session(workspace_path: str, mode: str, summary: str, note: str = "") -> None:
    script = ROOT / "scripts" / "sync-cline-session.py"
    cmd = [
        sys.executable,
        str(script),
        "record",
        "--workspace",
        workspace_path,
        "--mode",
        mode,
        "--summary",
        summary,
    ]
    if note:
        cmd.extend(["--note", note])
    subprocess.run(cmd, check=False)


def track_instinct_run(workspace_id: str, prompt: str, status: str, exit_code: int,
                       ticket_id: str | None) -> None:
    """Drop the run into Cam Instinct's follow-through ledger (motor.instinct).
    Failures open a coding job; bookkeeping must never break the run itself."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import instinct  # noqa: WPS433

        instinct.track_cline_run(workspace_id, prompt, status, exit_code, ticket_id)
    except Exception:
        pass


def build_env(data_dir: Path, kill: bool) -> dict[str, str]:
    env = os.environ.copy()
    data_dir.mkdir(parents=True, exist_ok=True)
    env["CLINE_DATA_DIR"] = str(data_dir)
    if kill:
        env["CAM_KILL_SWITCH"] = "1"
    # Point MCP at Cam server when configured
    mcp_cmd = env.get("CAM_MCP_COMMAND")
    if not mcp_cmd:
        env["CAM_MCP_COMMAND"] = f"{sys.executable} {ROOT / 'scripts' / 'cam-mcp-server.py'}"
    return env


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("prompt", nargs="?", default="", help="Cline prompt (omit for doctor)")
    p.add_argument("--workspace-id", help="registry workspace id")
    p.add_argument("--path", help="explicit workspace filesystem path")
    p.add_argument("--goal", default="", help="chooser signal text (defaults to prompt)")
    p.add_argument("--role", default="coding", help="Cam role invoking motor.cline")
    p.add_argument("--mode", choices=["act", "plan", "headless", "team", "doctor"], default="headless")
    p.add_argument("--plan", action="store_true", help="pass --plan to cline")
    p.add_argument("--yolo", action="store_true", help="auto-approve tools")
    p.add_argument("--json", action="store_true", default=True, help="NDJSON events (default on)")
    p.add_argument("--no-json", action="store_true", help="disable --json")
    p.add_argument("--dry-run", action="store_true", help="print argv/env; do not execute")
    p.add_argument("--doctor", action="store_true", help="run cline doctor in workspace")
    p.add_argument("--kill", action="store_true", help="simulate kill switch (refuse motor)")
    p.add_argument("--no-autonomy", action="store_true", help="require approvals (no --yolo)")
    p.add_argument("--team-name", help="cline --team-name for multi-agent teams")
    p.add_argument(
        "--secondary",
        default="",
        help="comma-separated secondary workspace ids for team prompt context",
    )
    p.add_argument("--timeout", type=int, default=0, help="optional seconds timeout")
    p.add_argument("--ticket-id", help="reuse/override ticket id")
    p.add_argument("--no-ticket", action="store_true", help="skip ticket binding")
    args = p.parse_args()

    if args.kill:
        print(
            json.dumps(
                {
                    "accepted": False,
                    "reason": "switch.kill act — motor.cline silenced",
                    "motor": "motor.cline",
                },
                indent=2,
            )
        )
        return 2

    goal = args.goal or args.prompt or ""
    choice = cw.choose_workspace(
        goal=goal,
        workspace_id=args.workspace_id,
        explicit_path=args.path,
        role=args.role,
    )
    ws = choice["workspace"]
    workspace_path = Path(choice["path"])
    data_dir = cw.resolve_data_dir(ws) if ws.get("id") != "ad-hoc" else Path(ws["cline_data_dir"]).expanduser()

    secondary_paths = []
    for sid in [s.strip() for s in args.secondary.split(",") if s.strip()]:
        try:
            sw = cw.get_workspace(sid)
            secondary_paths.append(
                {"id": sid, "path": str(cw.resolve_workspace_path(sw)), "exists": cw.workspace_exists(sw)}
            )
        except KeyError:
            secondary_paths.append({"id": sid, "error": "unknown_workspace"})

    prompt = args.prompt
    if secondary_paths and prompt:
        prompt = (
            f"{prompt}\n\nSecondary workspaces for coordination:\n"
            + "\n".join(
                f"- {s.get('id')}: {s.get('path')} (exists={s.get('exists', False)})"
                for s in secondary_paths
            )
        )

    use_doctor = args.doctor or args.mode == "doctor" or not prompt
    cline = find_cline_bin()
    cmd = list(cline)

    if use_doctor:
        cmd.append("doctor")
        mode = "doctor"
    else:
        if not prompt:
            print("prompt required unless --doctor", file=sys.stderr)
            return 1
        if not args.no_json:
            cmd.append("--json")
        cmd.extend(["--cwd", str(workspace_path)])
        if args.plan or args.mode == "plan":
            cmd.append("--plan")
            mode = "plan"
        else:
            mode = "act" if args.mode == "act" else "headless"
        if args.team_name:
            cmd.extend(["--team-name", args.team_name])
            mode = "team"
        if args.yolo or (not args.no_autonomy and mode != "plan"):
            cmd.append("--yolo")
        if args.timeout:
            cmd.extend(["--timeout", str(args.timeout)])
        cmd.append(prompt)

    env = build_env(data_dir, kill=False)
    ticket_id = args.ticket_id or f"cline-{cw.slugify(ws.get('id', 'ws'))}-{uuid.uuid4().hex[:10]}"
    meta = {
        "accepted": True,
        "motor": "motor.cline",
        "workspace_choice": choice,
        "data_dir": str(data_dir),
        "cwd": str(workspace_path),
        "argv": cmd,
        "ticket_id": None if args.no_ticket else ticket_id,
        "secondary": secondary_paths,
        "role": args.role,
    }

    if args.dry_run:
        meta["dry_run"] = True
        print(json.dumps(meta, indent=2))
        return 0

    if not workspace_path.exists():
        print(json.dumps({**meta, "accepted": False, "reason": f"workspace missing: {workspace_path}"}, indent=2))
        return 1

    events: list[dict] = []
    events.append({"type": "cam_start", "at": datetime.now(timezone.utc).isoformat(), "meta": meta})

    if not args.no_ticket:
        write_ticket(
            ticket_id=ticket_id,
            workspace_id=ws.get("id", "ad-hoc"),
            workspace_path=str(workspace_path),
            prompt=prompt or "doctor",
            mode=mode,
            status="running",
            events=events,
            exit_code=None,
            team_name=args.team_name,
        )

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workspace_path if workspace_path.is_dir() else workspace_path.parent),
            env=env,
            capture_output=True,
            text=True,
            timeout=args.timeout or None,
        )
    except FileNotFoundError:
        err = {"type": "cam_error", "error": "cline_binary_not_found", "argv": cmd}
        events.append(err)
        if not args.no_ticket:
            write_ticket(
                ticket_id=ticket_id,
                workspace_id=ws.get("id", "ad-hoc"),
                workspace_path=str(workspace_path),
                prompt=prompt or "doctor",
                mode=mode,
                status="failed",
                events=events,
                exit_code=127,
                team_name=args.team_name,
            )
        print(json.dumps({**meta, "accepted": False, "reason": "cline not installed on PATH", "events": events}, indent=2))
        return 127
    except subprocess.TimeoutExpired as exc:
        events.append({"type": "cam_timeout", "timeout": args.timeout})
        if not args.no_ticket:
            write_ticket(
                ticket_id=ticket_id,
                workspace_id=ws.get("id", "ad-hoc"),
                workspace_path=str(workspace_path),
                prompt=prompt or "doctor",
                mode=mode,
                status="failed",
                events=events,
                exit_code=124,
                team_name=args.team_name,
            )
        print(json.dumps({**meta, "accepted": False, "reason": "timeout", "partial": str(exc)}, indent=2))
        return 124

    # Parse NDJSON stdout when possible
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"type": "cline_stdout", "text": line[:2000]})
    if proc.stderr:
        events.append({"type": "cline_stderr", "text": proc.stderr[-4000:]})

    status = "completed" if proc.returncode == 0 else "failed"
    events.append(
        {
            "type": "cam_end",
            "at": datetime.now(timezone.utc).isoformat(),
            "exit_code": proc.returncode,
            "status": status,
        }
    )

    if not args.no_ticket:
        ticket_path = write_ticket(
            ticket_id=ticket_id,
            workspace_id=ws.get("id", "ad-hoc"),
            workspace_path=str(workspace_path),
            prompt=prompt or "doctor",
            mode=mode,
            status=status,
            events=events,
            exit_code=proc.returncode,
            team_name=args.team_name,
        )
    else:
        ticket_path = None

    summary = f"{status} exit={proc.returncode} ws={ws.get('id')}"
    record_session(str(workspace_path), mode, summary, note=f"ticket={ticket_id}")
    track_instinct_run(ws.get("id", "ad-hoc"), prompt, status, proc.returncode, ticket_id)

    out = {
        **meta,
        "exit_code": proc.returncode,
        "status": status,
        "ticket_path": str(ticket_path) if ticket_path else None,
        "event_count": len(events),
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }
    print(json.dumps(out, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
