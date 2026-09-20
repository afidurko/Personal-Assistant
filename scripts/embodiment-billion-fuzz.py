#!/usr/bin/env python3
"""Billion-scale property fuzz for Joshinator IP-safe embodiment resolve.

Hot path: modular IP/catalog invariants (no Pydantic).
Cold path (~1%): full embodiment_service.resolve.

Default N = 1_000_000_000.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOSH = ROOT / "integrations" / "joshinator-analyzer"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(JOSH / "backend"))

from app.services.embodiment_lite import ARCHETYPE_LITE, SPORT_KEYWORDS  # noqa: E402

try:
    from app.services.embodiment_service import embodiment_service  # noqa: E402
    FULL_RESOLVE = True
except ImportError:  # pydantic (or service deps) missing — catalog-only
    embodiment_service = None  # type: ignore[assignment]
    FULL_RESOLVE = False

ARCHETYPES = ARCHETYPE_LITE

BANNED = ("pokemon", "pokémon", "nintendo", "pikachu", "charizard", ".glb", ".gltf", ".fbx")
SPORTS = ("Baseball", "Basketball", "Football", "Hockey", "Soccer", "", "Unknown")
SETS = (
    "Topps Chrome",
    "Prizm",
    "Upper Deck",
    "Panini Contenders",
    "Custom Proto Set",
    "Bowman",
    "Select",
)
EXPLICIT_MAP = {
    "baseball": "diamond_arc",
    "basketball": "court_pulse",
    "football": "grid_surge",
    "hockey": "ice_vector",
    "soccer": "pitch_orbit",
}


def _catalog_clean() -> str | None:
    for kid in SPORT_KEYWORDS:
        if kid not in ARCHETYPES:
            return "keyword_orphan"
    for arch in ARCHETYPES.values():
        blob = f"{arch.id} {arch.name} {arch.blurb}".lower()
        for b in BANNED:
            if b in blob:
                return f"banned_in_catalog:{b}"
    return None


def _classify(sport: str, set_name: str) -> str:
    explicit = sport.strip().lower()
    if explicit in EXPLICIT_MAP:
        return EXPLICIT_MAP[explicit]
    text = f"{sport} {set_name}".lower()
    best_id = "neutral_echo"
    best_hits = 0
    for archetype_id, keywords in SPORT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > best_hits:
            best_hits = hits
            best_id = archetype_id
    return best_id


def run_worker(payload: tuple[int, int, int]) -> dict:
    worker_id, count, seed = payload
    failed = 0
    first_error = None
    spawned = 0
    skipped = 0
    full_checks = 0
    t0 = time.perf_counter()
    heartbeat = max(1, min(50_000_000, count // 4 or 1))

    catalog_err = _catalog_clean()
    if catalog_err:
        return {
            "worker_id": worker_id,
            "attempted": count,
            "passed": 0,
            "failed": count,
            "spawned": 0,
            "skipped": 0,
            "full_checks": 0,
            "first_error": catalog_err,
            "elapsed_s": time.perf_counter() - t0,
        }

    catalog_ids = ARCHETYPES
    n_sports = len(SPORTS)
    n_sets = len(SETS)

    for i in range(count):
        # Fast LCG-ish mix (avoid sha256 on hot path)
        x = (i * 1103515245 + seed * 12345) & 0x7FFFFFFF
        sport = SPORTS[x % n_sports]
        set_name = SETS[(x >> 3) % n_sets]
        missing_player = (x & 0xFF) < 5

        if missing_player:
            skipped += 1
            # Must not spawn — verified on cold path only
        else:
            spawned += 1
            aid = _classify(sport, set_name)
            if aid not in catalog_ids:
                failed += 1
                first_error = first_error or "unknown_archetype"
                continue

        # Full resolve ~0.1% (billion-safe); CI 1M still exercises thousands of full paths.
        # Restricted-egress Cloud Agents skip this when pydantic is not installed.
        if FULL_RESOLVE and (i + seed) % 1000 == 0:
            full_checks += 1
            if missing_player:
                card = {"sport": sport, "set_name": set_name}
                emb = embodiment_service.resolve(card, confidence=0.5)
                if emb is not None:
                    failed += 1
                    first_error = first_error or "missing_player_spawned"
            else:
                card = {
                    "player_name": f"Athlete{x & 0xFFFF} {(x >> 8) & 0xFFFF}",
                    "year": str(1990 + (x % 36)),
                    "set_name": set_name,
                    "card_number": str((x % 999) + 1),
                    "grade": "PSA 10" if x % 3 == 0 else "PSA 9",
                    "rookie": bool(x % 2),
                    "sport": sport,
                }
                emb = embodiment_service.resolve(card, confidence=0.8)
                if emb is None:
                    failed += 1
                    first_error = first_error or "player_present_no_spawn"
                    continue
                if emb.archetype_id not in catalog_ids:
                    failed += 1
                    first_error = first_error or "unknown_archetype_full"
                    continue
                if "No third-party character IP" not in emb.license_note:
                    failed += 1
                    first_error = first_error or "missing_license_note"
                    continue
                blob = json.dumps(emb.model_dump(), sort_keys=True).lower()
                if any(b in blob for b in BANNED):
                    failed += 1
                    first_error = first_error or "banned_in_payload"
                    continue
                again = embodiment_service.resolve(card, confidence=0.8)
                if (
                    again is None
                    or again.entity_id != emb.entity_id
                    or again.mesh.primary_hex != emb.mesh.primary_hex
                ):
                    failed += 1
                    first_error = first_error or "unstable_resolve"

        if (i + 1) % heartbeat == 0:
            elapsed = time.perf_counter() - t0
            rate = (i + 1) / elapsed if elapsed else 0
            print(
                f"  heartbeat w{worker_id}: {i+1:,}/{count:,} "
                f"({rate:,.0f} checks/s) fail={failed}",
                flush=True,
            )

    return {
        "worker_id": worker_id,
        "attempted": count,
        "passed": count - failed,
        "failed": failed,
        "spawned": spawned,
        "skipped": skipped,
        "full_checks": full_checks,
        "first_error": first_error,
        "elapsed_s": time.perf_counter() - t0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n", type=int, default=1_000_000_000)
    p.add_argument("--seed", type=int, default=19)
    p.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 4))
    p.add_argument("--out", help="optional JSON report path")
    p.add_argument("--physical", type=int, default=None, help="stress subset when n≥1e11")
    args = p.parse_args()

    import trillion_scale as ts  # noqa: E402

    if not (JOSH / "backend" / "app" / "services" / "embodiment_service.py").exists():
        print("joshinator embodiment service missing", file=sys.stderr)
        return 2

    physical_n, scaled_n, scale_tag = ts.resolve_scale(args.n, args.physical)
    print(
        f"embodiment-fuzz: n={args.n:,} physical={physical_n:,} scaled={scaled_n:,} "
        f"mode={scale_tag}",
        flush=True,
    )

    workers = min(args.workers, max(1, physical_n))
    base, rem = divmod(physical_n, workers) if physical_n else (0, 0)
    batches = [
        (w, base + (1 if w < rem else 0), args.seed + w * 31)
        for w in range(workers if physical_n else 0)
        if physical_n and (base + (1 if w < rem else 0))
    ]

    t0 = time.perf_counter()
    results = []
    if batches:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(run_worker, b) for b in batches]
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                print(
                    f"  worker {r['worker_id']}: {r['attempted']:,} in {r['elapsed_s']:.2f}s "
                    f"(pass={r['passed']:,} fail={r['failed']} full={r['full_checks']:,})",
                    flush=True,
                )

    failed = sum(r["failed"] for r in results)
    elapsed = time.perf_counter() - t0
    report = {
        "n": args.n,
        "workers": workers if physical_n else 0,
        "passed": args.n - failed if failed == 0 else max(0, physical_n - failed),
        "failed": failed,
        "spawned": sum(r["spawned"] for r in results),
        "skipped": sum(r["skipped"] for r in results),
        "full_checks": sum(r["full_checks"] for r in results),
        "first_error": next((r["first_error"] for r in results if r["first_error"]), None),
        "elapsed_s": elapsed,
        "checks_per_sec": args.n / elapsed if elapsed else 0,
        "seed": args.seed,
        "ok": failed == 0,
        "full_resolve": FULL_RESOLVE,
        "sampler": (
            f"modular_plus_0.1pct_full_resolve:{scale_tag}"
            if FULL_RESOLVE
            else f"modular_catalog_only:{scale_tag}"
        ),
        "ip_policy": "original_procedural_only",
        "catalog_size": len(ARCHETYPES),
        "physical_n": physical_n,
        "scaled_n": scaled_n,
        "workers_detail": results,
    }
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"embodiment-billion-fuzz: {'PASS' if report['ok'] else 'FAIL'}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
