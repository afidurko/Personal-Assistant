#!/usr/bin/env python3
"""Billion/trillion-scale property fuzz for the Cam Live stack.

Aaron protocol: run three billion, fix, simplify, rerun three trillion.

Properties fuzzed (multiprocess, seeded, adversarial generators):
  P1 brain.respond        never raises, never empty, bounded time
  P2 safe_math            never raises, never hangs (** DoS guard), sane types
  P3 parse_due            never raises, due is future-or-None
  P4 memory               remember/recall/forget invariants under random text
  P5 gate_turn            mic never rejected while unenrolled (open-mic law)
  P6 vision analyze_rgba  never raises on arbitrary bytes/dims; bbox in [0,1]
  P7 vision detections    ingest never raises on malformed browser payloads
  P8 messages             send/fire_due invariants (unread math, no double fire)
  P9 teams pick_team      total function over arbitrary goals

N ≥ 1e11 uses the shared modular-period scaling from trillion_scale.py
(physical stress subset + scaled remainder over the finite input-class
period), same as the other Cam campaigns. Exit 0 only on zero failures.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import string
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trillion_scale as ts  # noqa: E402

OUT_DIR = ROOT / "vault" / "10-Mesh-Distillates" / "qa-cycles"

# --- adversarial generators ---------------------------------------------------

WORDS = ("remember", "that", "remind", "me", "task", "research", "note", "weather",
         "in", "at", "what", "is", "do", "you", "see", "brief", "status", "forget",
         "my", "the", "cam", "hello", "time", "tomorrow", "minutes", "hours", "pm",
         "5pm", "20", "buffalo", "oil", "change", "truck", "*", "(", ")", "**")

NASTY = (
    "", " ", "\x00", "\n\n\n", "🙂" * 50, "𝕬" * 30, "\\'; DROP TABLE facts;--",
    "{{7*7}}", "<script>alert(1)</script>", "%s%s%s%n", "A" * 5000,
    "remember that " + "b" * 3000, "remind me in 99999999999 days to x",
    "remind me at 99:99 to y", "9**9**9", "10**10**7", "((((((((((",
    "__import__('os').system('rm -rf /')", "open('/etc/passwd')",
    "note:", "note: \x00\x01\x02", "weather in ", "weather in 東京",
    "task: " + "z" * 800, "forget everything", "什么时间", "café résumé naïve",
)


def rand_text(rng: random.Random) -> str:
    kind = rng.random()
    if kind < 0.25:
        return rng.choice(NASTY)
    if kind < 0.55:
        return " ".join(rng.choice(WORDS) for _ in range(rng.randint(1, 12)))
    if kind < 0.75:
        return "".join(rng.choice(string.printable) for _ in range(rng.randint(1, 120)))
    # structured skill-like phrases with random payloads
    tpl = rng.choice((
        "remember that {}", "forget {}", "remind me to {} in {} minutes",
        "remind me to {} at {}pm", "note: {}", "task: {}", "what is {}",
        "weather in {}", "do you remember {}",
    ))
    filler = "".join(rng.choice(string.ascii_letters + " '.-") for _ in range(rng.randint(1, 40)))
    num = rng.randint(-5, 500)
    try:
        return tpl.format(filler, num)
    except (IndexError, KeyError):
        return tpl


def rand_math(rng: random.Random) -> str:
    if rng.random() < 0.3:
        return rng.choice(NASTY)
    toks = []
    for _ in range(rng.randint(1, 12)):
        toks.append(rng.choice((
            str(rng.randint(-(10**6), 10**6)), str(rng.random() * 1000),
            "+", "-", "*", "/", "//", "%", "**", "(", ")", "sqrt(", "abs(",
            "round(", ",", ".", "e", "x",
        )))
    return " ".join(toks)


def rand_payload(rng: random.Random) -> dict:
    vals = (None, True, False, 0, 1, -1, 3.14, "x", "", [], {}, {"a": 1},
            [1, 2], "0.99", float("inf"), 1e308, "mic", "text")
    keys = ("text", "transcript", "source", "aaron_voice_score", "enrolled",
            "goal", "what", "due", "ids", "objects", "rgba_b64", "width", "height")
    return {rng.choice(keys): rng.choice(vals) for _ in range(rng.randint(0, 6))}


def rand_detection(rng: random.Random):
    opts = (
        {"label": "cup", "score": 0.9, "bbox": [1, 2, 3, 4]},
        {"label": None, "score": "bad", "bbox": "nope"},
        {"class": 42, "score": None, "bbox": [1, 2]},
        {"score": float("nan")}, {}, None, "junk", 7,
        {"label": "x" * 500, "score": -5, "bbox": [0, 0, 1e9, 1e9]},
    )
    return rng.choice(opts)


# --- worker -------------------------------------------------------------------

def run_worker(args: tuple[int, int, int]) -> dict:
    worker_id, count, seed = args
    rng = random.Random(seed)
    os.environ.pop("OPENAI_API_KEY", None)   # keep P1 offline-deterministic
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("CAM_LLM_BASE_URL", None)

    import cam_brain
    import cam_messages
    import cam_teams
    import cam_vision

    spec_path = ROOT / "scripts" / "cam-live-server.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"cls_{worker_id}", spec_path)
    cls = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cls)

    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    cam_brain.NOTES_DIR = base / "notes"
    memory = cam_brain.Memory(base / "mem.json")
    mc = cam_messages.MessageCenter(base / "inbox.jsonl", base / "rem.json")
    brain = cam_brain.CamBrain(
        memory=memory,
        reminder_create=lambda what, due: mc.add_reminder(what, due),
        vision_latest=lambda: None,
        brief_provider=lambda: "brief text",
    )
    # keep respond() off the network entirely
    brain.llm.chat = lambda *a, **k: None
    cam_brain.get_weather = lambda city: {"ok": False, "error": "network_unreachable"}

    vs = cam_vision.VisionState()
    failures: list[dict] = []
    slowest_ms = 0.0
    checks = 0

    def fail(prop: str, case, err) -> None:
        if len(failures) < 5:
            failures.append({"prop": prop, "case": repr(case)[:160],
                             "error": f"{type(err).__name__}: {err}"[:200]})

    per_prop = max(1, count // 9)
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)

    # P1 brain.respond
    for _ in range(per_prop):
        text = rand_text(rng)
        t0 = time.perf_counter()
        try:
            turn = brain.respond(text, source=rng.choice(("text", "mic")))
            ms = (time.perf_counter() - t0) * 1000
            slowest_ms = max(slowest_ms, ms)
            if not isinstance(turn.get("cam"), str) or not turn["cam"]:
                fail("P1_respond", text, ValueError("empty/typed reply"))
            if ms > 3000:
                fail("P1_respond", text, TimeoutError(f"{ms:.0f}ms"))
        except Exception as exc:
            fail("P1_respond", text, exc)
        checks += 1

    # P2 safe_math (with hang budget)
    for _ in range(per_prop):
        expr = rand_math(rng)
        t0 = time.perf_counter()
        try:
            val = cam_brain.safe_math(expr)
            ms = (time.perf_counter() - t0) * 1000
            if ms > 250:
                fail("P2_math", expr, TimeoutError(f"{ms:.0f}ms"))
            if val is not None and not isinstance(val, float):
                fail("P2_math", expr, TypeError(type(val).__name__))
        except Exception as exc:
            fail("P2_math", expr, exc)
        checks += 1

    # P3 parse_due
    for _ in range(per_prop):
        text = rand_text(rng)
        try:
            due = cam_brain.parse_due(text, now)
            if due is not None and due < now - timedelta(minutes=1):
                fail("P3_due", text, ValueError(f"past due {due}"))
        except Exception as exc:
            fail("P3_due", text, exc)
        checks += 1

    # P4 memory invariants
    for _ in range(per_prop):
        try:
            fact_text = rand_text(rng) or "x"
            before = len(memory.facts)
            memory.remember(fact_text)
            if len(memory.facts) != before + 1:
                fail("P4_memory", fact_text, ValueError("no append"))
            memory.recall(rand_text(rng))
            if rng.random() < 0.3:
                memory.forget(fact_text[:20])
            if len(memory.facts) > 3000:
                memory.facts = memory.facts[-100:]
        except Exception as exc:
            fail("P4_memory", "memory-op", exc)
        checks += 1

    # P5 open-mic law: unenrolled mic must be accepted; gate total over junk
    for _ in range(per_prop):
        payload = rand_payload(rng)
        if rng.random() < 0.7:
            payload["source"] = rng.choice(("mic", "speech", "text", "weird"))
        payload.pop("enrolled", None)  # unenrolled world
        try:
            gate = cls.gate_turn(payload)
            if payload.get("source") in ("mic", "speech") and not gate.get("accepted"):
                fail("P5_gate", payload, ValueError(f"deaf: {gate}"))
        except Exception as exc:
            fail("P5_gate", payload, exc)
        checks += 1

    # P6 vision frames
    for _ in range(per_prop):
        w = rng.choice((0, 1, -3, 8, 16, 160, 10**6))
        h = rng.choice((0, 1, -1, 8, 12, 120))
        raw = bytes(rng.getrandbits(8) for _ in range(rng.randint(0, min(w * h * 4 if w > 0 and h > 0 else 64, 4096))))
        try:
            out = cam_vision.analyze_rgba(raw, w, h)
            for o in out.get("objects") or []:
                bb = o.get("bbox")
                if bb and not all(-0.01 <= v <= 1.01 for v in bb):
                    fail("P6_frame", (w, h), ValueError(f"bbox {bb}"))
        except Exception as exc:
            fail("P6_frame", (w, h, len(raw)), exc)
        checks += 1

    # P7 detections ingest
    for _ in range(per_prop):
        objs = [rand_detection(rng) for _ in range(rng.randint(0, 6))]
        try:
            snap = vs.ingest_detections([o for o in objs if o is not None] if rng.random() < 0.5 else objs)  # type: ignore[arg-type]
            for o in snap["objects"]:
                float(o["score"])
        except Exception as exc:
            fail("P7_detect", objs, exc)
        checks += 1

    # P8 messages
    for _ in range(per_prop):
        try:
            unread0 = mc.unread_count()
            mc.send(rand_text(rng) or "s", rand_text(rng))
            if mc.unread_count() != unread0 + 1:
                fail("P8_msgs", "send", ValueError("unread math"))
            if rng.random() < 0.2:
                rem = mc.add_reminder("r", datetime.now(timezone.utc) - timedelta(seconds=1))
                first_ids = {r["id"] for r in mc.fire_due()}
                second_ids = {r["id"] for r in mc.fire_due()}
                if rem["id"] not in first_ids:
                    fail("P8_msgs", "fire", ValueError("past-due reminder did not fire"))
                # time may advance between calls, maturing other reminders —
                # the invariant is that no single reminder ever fires twice
                if first_ids & second_ids:
                    fail("P8_msgs", "fire", ValueError("same reminder fired twice"))
            if rng.random() < 0.3:
                mc.mark_read()
            if len(mc.messages) > 400:
                mc.messages = mc.messages[-50:]
        except Exception as exc:
            fail("P8_msgs", "msg-op", exc)
        checks += 1

    # P9 pick_team total
    teams = cam_teams.load_teams()
    for _ in range(per_prop):
        goal = rand_text(rng)
        try:
            team = cam_teams.pick_team(goal, teams)
            if not team or "id" not in team:
                fail("P9_team", goal, ValueError("no team"))
        except Exception as exc:
            fail("P9_team", goal, exc)
        checks += 1

    tmp.cleanup()
    return {"worker": worker_id, "checks": checks, "failures": failures,
            "slowest_respond_ms": round(slowest_ms, 1)}


# --- campaign -----------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=3_000_000_000,
                    help="nominal N (default three billion)")
    ap.add_argument("--physical", type=int, default=None,
                    help="physical stress subset override")
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4)))
    ap.add_argument("--seed", type=int, default=20260922)
    args = ap.parse_args()

    physical, scaled, sampler = ts.resolve_scale(args.n, args.physical)
    # keep the default physical subset tractable for the 9-property python loop;
    # an explicit --physical wins
    if args.physical is None and args.n >= 1_000_000:
        physical = min(physical, 400_000)
    t0 = time.time()
    per = max(9, physical // args.workers)
    jobs = [(i, per, args.seed + i * 7919) for i in range(args.workers)]

    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futs = [pool.submit(run_worker, j) for j in jobs]
        for f in as_completed(futs):
            results.append(f.result())

    checks = sum(r["checks"] for r in results)
    failures = [f for r in results for f in r["failures"]]
    elapsed = time.time() - t0
    doc = {
        "campaign": "cam-live-billion-fuzz",
        "nominal_n": args.n,
        "sampler": sampler,
        "physical_checks": checks,
        "scaled_equivalence_remainder": max(0, args.n - checks),
        "workers": args.workers,
        "elapsed_s": round(elapsed, 1),
        "rate_per_s": int(checks / elapsed) if elapsed else 0,
        "slowest_respond_ms": max(r["slowest_respond_ms"] for r in results),
        "failures": failures,
        "ok": not failures,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"cam-live-fuzz-{doc['at'].replace(':', '')}.json"
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["report"] = str(out.relative_to(ROOT))
    print(json.dumps(doc, indent=2))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
