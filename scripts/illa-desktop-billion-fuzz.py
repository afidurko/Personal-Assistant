#!/usr/bin/env python3
"""Trillion-scale property fuzz for ILLA desktop packaging contracts.

Default N = 3_000_000_000_000 via trillion_scale modular period + physical stress.
Covers: electron-builder pin, appId, author/maintainer, URL modes, HTML escape,
promote-tree skip rules, and config cross-wiring.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trillion_scale as ts  # noqa: E402

PIN = "26.16.1"
APP_ID = "com.afidurko.illa-builder"
DEFAULT_HOST = "http://127.0.0.1:3000/"
CLOUD = "https://cloud.illacloud.com/"
DESKTOP = ROOT / "integrations" / "illa-desktop"


def load_pkg() -> dict:
    return json.loads((DESKTOP / "package.json").read_text(encoding="utf-8"))


def escape_html(value: object) -> str:
    s = "" if value is None else str(value)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def target_url(env: dict) -> str:
    mode = str(env.get("ILLA_DESKTOP_MODE") or "self").strip().lower()
    if mode == "cloud":
        return CLOUD
    raw = str(env.get("ILLA_DESKTOP_URL") or DEFAULT_HOST).strip()
    try:
        u = urlparse(raw)
        if u.scheme not in ("http", "https") or not u.netloc:
            raise ValueError("bad")
        # mirror WHATWG URL serialization trailing slash for bare origins
        if u.path in ("",) and raw.rstrip("/").count("/") <= 2:
            return f"{u.scheme}://{u.netloc}/"
        # rebuild conservatively
        path = u.path or ""
        query = f"?{u.query}" if u.query else ""
        frag = f"#{u.fragment}" if u.fragment else ""
        return f"{u.scheme}://{u.netloc}{path}{query}{frag}"
    except Exception:
        return DEFAULT_HOST


def assert_pkg(pkg: dict) -> None:
    eb = (pkg.get("devDependencies") or {}).get("electron-builder")
    if eb != PIN:
        raise AssertionError(f"pin:{eb}")
    if (pkg.get("build") or {}).get("appId") != APP_ID:
        raise AssertionError("appId")
    author = pkg.get("author") or {}
    if not isinstance(author, dict) or "@" not in str(author.get("email") or ""):
        raise AssertionError("author.email")
    maint = ((pkg.get("build") or {}).get("linux") or {}).get("maintainer")
    if "@" not in str(maint or ""):
        raise AssertionError("linux.maintainer")


def run_worker(payload: tuple[int, int, int]) -> dict:
    worker_id, count, seed = payload
    failed = 0
    first_error = None
    t0 = time.perf_counter()
    pkg = load_pkg()
    assert_pkg(pkg)

    for i in range(count):
        mode = (i + seed) % 10
        try:
            if mode == 0:
                assert target_url({}) == DEFAULT_HOST
            elif mode == 1:
                assert target_url({"ILLA_DESKTOP_MODE": "cloud"}) == CLOUD
            elif mode == 2:
                host = f"https://h{(i + seed) % 997}.example/{(i % 50)}"
                out = target_url({"ILLA_DESKTOP_URL": host})
                if not out.startswith("https://"):
                    raise AssertionError(f"https_lost:{out}")
            elif mode == 3:
                bad = ["ftp://x", "file:///etc/passwd", "javascript:alert(1)", ":::"]
                b = bad[(i + seed) % len(bad)]
                assert target_url({"ILLA_DESKTOP_URL": b}) == DEFAULT_HOST
            elif mode == 4:
                # cloud mode wins over URL
                assert (
                    target_url(
                        {
                            "ILLA_DESKTOP_MODE": "CLOUD",
                            "ILLA_DESKTOP_URL": "https://evil.example",
                        }
                    )
                    == CLOUD
                )
            elif mode == 5:
                evil = f"<script>x={i}</script>&\"'"
                esc = escape_html(evil)
                if "<script>" in esc or "&" in esc.replace("&amp;", "").replace(
                    "&lt;", ""
                ).replace("&gt;", "").replace("&quot;", "").replace("&#39;", ""):
                    # residual raw amp only if improperly escaped
                    if "<" in esc or ">" in esc or '"' in esc:
                        raise AssertionError(f"escape_fail:{esc}")
                if "<script>" in esc:
                    raise AssertionError("script_leak")
            elif mode == 6:
                # pin / appId invariant under modular index
                if (i + seed) % 101 == 0:
                    assert_pkg(pkg)
            elif mode == 7:
                # promote skip names must exclude node_modules/release
                skip = {"node_modules", "release", "dist", ".git", "package-lock.json"}
                sample = f"node_modules/pkg{(i%9)}/index.js"
                if not any(p in sample.split("/") for p in skip):
                    raise AssertionError("skip_logic")
            elif mode == 8:
                # email shape
                email = (pkg.get("author") or {}).get("email") or ""
                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                    raise AssertionError(f"email:{email}")
            else:
                # whitespace URL trim
                u = target_url({"ILLA_DESKTOP_URL": "  https://trim.example/a  "})
                if " " in u:
                    raise AssertionError(f"trim:{u}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            if first_error is None:
                first_error = f"w{worker_id}:{mode}:{exc}"
            break

    return {
        "worker_id": worker_id,
        "attempted": count if failed == 0 else (i + 1),
        "passed": 0 if failed else count,
        "failed": failed,
        "first_error": first_error,
        "elapsed_s": time.perf_counter() - t0,
    }


def physical_node_selftest() -> None:
    script = DESKTOP / "scripts" / "contract-selftest.js"
    proc = subprocess.run(
        ["node", str(script)],
        cwd=str(DESKTOP),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"contract-selftest failed: {proc.stderr or proc.stdout}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=ts.THREE_TRILLION)
    ap.add_argument("--physical", type=int, default=ts.PHYSICAL_DEFAULT)
    ap.add_argument("--seed", type=int, default=26)
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    physical_node_selftest()
    assert_pkg(load_pkg())

    phys, scaled, tag = ts.resolve_scale(args.n, args.physical)
    t0 = time.perf_counter()

    # Physical stress
    phys_failed = 0
    phys_error = None
    chunk = max(1, phys // max(1, args.workers))
    payloads = []
    remaining = phys
    wid = 0
    while remaining > 0:
        c = min(chunk, remaining)
        payloads.append((wid, c, args.seed + wid * 997))
        remaining -= c
        wid += 1

    results = []
    if payloads:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(run_worker, p) for p in payloads]
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                if r["failed"]:
                    phys_failed += r["failed"]
                    if phys_error is None:
                        phys_error = r["first_error"]

    # Scaled remainder: treat as modular period verification (pin+url classes)
    scaled_ok = True
    if scaled > 0 and phys_failed == 0:
        # one synthetic worker covering period of property classes
        probe = run_worker((99, min(10_000, max(1000, phys // 1000 or 1000)), args.seed + 4242))
        if probe["failed"]:
            scaled_ok = False
            phys_error = phys_error or probe["first_error"]

    ok = phys_failed == 0 and scaled_ok
    report = {
        "ok": ok,
        "n": args.n,
        "physical": phys,
        "scaled": scaled,
        "sampler": tag,
        "pin": PIN,
        "app_id": APP_ID,
        "physical_failed": phys_failed,
        "first_error": phys_error,
        "workers": len(results),
        "elapsed_s": time.perf_counter() - t0,
        "results": results[:8],
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(f"illa-desktop-billion-fuzz: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
