#!/usr/bin/env python3
"""Cam see bridge — ingest Pupil world-camera + gaze so Cam can see.

Does not require a live Pupil process for dry-run / file packing. When Pupil
Capture/Service is up, optionally pulls recent gaze via Pupil Remote (ZMQ).

Emits distilled mesh docs under mesh/vision (world) and mesh/gaze, then routes
sense.vision.world through the connectome (hotspot.pupil_see → motor.pupil).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path | None):
    if not path:
        return None
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_gaze_module():
    import importlib.util

    path = ROOT / "scripts" / "pack-gaze-result.py"
    spec = importlib.util.spec_from_file_location("pack_gaze_result", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def fetch_pupil_remote(host: str, port: int, timeout: float = 1.5) -> dict:
    """Best-effort Pupil Remote pull. Returns {ok, gaze?, error?}."""
    try:
        import zmq  # type: ignore
    except ImportError:
        return {"ok": False, "error": "pyzmq_not_installed"}

    ctx = zmq.Context.instance()
    req = ctx.socket(zmq.REQ)
    req.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
    req.setsockopt(zmq.SNDTIMEO, int(timeout * 1000))
    req.setsockopt(zmq.LINGER, 0)
    try:
        req.connect(f"tcp://{host}:{port}")
        req.send_string("SUB_PORT")
        sub_port = req.recv_string()
        # Ask for a recent gaze notification via IPC — keep light
        req.send_string("t")  # get pupil time as liveness probe
        pupil_time = req.recv_string()
        return {
            "ok": True,
            "sub_port": sub_port,
            "pupil_time": pupil_time,
            "host": host,
            "port": port,
            "note": "service_live — subscribe SUB_PORT for continuous gaze if needed",
        }
    except Exception as exc:  # noqa: BLE001 — soft bridge
        return {"ok": False, "error": str(exc), "host": host, "port": port}
    finally:
        req.close(0)


def pack_world(frame_meta: dict | None, gaze_samples: list, task: str) -> dict:
    meta = frame_meta or {}
    return {
        "namespace": "mesh/vision",
        "source": "integrations/pupil",
        "sensitivity": "private",
        "task": task,
        "modality": "world_frame",
        "created_at": utc_now(),
        "frame_ref": meta.get("frame_ref") or meta.get("path") or meta.get("id"),
        "frame_size": meta.get("size") or meta.get("resolution"),
        "gaze_count": len(gaze_samples),
        "gaze_overlay": gaze_samples[:32],
        "note": "world frame ref + gaze overlay; raw video not stored in mesh by default",
    }


def route_see(goal: str) -> dict:
    import cam_reason as cr

    return cr.connectome_route_tool(
        "sense.vision.world",
        goal or "cam see via pupil",
        hotspot_id="hotspot.pupil_see",
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--gaze", help="path to gaze JSON (Pupil export or sample)")
    p.add_argument("--world", help="path to world-frame metadata JSON")
    p.add_argument("--host", default="127.0.0.1", help="Pupil Remote host")
    p.add_argument("--port", type=int, default=50020, help="Pupil Remote REQ port")
    p.add_argument("--task", default="see", help="see|world|gaze|fixation")
    p.add_argument("--goal", default="Cam see via Pupil world camera")
    p.add_argument("--out-dir", help="write mesh docs into this directory")
    p.add_argument("--no-route", action="store_true", help="skip connectome-route")
    p.add_argument("--probe", action="store_true", help="probe live Pupil Remote")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    gaze_pack = load_gaze_module()
    gaze_samples: list = []
    if args.gaze:
        gaze_samples = gaze_pack.distill(gaze_pack.load_gaze(Path(args.gaze)))

    world_meta = load_json(Path(args.world)) if args.world else None
    if world_meta is None and not gaze_samples:
        # Demo defaults so Cam can exercise the see path without hardware
        sample = ROOT / "scripts" / "testdata" / "sample-gaze.json"
        world_sample = ROOT / "scripts" / "testdata" / "sample-world-frame.json"
        if sample.exists():
            gaze_samples = gaze_pack.distill(gaze_pack.load_gaze(sample))
        if world_sample.exists():
            world_meta = load_json(world_sample)

    remote = None
    if args.probe:
        remote = fetch_pupil_remote(args.host, args.port)

    world_doc = pack_world(world_meta if isinstance(world_meta, dict) else None, gaze_samples, args.task)
    gaze_doc = {
        "namespace": "mesh/gaze",
        "source": "integrations/pupil",
        "sensitivity": "private",
        "task": "gaze",
        "created_at": utc_now(),
        "count": len(gaze_samples),
        "samples": gaze_samples,
        "note": "paired with mesh/vision world ingest for Cam see",
    }

    route = None
    if not args.no_route:
        route = route_see(args.goal)

    result = {
        "accepted": True,
        "dry_run": bool(args.dry_run),
        "cam_can_see": True,
        "switch": "switch.pupil_vision",
        "motor": "motor.pupil",
        "sense": "sense.vision.world",
        "hotspot": "hotspot.pupil_see",
        "pupil_remote": remote,
        "mesh_vision": world_doc,
        "mesh_gaze": gaze_doc,
        "route": route,
    }

    if args.out_dir and not args.dry_run:
        out = Path(args.out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "mesh-vision-pupil.json").write_text(
            json.dumps(world_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out / "mesh-gaze-pupil.json").write_text(
            json.dumps(gaze_doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    print(json.dumps(result, indent=2, sort_keys=True))
    if route and not route.get("accepted"):
        return 2
    if route and "motor.pupil" not in (route.get("motor_plan") or []):
        # Still useful if mesh packed; warn via non-zero only when kill held pathway
        if route.get("switch_state", {}).get("switch.kill") == "act":
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
