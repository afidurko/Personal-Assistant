#!/usr/bin/env python3
"""HTTP gaze bridge for the AR card battle pupil UI.

Streams Cam Pupil-normalized gaze (`norm_pos`) to the browser so the viz can
use sense.vision.gaze / integrations/pupil without ZMQ in the page.

Modes:
  --fixture PATH   loop sample gaze JSON (offline demo)
  --file PATH      serve latest gaze JSON written by pupil-see / Capture export
  --probe          try Pupil Remote (REQ 50020) for liveness only

Browser: GET http://127.0.0.1:8766/gaze  →  {ok, norm_pos:[x,y], confidence}
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


class GazeState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.payload = {
            "ok": False,
            "source": "none",
            "norm_pos": [0.5, 0.5],
            "confidence": 0.0,
            "note": "waiting",
        }

    def set(self, **kwargs) -> None:
        with self.lock:
            self.payload.update(kwargs)
            self.payload["ok"] = True
            self.payload["ts"] = time.time()

    def get(self) -> dict:
        with self.lock:
            return dict(self.payload)


STATE = GazeState()


def load_samples(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("gaze", "gaze_data", "samples", "data", "points"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    raise ValueError("unsupported gaze JSON")


def fixture_loop(path: Path, hz: float) -> None:
    samples = load_samples(path)
    if not samples:
        STATE.set(ok=False, note="empty_fixture", source="fixture")
        return
    i = 0
    dt = 1.0 / max(hz, 1.0)
    while True:
        item = samples[i % len(samples)]
        norm = item.get("norm_pos") or item.get("norm") or [0.5, 0.5]
        conf = item.get("confidence") or item.get("score") or 0.9
        STATE.set(
            source="fixture",
            norm_pos=list(norm),
            confidence=float(conf),
            note=str(path),
        )
        i += 1
        time.sleep(dt)


def file_watch(path: Path, hz: float) -> None:
    dt = 1.0 / max(hz, 1.0)
    while True:
        try:
            if path.exists():
                samples = load_samples(path)
                if samples:
                    item = samples[-1]
                    norm = item.get("norm_pos") or item.get("norm") or [0.5, 0.5]
                    conf = item.get("confidence") or item.get("score") or 0.0
                    STATE.set(
                        source="file",
                        norm_pos=list(norm),
                        confidence=float(conf) if conf is not None else 0.0,
                        note=str(path),
                    )
        except Exception as exc:  # noqa: BLE001
            STATE.set(ok=False, source="file", note=str(exc))
        time.sleep(dt)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:  # quieter
        return

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/health"):
            body = json.dumps({"ok": True, "service": "pupil-gaze-bridge"}).encode()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/gaze":
            body = json.dumps(STATE.get()).encode()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self._cors()
        self.end_headers()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8766)
    p.add_argument(
        "--fixture",
        default=str(ROOT / "scripts/testdata/sample-gaze.json"),
        help="loop this gaze JSON (default sample)",
    )
    p.add_argument("--file", help="watch this gaze JSON instead of fixture loop")
    p.add_argument("--hz", type=float, default=30.0)
    p.add_argument("--probe", action="store_true", help="probe Pupil Remote liveness")
    args = p.parse_args()

    if args.probe:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "pupil_see", ROOT / "scripts" / "pupil-see.py"
            )
            mod = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(mod)
            print(json.dumps(mod.fetch_pupil_remote("127.0.0.1", 50020), indent=2))
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"ok": False, "error": str(exc)}))

    if args.file:
        threading.Thread(target=file_watch, args=(Path(args.file), args.hz), daemon=True).start()
    else:
        threading.Thread(
            target=fixture_loop, args=(Path(args.fixture), args.hz), daemon=True
        ).start()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        json.dumps(
            {
                "listening": f"http://{args.host}:{args.port}/gaze",
                "mode": "file" if args.file else "fixture",
                "source": args.file or args.fixture,
            }
        ),
        flush=True,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
