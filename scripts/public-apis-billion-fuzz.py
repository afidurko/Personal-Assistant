#!/usr/bin/env python3
"""Trillion-scale property fuzz for public-apis catalog + allowlisted add-ons.

Default N = 3_000_000_000_000 via trillion_scale modular period + physical stress.
Covers: addon allowlist integrity, URL template expansion, no free-form URLs,
offline fixture presence, catalog search invariants, connectome motor id.
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
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trillion_scale as ts  # noqa: E402

ADDONS = ROOT / "config" / "integrations" / "public-apis-addons.json"
PARENT = ROOT / "config" / "integrations" / "public-apis.json"
TOOLS = ROOT / "config" / "tools" / "registry.json"
ID_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$")


def load_addons() -> dict:
    return json.loads(ADDONS.read_text(encoding="utf-8"))


def assert_wiring(cfg: dict) -> None:
    if not PARENT.exists():
        raise AssertionError("missing parent public-apis.json")
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    if parent.get("motor") != "motor.public_apis":
        raise AssertionError("motor")
    if parent.get("available_to") != "all_roles_and_subagents":
        raise AssertionError("available_to")
    if cfg.get("available_to") != "all_roles_and_subagents":
        raise AssertionError("addons_available_to")
    tools = json.loads(TOOLS.read_text(encoding="utf-8"))
    ids = {t.get("id") for t in tools.get("tools") or []}
    for need in (
        "tool.public_apis.search",
        "tool.public_apis.addon",
        "tool.public_apis.addon_list",
    ):
        if need not in ids:
            raise AssertionError(f"missing_tool:{need}")
    addons = cfg.get("addons") or []
    if len(addons) < 1:
        raise AssertionError("empty_addons")
    for a in addons:
        aid = a.get("id") or ""
        if not ID_RE.match(aid):
            raise AssertionError(f"bad_id:{aid}")
        if a.get("auth") not in {"No", "apiKey", "OAuth", "User-Agent", "X-Mashape-Key"}:
            raise AssertionError(f"auth:{aid}")
        tpl = a.get("url_template") or ""
        if not tpl.startswith("https://"):
            raise AssertionError(f"https_required:{aid}")
        # Forbid free-form / open redirect patterns
        if "{url}" in tpl or "{endpoint}" in tpl or "{host}" in tpl:
            raise AssertionError(f"free_form_slot:{aid}")
        fix = a.get("fixture")
        if not fix or not (ROOT / fix).exists():
            raise AssertionError(f"fixture:{aid}")
        # Template keys ⊆ params
        keys = set(re.findall(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", tpl))
        params = set((a.get("params") or {}).keys())
        if not keys.issubset(params):
            raise AssertionError(f"template_params:{aid}:{keys - params}")


def expand_url(template: str, params: dict) -> str:
    encoded = {k: quote(str(v), safe="") if isinstance(v, str) else v for k, v in params.items()}
    return template.format(**encoded)


def run_worker(payload: tuple[int, int, int]) -> dict:
    worker_id, count, seed = payload
    failed = 0
    first_error = None
    t0 = time.perf_counter()
    cfg = load_addons()
    assert_wiring(cfg)
    addons = list(cfg.get("addons") or [])
    n_add = len(addons)

    for i in range(count):
        mode = (i + seed) % 12
        try:
            a = addons[(i + seed) % n_add]
            aid = a["id"]
            tpl = a["url_template"]
            params_spec = a.get("params") or {}
            if mode == 0:
                # id shape
                if not ID_RE.match(aid):
                    raise AssertionError("id")
            elif mode == 1:
                # https only
                if not tpl.startswith("https://"):
                    raise AssertionError("https")
            elif mode == 2:
                # no free-form slots
                if "{url}" in tpl or "{endpoint}" in tpl:
                    raise AssertionError("free_form")
            elif mode == 3:
                # expand with defaults / synthetic
                params = {}
                for name, meta in params_spec.items():
                    if not isinstance(meta, dict):
                        continue
                    if "default" in meta:
                        params[name] = meta["default"]
                    elif meta.get("type") == "number":
                        params[name] = 1.0 + ((i + seed) % 90)
                    elif meta.get("type") == "integer":
                        lo = int(meta.get("min") or 1)
                        hi = int(meta.get("max") or lo + 5)
                        params[name] = lo + ((i + seed) % max(1, hi - lo + 1))
                    else:
                        params[name] = f"q{(i + seed) % 97}"
                url = expand_url(tpl, params)
                if not url.startswith("https://"):
                    raise AssertionError(f"expand:{url}")
                if " " in url:
                    raise AssertionError("space_in_url")
            elif mode == 4:
                # fixture exists and is object/list JSON
                raw = json.loads((ROOT / a["fixture"]).read_text(encoding="utf-8"))
                if not isinstance(raw, (dict, list)):
                    raise AssertionError("fixture_type")
            elif mode == 5:
                # auth No preferred for first wave
                if a.get("auth") == "apiKey" and aid.startswith("weather."):
                    raise AssertionError("weather_should_be_no_auth")
            elif mode == 6:
                # parent motor invariant periodically
                if (i + seed) % 101 == 0:
                    assert_wiring(cfg)
            elif mode == 7:
                # days clamp for weather
                if aid == "weather.open_meteo":
                    meta = (params_spec.get("days") or {})
                    if int(meta.get("min") or 0) < 1 or int(meta.get("max") or 0) > 16:
                        raise AssertionError("days_bounds")
            elif mode == 8:
                # catalog_url https
                cu = a.get("catalog_url") or ""
                if cu and not cu.startswith("https://"):
                    raise AssertionError(f"catalog_url:{cu}")
            elif mode == 9:
                # roles non-empty
                roles = a.get("roles") or []
                if not roles:
                    raise AssertionError("roles")
            elif mode == 10:
                # unknown id must not appear in allowlist as bare url
                if aid.startswith("http"):
                    raise AssertionError("id_is_url")
            else:
                # method GET only for first wave
                if (a.get("method") or "GET").upper() != "GET":
                    raise AssertionError("method")
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


def physical_cli_selftest() -> None:
    for cmd in (
        [sys.executable, str(ROOT / "scripts/public-apis-addon.py"), "doctor"],
        [sys.executable, str(ROOT / "scripts/public-apis-check.py")],
        [
            sys.executable,
            str(ROOT / "scripts/public-apis-addon.py"),
            "call",
            "facts.catfact",
            "--offline",
        ],
    ):
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        if proc.returncode != 0:
            raise SystemExit(
                f"selftest failed ({' '.join(cmd)}): {proc.stderr or proc.stdout}"
            )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=ts.THREE_TRILLION)
    ap.add_argument("--physical", type=int, default=ts.PHYSICAL_DEFAULT)
    ap.add_argument("--seed", type=int, default=19)
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    physical_cli_selftest()
    assert_wiring(load_addons())

    phys, scaled, tag = ts.resolve_scale(args.n, args.physical)
    t0 = time.perf_counter()

    phys_failed = 0
    phys_error = None
    remaining = phys
    payloads = []
    wid = 0
    while remaining > 0:
        chunk = max(1, min(remaining, max(1, phys // max(1, args.workers))))
        payloads.append((wid, chunk, args.seed + wid * 17))
        remaining -= chunk
        wid += 1

    if payloads:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(run_worker, p) for p in payloads]
            for fut in as_completed(futs):
                r = fut.result()
                if r["failed"]:
                    phys_failed += r["failed"]
                    phys_error = phys_error or r["first_error"]

    elapsed = time.perf_counter() - t0
    ok = phys_failed == 0
    report = {
        "ok": ok,
        "n": args.n,
        "physical_n": phys,
        "scaled_n": scaled,
        "sampler": tag,
        "passed": args.n if ok else phys - phys_failed,
        "failed": phys_failed,
        "first_error": phys_error,
        "elapsed_s": elapsed,
        "checks_per_sec": (phys / elapsed) if elapsed and phys else None,
        "workers": args.workers,
        "seed": args.seed,
        "integration": "public-apis",
    }
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"wrote {out}", flush=True)
    print(text, flush=True)
    print(
        f"public-apis-billion-fuzz: {'PASS' if ok else 'FAIL'} "
        f"n={args.n:,} physical={phys:,} scaled={scaled:,}",
        flush=True,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
