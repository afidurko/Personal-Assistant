#!/usr/bin/env python3
"""Parity: Python, TS and companion-JS overlay mirrors answer identically.

Runs the deterministic corpus from converse_overlays.parity_corpus() through
  * scripts/converse_overlays.py            (Python converse server)
  * shared/converseOverlays.ts              (TS home server, via Node strip-types / tsx)
  * companions/web/converse-overlays.js     (on-device companion)
and fails on any text / kind / id / intent divergence.

Exit 0 with {"skipped": ...} when Node is unavailable so Python-only hosts
still pass the static gate; the 3T campaign treats a skip as a warning.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import converse_overlays as co  # noqa: E402

TS_MODULE = ROOT / "shared" / "converseOverlays.ts"
JS_MODULE = ROOT / "companions" / "web" / "converse-overlays.js"

RUNNER = """
import fs from 'node:fs';
const [, , tsPath, jsPath, inputPath] = process.argv;
const input = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
const cfg = input.cfg;
const ts = await import(tsPath);
await import(jsPath);
const js = globalThis.CamOverlays;
function run(mod, c) {
  const trace = {
    intents: c.intents || [],
    path: c.path || 'fast',
    hotspot_id: c.hotspot_id ?? null,
    motor_plan: c.motor_plan ?? null,
  };
  const out = mod.explainReply(c.text || '', trace, c.history || null, cfg);
  return { text: out.text, kind: out.kind, id: out.id, intents_from_config: mod.classifyIntents(c.text || '', cfg) };
}
// Companion load(): absolute path first, relative fallback, cache when offline.
const store = new Map();
const storage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, v) };
const okJson = { ok: true, json: async () => cfg };
const fetchAbsolute404 = async (url) => (url.startsWith('/') ? { ok: false, status: 404 } : okJson);
const first = await js.load({ storage, fetch: fetchAbsolute404 });
const offline = await js.load({ storage, fetch: async () => { throw new Error('offline'); } });
const cold = await js.load({ storage: { getItem: () => null, setItem: () => {} }, fetch: async () => { throw new Error('offline'); } });
const jsLoad = {
  network_source: first.source,
  network_version: first.cfg.version,
  cache_source: offline.source,
  cache_version: offline.cfg.version,
  cold_source: cold.source,
  cold_answers: js.explainReply('anything', {}, null, cold.cfg).kind,
};
const result = {
  ts: input.cases.map((c) => run(ts, c)),
  js: input.cases.map((c) => run(js, c)),
  ts_check: ts.checkOverlays(cfg),
  ts_speak: ts.speakParams(cfg),
  js_speak: js.speakParams(cfg),
  js_load: jsLoad,
};
process.stdout.write(JSON.stringify(result));
"""


def _node_results(cfg: dict, cases: list[dict]) -> tuple[dict | None, str | None]:
    node = shutil.which("node")
    if not node:
        return None, "node_missing"
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "parity-runner.mjs"
        runner.write_text(RUNNER, encoding="utf-8")
        payload = Path(tmp) / "input.json"
        payload.write_text(json.dumps({"cfg": cfg, "cases": cases}), encoding="utf-8")
        attempts = [
            [node, "--no-warnings", "--experimental-strip-types", str(runner)],
        ]
        npx = shutil.which("npx")
        if npx and (ROOT / "node_modules" / "tsx").exists():
            attempts.append([npx, "--no-install", "tsx", str(runner)])
        last_err = None
        for cmd in attempts:
            try:
                out = subprocess.run(
                    [*cmd, str(TS_MODULE), str(JS_MODULE), str(payload)],
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                    timeout=120,
                    check=True,
                )
                return json.loads(out.stdout), None
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
                stderr = getattr(exc, "stderr", "") or ""
                last_err = f"{type(exc).__name__}: {stderr.strip()[-400:] or exc}"
        return None, f"node_runner_failed: {last_err}"


def run_parity() -> dict:
    cfg = co.load_overlays(force=True)
    cases = co.parity_corpus(cfg)
    py = [co.run_parity_case(c, cfg) for c in cases]
    node, skip = _node_results(cfg, cases)
    report: dict = {
        "ok": True,
        "cases": len(cases),
        "mirrors": ["python"],
        "mismatches": [],
        "config": "config/persona/converse-overlays.json",
        "version": cfg.get("version"),
    }
    if node is None:
        report["skipped"] = skip
        report["ok"] = skip == "node_missing"
        if not report["ok"]:
            report["mismatches"].append({"mirror": "node", "error": skip})
        return report

    mismatches: list[dict] = report["mismatches"]

    def diff(mirror: str, expected: dict, got: dict, keys: tuple[str, ...], **where: object) -> None:
        for key in keys:
            if expected.get(key) != got.get(key):
                mismatches.append(
                    {"mirror": mirror, "key": key, "python": expected.get(key), "got": got.get(key), **where}
                )

    report["mirrors"] = ["python", "ts", "js"]
    reply_keys = ("text", "kind", "id", "intents_from_config")
    for mirror in ("ts", "js"):
        rows = node.get(mirror) or []
        if len(rows) != len(py):
            mismatches.append({"mirror": mirror, "error": "case_count"})
            continue
        for idx, (case, expect, got) in enumerate(zip(cases, py, rows)):
            diff(mirror, expect, got, reply_keys, case=idx, text=(case.get("text") or "")[:60])
    for mirror, check in (("python", co.check_overlays(cfg)), ("ts", node.get("ts_check") or {})):
        if not check.get("ok"):
            mismatches.append({"mirror": mirror, "error": f"{mirror}_check:{check.get('errors')}"})
    expected_load = {
        "network_source": "network",
        "network_version": cfg.get("version"),
        "cache_source": "cache",
        "cache_version": cfg.get("version"),
        "cold_source": "fallback",
        "cold_answers": "echo",
    }
    report["js_load"] = node.get("js_load") or {}
    diff("js_load", expected_load, report["js_load"], tuple(expected_load))
    py_speak = co.speak_params(cfg)
    for mirror in ("ts_speak", "js_speak"):
        diff(mirror, py_speak, node.get(mirror) or {}, ("rate", "pitch", "lang"))
    report["ok"] = not mismatches
    return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", help="optional JSON report path")
    args = p.parse_args()
    report = run_parity()
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
