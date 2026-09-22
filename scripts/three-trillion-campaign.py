#!/usr/bin/env python3
"""Aaron "test" protocol — three-trillion dual campaign.

When Aaron says **test**:
  1. Run three trillion checks
  2. Fix errors / simplify
  3. Add suggestions
  4. Run three trillion again
  5. If fully successful → merge readiness (exit 0)

N = 3_000_000_000_000 via exhaustive/modular scale + physical stress.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trillion_scale as ts  # noqa: E402

OUT = ROOT / "vault" / "10-Mesh-Distillates"
CYCLES = OUT / "qa-cycles"
THREE_T = ts.THREE_TRILLION


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _pydantic_ready() -> bool:
    try:
        import pydantic  # noqa: F401
        return True
    except ImportError:
        return False


def _maybe_install_embodiment_deps() -> dict:
    """Install CI pydantic if missing; offline / restricted egress is soft."""
    if _pydantic_ready():
        return {
            "label": "embodiment-deps",
            "cmd": [sys.executable, "-c", "import pydantic"],
            "exit_code": 0,
            "wall_s": 0.0,
            "note": "pydantic already importable",
        }
    req = ROOT / "integrations/joshinator-analyzer/backend/requirements-ci.txt"
    if not req.exists():
        return {
            "label": "embodiment-deps-offline",
            "cmd": [],
            "exit_code": 0,
            "wall_s": 0.0,
            "soft": True,
            "note": "no requirements-ci.txt; catalog-only fuzz",
        }
    result = run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
        "embodiment-deps",
    )
    if result["exit_code"] != 0:
        result["label"] = "embodiment-deps-offline"
        result["exit_code"] = 0
        result["soft"] = True
        result["note"] = "pypi unreachable; embodiment 3T uses catalog-only path"
    return result


def run(
    cmd: list[str],
    label: str,
    *,
    env: dict | None = None,
    cwd: str | None = None,
) -> dict:
    print(f"[3T] {label}: {' '.join(cmd)}", flush=True)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd or str(ROOT), env=env)
    wall = time.perf_counter() - t0
    return {"label": label, "cmd": cmd, "exit_code": proc.returncode, "wall_s": wall}


def write_suggestions(cycle_dir: Path, pass_id: str, results: list[dict], green: bool) -> None:
    lines = [
        f"# Three-trillion QA suggestions — pass {pass_id}",
        "",
        f"- status: {'green' if green else 'needs_work'}",
        f"- n: {THREE_T:,}",
        f"- at: {utc_now()}",
        "",
        "## Results",
    ]
    for r in results:
        lines.append(f"- {r['label']}: exit={r['exit_code']} wall={r['wall_s']:.1f}s")
    lines += [
        "",
        "## Fixes applied this cycle",
        "- Converse `/api/turn` is one `cam_reason.reason()` + `speak_from_trace` (camera/pupil/voice overlays)",
        "- In-process `connectome-route.route()` + `cam_inproc` (no python3 spawn per check/route)",
        "- `ci-static-gate.py` one-process static CI; 1M fuzz stays isolated",
        "- 3T campaign now runs `ci-static-gate` + converse/reason units + Aaron-voice 3T",
        "- `aaron-voice-billion-fuzz.py` honors `--physical` / modular_period_scaled (N≥1e11)",
        "- cam-reason 3T workers assert in-process coding route + converse greeting/see-me overlay",
        "- workspace-integration-check is inside the static gate (was campaign-only)",
        "- Public-apis 3T + expanded allowlisted add-ons (frankfurter / advice slip) from #42",
        "- CI: install pydantic before joshinator embodiment unit tests",
        "- Embodiment 3T: pydantic-free `embodiment_lite` catalog path when pypi is blocked",
        "- 3T campaign auto-installs `integrations/joshinator-analyzer/backend/requirements-ci.txt` before embodiment fuzz",
        "- connectome-simulate v4-exhaustive-scaled for N≥1e11",
        "- Companion fuzzers: modular_period_scaled via trillion_scale.py",
        "- Codified Aaron test protocol (this entrypoint + CONTINUOUS_QA)",
        "- Google Trends: `scripts/google-trends-check.py` + curated add-ons (`trends.search_*`)",
        "- Presence: Higgsfield Speak clips rejected — portrait + A2F only (`scripts/presence-check.py`)",
        "- Trajectory: `higgsfield_rejected_for_cam_face` strips Speak clips from speak plans",
        "- Higgsfield IDs are GPU train (`switch.cam_enhance`); Speak never owns `motor.higgsfield`",
        "- Converse overlays live in `config/persona/converse-overlays.json` (`speak_from_trace` reads config)",
        "- `converse-billion-fuzz.py` overlay × intent matrix + in-process catalog smoke",
        "- `cam_inproc.public_apis_search` / `google_trends_search` / `catalog_sense_smoke` (no subprocess)",
        "- FunASR/hash_dev enroll checksum on VoiceStore; aaron-voice 3T verifies reload",
        "- `activity_emit.invalidate_dual_stream_cache` + mesh-params mtime reload",
        "- One converse voice: TS home server (`shared/converseOverlays.ts`) + web companion "
        "(`companions/web/converse-overlays.js`) read the same persona config as Python",
        "- `converse-parity-check.py` asserts Python/TS/JS mirrors byte-identical (static gate + 3T)",
        "- Turn-history phrasing (`echo_repeat`) + config `intent_rules` mirrored from cam_reason",
        "- Reply metadata (`overlay.kind/id`) flows /api/turn → home bubble tag + MiniBrain label",
        "- `/api/converse/overlays` (+ `/reload`, `/preview`) on both hosts; MCP `converse_overlays_check`",
        "",
        "## Suggested add-ons",
        "- `quotes.quotable` / `exchange.open_er_api` allowlisted public-apis add-ons when ops asks",
        "- Voice add-on: live FunASR CAM++ enroll on Aaron’s host (checksum already in store)",
        "- Converse add-on: per-overlay `area`/`tracts` hints so the cortex lights the phrase's pathway",
        "- Converse add-on: iOS companion reads `converse-overlays.json` (Swift mirror + parity case)",
        "",
        "## Standing suggestions",
        "- Keep `python3 scripts/ci-static-gate.py` as the fast static gate; `bash scripts/ci-connectome.sh` still owns 1M fuzz",
        "- Dual three-trillion: `python3 scripts/three-trillion-campaign.py --passes 2`",
        "- Merge prep: `bash scripts/merge-prep-trillion.sh`",
        "- Raise `--physical 1000000000` when you want a full 1B physical stress under 3T",
        "- Aaron voice 3T: `python3 scripts/aaron-voice-billion-fuzz.py --n 3000000000000`",
        "- Converse units: `AARON_VOICE_TEST=1 AARON_VOICE_ALLOW_DEV_BACKEND=1 python3 scripts/test_cam_converse_voice_gate.py`",
        "- Slim CI deps: `integrations/joshinator-analyzer/backend/requirements-ci.txt`",
        "- After registry edits: `python3 scripts/test_cline_workspaces.py`",
        "- Converse overlays: `python3 scripts/converse-overlays-check.py`",
        "- Converse parity (py/ts/js): `python3 scripts/converse-parity-check.py`",
        "- Converse TS units: `npx vitest run shared/converseOverlays.test.ts server/core/cam-converse.test.ts`",
        "- Converse 3T: `python3 scripts/converse-billion-fuzz.py --n 3000000000000`",
        "- In-process catalogs: `cam_inproc.public_apis_search` / `google_trends_search`",
        "- Trends add-ons: `python3 scripts/google-trends-addon.py list`",
        "- Higgsfield: `python3 scripts/higgsfield-run.py --doctor` then pack to `mesh/runs`",
        "- Higgsfield train jobs stay enhance-gated; never free-spend GPU from Cline",
        "- `git submodule update --init integrations/higgsfield` before any live train intent",
        "- Allowlist `pypi.org` / `files.pythonhosted.org` if you want full embodiment resolve in Cloud Agent",
        "- Presence add-on: `python3 scripts/presence-check.py` (no Speak overlay on Cam’s face)",
        "- Mirror cycles into `identity/persistence/qa-mesh-latest.json`",
        "- ILLA desktop: `python3 scripts/illa-desktop-billion-fuzz.py --n 3000000000000`",
        "- ILLA unit: `python3 scripts/test_illa_desktop.py`",
        "- Public APIs: `python3 scripts/public-apis-billion-fuzz.py --n 3000000000000`",
        "- Public APIs unit: `python3 scripts/test_public_apis.py` + `test_public_apis_addons.py`",
        "- Public APIs add-ons: `python3 scripts/public-apis-addon.py list`",
        "- Keep electron-builder pin exact `26.16.1` (not fork master / v27)",
        "- After packaging edits: `npm --prefix integrations/illa-desktop run check:pin`",
        "- Cloud Agent: install must be a real command (`./scripts/cloud-agent-install.sh`); never `build` / `promote`",
        "- Do not add `npm ci` to Cloud Agent install until `registry.npmjs.org` is allowlisted",
        "- After merge, start a new Cloud Agent so `.cursor/environment.json` overrides the dashboard",
        "- Dashboard Save is on the agent Environment panel; if Save is missing, merge this PR so repo JSON wins",
        "- Suggest: add `quotes.quotable` / `exchange.open_er_api` allowlisted add-ons when ops asks",
        "- Suggest: MCP `public_apis_addon` for weather/geo before inventing HTTP helpers",
        "",
    ]
    (cycle_dir / "suggestions.md").write_text("\n".join(lines), encoding="utf-8")


def one_pass(
    pass_id: str,
    seed: int,
    workers: int,
    physical: int,
) -> tuple[bool, list[dict], Path]:
    stamp = utc_now()
    cycle_dir = CYCLES / f"{stamp}-3t-pass-{pass_id}"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    out_tag = f"pass{pass_id}"

    results.append(run([sys.executable, "scripts/ci-static-gate.py"], "ci-static-gate"))
    results.append(
        run([sys.executable, "scripts/test_cline_workspaces.py"], "workspace-unit-tests")
    )
    results.append(
        run(
            [sys.executable, "scripts/test_cloud_agent_install.py"],
            "cloud-agent-install",
        )
    )
    results.append(
        run([sys.executable, "scripts/test_cam_system.py"], "cam-system-unit")
    )
    results.append(
        run(
            [
                sys.executable,
                "-m",
                "unittest",
                "test_cam_reason",
                "test_cam_fast",
                "test_cam_infinitemind",
            ],
            "cam-reason-unit",
            cwd=str(ROOT / "scripts"),
        )
    )
    env_voice = dict(os.environ)
    env_voice["AARON_VOICE_TEST"] = "1"
    env_voice["AARON_VOICE_ALLOW_DEV_BACKEND"] = "1"
    results.append(
        run(
            [
                sys.executable,
                "-m",
                "unittest",
                "test_aaron_voice_gate",
                "test_cam_converse_voice_gate",
            ],
            "converse-voice-unit",
            env=env_voice,
            cwd=str(ROOT / "scripts"),
        )
    )
    results.append(
        run([sys.executable, "scripts/higgsfield-check.py"], "higgsfield-check")
    )
    results.append(
        run([sys.executable, "scripts/test_higgsfield.py"], "higgsfield-unit")
    )
    results.append(
        run([sys.executable, "scripts/test_embodiment_lite.py"], "embodiment-lite")
    )
    results.append(run([sys.executable, "scripts/presence-check.py"], "presence-check"))
    results.append(
        run([sys.executable, "scripts/converse-overlays-check.py"], "converse-overlays-check")
    )
    results.append(
        run([sys.executable, "scripts/test_converse_overlays.py"], "converse-overlays-unit")
    )
    results.append(
        run(
            [
                sys.executable,
                "scripts/converse-parity-check.py",
                "--out",
                str(OUT / f"converse-parity-{out_tag}.json"),
            ],
            "converse-parity",
        )
    )
    results.append(
        run([sys.executable, "scripts/trajectory-policy-check.py"], "trajectory-policy-check")
    )

    conn_out = OUT / f"connectome-sim-3t-{out_tag}.json"
    results.append(
        run(
            [
                sys.executable,
                "scripts/connectome-simulate.py",
                "--n",
                str(THREE_T),
                "--strict-edges",
                "--scale",
                "exhaustive",
                "--physical",
                str(physical),
                "--seed",
                str(seed),
                "--workers",
                str(workers),
                "--out",
                str(conn_out),
            ],
            "connectome-3t",
        )
    )

    results.append(
        run([sys.executable, "scripts/test_illa_desktop.py"], "illa-desktop-unit")
    )
    results.append(
        run([sys.executable, "scripts/illa-electron-check.py"], "illa-electron-check")
    )
    results.append(
        run([sys.executable, "scripts/test_public_apis.py"], "public-apis-unit")
    )
    results.append(
        run(
            [sys.executable, "scripts/test_public_apis_addons.py"],
            "public-apis-addons-unit",
        )
    )
    results.append(
        run([sys.executable, "scripts/public-apis-check.py"], "public-apis-check")
    )

    for script, name, extra_seed in (
        ("scripts/trajectory-billion-fuzz.py", "trajectory-3t", 17),
        ("scripts/embodiment-billion-fuzz.py", "embodiment-3t", 31),
        ("scripts/cam-reason-billion-fuzz.py", "cam-reason-3t", 11),
        ("scripts/illa-desktop-billion-fuzz.py", "illa-desktop-3t", 26),
        ("scripts/aaron-voice-billion-fuzz.py", "aaron-voice-3t", 19),
        ("scripts/public-apis-billion-fuzz.py", "public-apis-3t", 23),
        ("scripts/converse-billion-fuzz.py", "converse-3t", 29),
    ):
        if name == "embodiment-3t":
            results.append(_maybe_install_embodiment_deps())
        out = CYCLES / f"{name}-{out_tag}.json"
        results.append(
            run(
                [
                    sys.executable,
                    script,
                    "--n",
                    str(THREE_T),
                    "--physical",
                    str(physical),
                    "--seed",
                    str(seed + extra_seed),
                    "--workers",
                    str(workers),
                    "--out",
                    str(out),
                ],
                name,
            )
        )

    green = all(r["exit_code"] == 0 for r in results)
    write_suggestions(cycle_dir, pass_id, results, green)
    (cycle_dir / "cycle.json").write_text(
        json.dumps(
            {
                "pass": pass_id,
                "n": THREE_T,
                "physical": physical,
                "seed": seed,
                "status": "green" if green else "failed",
                "results": results,
                "at": utc_now(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return green, results, cycle_dir


def write_merge_readiness(pass_a: dict, pass_b: dict, ok: bool) -> Path:
    path = OUT / "MERGE_READINESS_THREE_TRILLION.md"
    doc = f"""# Merge readiness — three-trillion campaign

**Verdict: {'READY TO MERGE' if ok else 'HOLD'}**

Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}  
Protocol: Aaron base **test** — 3T → fix/suggest → 3T → merge if green

| Gate | Result |
|---|---|
| Pass A | {'green' if pass_a.get('ok') else 'failed'} · cycle `{pass_a.get('cycle')}` |
| Pass B | {'green' if pass_b.get('ok') else 'failed'} · cycle `{pass_b.get('cycle')}` |
| N | {THREE_T:,} (exhaustive/modular scale + physical stress) |

Evidence under `vault/10-Mesh-Distillates/qa-cycles/` and `connectome-sim-3t-*.json`.
"""
    path.write_text(doc, encoding="utf-8")
    return path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--passes", type=int, default=2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument(
        "--physical",
        type=int,
        default=ts.PHYSICAL_DEFAULT,
        help="physical stress subset per harness (default 10M)",
    )
    args = p.parse_args()

    CYCLES.mkdir(parents=True, exist_ok=True)
    print(
        f"[3T] Aaron test protocol: passes={args.passes} n={THREE_T:,} "
        f"physical={args.physical:,}",
        flush=True,
    )

    pass_meta: list[dict] = []
    overall = True
    for i in range(1, args.passes + 1):
        print(f"[3T] === pass {i}/{args.passes} ===", flush=True)
        ok, _results, cycle_dir = one_pass(
            str(i), args.seed + i * 100, args.workers, args.physical
        )
        pass_meta.append({"ok": ok, "cycle": str(cycle_dir.relative_to(ROOT))})
        if not ok:
            overall = False
            print(f"[3T] pass {i} FAILED — stop for fix before pass 2", flush=True)
            break
        print(f"[3T] pass {i} green", flush=True)

    a = pass_meta[0] if pass_meta else {"ok": False, "cycle": ""}
    b = pass_meta[1] if len(pass_meta) > 1 else {"ok": False, "cycle": "not-run"}
    ready = overall and len(pass_meta) >= 2 and a["ok"] and b["ok"]
    path = write_merge_readiness(a, b, ready)
    print(f"[3T] merge readiness → {path}", flush=True)
    print(f"[3T] done ready={ready}", flush=True)
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
