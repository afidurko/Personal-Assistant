#!/usr/bin/env python3
"""Daily AI/AGI research scan for Cam enhancement.

Standing goal (Aaron 2026-09-17): scan open sources for new papers/findings,
score Cam relevance, write vault + mesh distillates, and draft enhancement
proposals. Applying functionality changes still requires Aaron
(switch.cam_enhance / cam-enhance-gate).

Usage:
  python3 scripts/agi-research-scan.py              # live arXiv pull
  python3 scripts/agi-research-scan.py --dry-run    # plan only
  python3 scripts/agi-research-scan.py --offline    # no network; scaffold day note
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAM = json.loads(
    (ROOT / "config" / "teams" / "agi-research-scan.json").read_text(encoding="utf-8")
)
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def today_stamp() -> str:
    return date.today().isoformat()


def vault_paths(day: str) -> dict[str, Path]:
    out = TEAM["outputs"]
    daily_dir = ROOT / out["vault_dir"] / day
    proposals = ROOT / out["proposals_dir"]
    index = ROOT / out["daily_index"]
    return {
        "daily_dir": daily_dir,
        "proposals": proposals,
        "index": index,
        "json": daily_dir / "scan.json",
        "md": daily_dir / f"{day}-AGI-scan.md",
        "mesh": ROOT / "vault" / "10-Mesh-Distillates" / "agi-scan" / f"{day}.json",
    }


def arxiv_query(category: str, max_results: int) -> str:
    params = {
        "search_query": f"cat:{category}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    base = TEAM["sources"][0]["api"]
    return f"{base}?{urllib.parse.urlencode(params)}"


def parse_arxiv_feed(raw: bytes) -> list[dict]:
    root = ET.fromstring(raw)
    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        paper_id = (entry.findtext(f"{ATOM}id") or "").strip()
        title = re.sub(r"\s+", " ", (entry.findtext(f"{ATOM}title") or "").strip())
        summary = re.sub(
            r"\s+", " ", (entry.findtext(f"{ATOM}summary") or "").strip()
        )
        published = (entry.findtext(f"{ATOM}published") or "").strip()
        authors = [
            (a.findtext(f"{ATOM}name") or "").strip()
            for a in entry.findall(f"{ATOM}author")
        ]
        cats = [
            c.attrib.get("term", "")
            for c in entry.findall(f"{ARXIV}primary_category")
        ] + [
            c.attrib.get("term", "")
            for c in entry.findall(f"{ATOM}category")
        ]
        cats = sorted({c for c in cats if c})
        papers.append(
            {
                "id": paper_id,
                "title": title,
                "summary": summary[:1200],
                "published": published,
                "authors": authors[:12],
                "categories": cats,
                "source": "arxiv",
                "url": paper_id,
            }
        )
    return papers


def fetch_arxiv(max_results: int, timeout: int = 45) -> list[dict]:
    """Fetch recent papers per category (merged). Per-cat queries avoid 406s on long ORs."""
    categories = TEAM["sources"][0]["categories"]
    per_cat = max(2, max_results // max(1, len(categories)))
    headers = {
        "User-Agent": "CamAGIScout/1.0 (research; +https://github.com/afidurko/Personal-Assistant)",
        "Accept": "*/*",
    }
    by_id: dict[str, dict] = {}
    errors: list[str] = []
    for cat in categories:
        url = arxiv_query(cat, per_cat)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for paper in parse_arxiv_feed(resp.read()):
                    by_id[paper["id"]] = paper
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{cat}: {exc}")
    if not by_id and errors:
        raise RuntimeError("; ".join(errors))
    papers = list(by_id.values())
    papers.sort(key=lambda p: p.get("published") or "", reverse=True)
    return papers[:max_results]


def score_paper(paper: dict) -> dict:
    text = f"{paper.get('title','')} {paper.get('summary','')}".lower()
    rubric = TEAM["relevance_rubric"]
    scores = {
        "enhance_cam_routing": 0,
        "enhance_memory_mesh": 0,
        "enhance_presence_voice": 0,
        "enhance_vision": 0,
        "enhance_slm_local": 0,
        "enhance_dl_embeddings": 0,
        "enhance_predictive_cortex": 0,
        "general_agi_theory": 0,
    }
    checks = [
        (
            "enhance_predictive_cortex",
            [
                "world model",
                "experience replay",
                "learn from experience",
                "experiential",
                "calibrat",
                "conformal",
                "uncertainty quantification",
                "brier",
                "successor representation",
                "temporal difference",
                "predictive coding",
            ],
        ),
        ("enhance_cam_routing", ["agent", "multi-agent", "tool use", "planning", "orchestr"]),
        ("enhance_memory_mesh", ["retriev", "rag", "memory", "continual", "knowledge graph"]),
        ("enhance_presence_voice", ["speech", "tts", "avatar", "dialogue", "convers"]),
        ("enhance_vision", ["vision", "multimodal", "image", "video", "detect"]),
        ("enhance_slm_local", ["small language", "slm", "on-device", "efficient", "quantiz", "lora"]),
        ("enhance_dl_embeddings", ["embed", "rerank", "encoder", "contrastive", "represent"]),
        ("general_agi_theory", ["agi", "general intelligence", "foundation model"]),
    ]
    for key, needles in checks:
        if any(n in text for n in needles):
            scores[key] = rubric.get(key, 1)
    total = sum(scores.values())
    touchpoints = []
    if scores["enhance_cam_routing"]:
        touchpoints += ["center.capability", "center.router", "config/roles"]
    if scores["enhance_memory_mesh"]:
        touchpoints += ["center.memory", "center.info", "smart-second-brain"]
    if scores["enhance_slm_local"]:
        touchpoints += ["center.slm", "config/enhancement/slm-dl.json"]
    if scores["enhance_dl_embeddings"]:
        touchpoints += ["center.dl", "config/enhancement/slm-dl.json"]
    if scores["enhance_predictive_cortex"]:
        touchpoints += ["center.dl", "config/enhancement/predictive-cortex.json", "scripts/cam_experience.py"]
    if scores["enhance_presence_voice"]:
        touchpoints += ["center.comms", "motor.speak"]
    if scores["enhance_vision"]:
        touchpoints += ["center.vision", "center.dl"]
    return {
        **paper,
        "relevance_scores": scores,
        "relevance_total": total,
        "propose": total >= rubric["min_score_to_propose"],
        "cam_touchpoints": sorted(set(touchpoints)),
    }


def write_markdown(day: str, scored: list[dict], paths: dict[str, Path]) -> None:
    proposed = [p for p in scored if p["propose"]]
    lines = [
        f"# AGI Daily Scan — {day}",
        "",
        "Standing Cam enhancement scan (Aaron-authorized). "
        "**Functionality apply still requires Aaron** (`switch.cam_enhance`).",
        "",
        f"- Papers scored: **{len(scored)}**",
        f"- Above propose threshold: **{len(proposed)}**",
        f"- Team: `team.agi-research-scan`",
        f"- Pipeline: `config/pipelines/daily-agi-scan.json`",
        "",
        "## Highlights",
        "",
    ]
    for p in proposed[:15]:
        lines.append(
            f"- [{p['title']}]({p['url']}) — score {p['relevance_total']} — "
            f"touch: {', '.join(p['cam_touchpoints']) or 'n/a'}"
        )
    if not proposed:
        lines.append("- No papers crossed the propose threshold today.")
    lines += ["", "## All scored", ""]
    for p in scored:
        flag = "PROPOSE" if p["propose"] else "note"
        lines.append(
            f"### {p['title']}\n"
            f"- status: `{flag}` · score: {p['relevance_total']}\n"
            f"- url: {p['url']}\n"
            f"- published: {p.get('published','')}\n"
            f"- categories: {', '.join(p.get('categories') or [])}\n"
            f"- touchpoints: {', '.join(p['cam_touchpoints']) or '—'}\n"
            f"- gist: {p.get('summary','')[:400]}\n"
        )
    paths["md"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_index(day: str, scored: list[dict], index: Path) -> None:
    proposed = sum(1 for p in scored if p["propose"])
    stub = (
        f"# AGI Daily Scan\n\n"
        f"Cam’s standing everyday AI/AGI research scan. "
        f"Aaron has ultimate say over functionality changes.\n\n"
        f"Team: `config/teams/agi-research-scan.json` · "
        f"Docs: `docs/AGI_RESEARCH_TEAM.md`\n\n"
        f"## Days\n\n"
    )
    line = (
        f"- [[{day}-AGI-scan|{day}]] — scored {len(scored)}, "
        f"propose {proposed} → `agi-daily/{day}/`\n"
    )
    if index.exists():
        text = index.read_text(encoding="utf-8")
        if day in text:
            return
        if "## Days" not in text:
            text = stub
        text = text.rstrip() + "\n" + line
        index.write_text(text + "\n", encoding="utf-8")
    else:
        index.write_text(stub + line + "\n", encoding="utf-8")


def write_proposals(day: str, scored: list[dict], proposals_dir: Path) -> list[Path]:
    proposals_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for p in [x for x in scored if x["propose"]][:10]:
        slug = re.sub(r"[^a-z0-9]+", "-", p["title"].lower())[:48].strip("-")
        path = proposals_dir / f"{day}-{slug}.md"
        body = (
            f"# Enhancement proposal — {p['title']}\n\n"
            f"**Status:** propose_only (awaiting Aaron / `switch.cam_enhance`)\n"
            f"**Date:** {day}\n"
            f"**Source:** [{p['url']}]({p['url']})\n"
            f"**Relevance:** {p['relevance_total']} — {p['relevance_scores']}\n\n"
            f"## Suggested Cam touchpoints\n\n"
            + "\n".join(f"- `{t}`" for t in p["cam_touchpoints"])
            + "\n\n## Why it might enhance Cam\n\n"
            f"{p.get('summary','')[:800]}\n\n"
            f"## Apply gate\n\n"
            f"1. QA cite-check\n"
            f"2. Aaron approve via `config/pipelines/cam-enhance-gate.json`\n"
            f"3. capability-broker applies with implementer subagents\n"
            f"4. `python3 scripts/connectome-check.py`\n"
        )
        path.write_text(body, encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true", help="no network")
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument("--day", default=today_stamp())
    args = parser.parse_args()

    paths = vault_paths(args.day)
    plan = {
        "day": args.day,
        "team": TEAM["id"],
        "trigger": "sense.clock.daily",
        "hotspot": TEAM["pathway_hotspot"],
        "human_gate_for_apply": "switch.cam_enhance",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.dry_run:
        print(json.dumps({**plan, "mode": "dry-run"}, indent=2))
        return 0

    papers: list[dict] = []
    fetch_error = None
    if not args.offline:
        try:
            papers = fetch_arxiv(args.max_results)
        except Exception as exc:  # noqa: BLE001 — scout must still archive the day
            fetch_error = str(exc)
    scored = [score_paper(p) for p in papers]
    scored.sort(key=lambda p: p["relevance_total"], reverse=True)

    payload = {
        **plan,
        "mode": "offline" if args.offline else "live",
        "fetch_error": fetch_error,
        "count": len(scored),
        "propose_count": sum(1 for p in scored if p["propose"]),
        "papers": scored,
    }

    paths["daily_dir"].mkdir(parents=True, exist_ok=True)
    paths["mesh"].parent.mkdir(parents=True, exist_ok=True)
    paths["json"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    paths["mesh"].write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_markdown(args.day, scored, paths)
    # Obsidian-friendly copy name for wikilink in index
    wiki = paths["daily_dir"] / f"{args.day}-AGI-scan.md"
    if wiki != paths["md"]:
        wiki.write_text(paths["md"].read_text(encoding="utf-8"), encoding="utf-8")
    update_index(args.day, scored, paths["index"])
    written = write_proposals(args.day, scored, paths["proposals"])

    print(
        json.dumps(
            {
                "ok": True,
                "day": args.day,
                "papers": len(scored),
                "propose": sum(1 for p in scored if p["propose"]),
                "fetch_error": fetch_error,
                "vault_note": str(paths["md"].relative_to(ROOT)),
                "proposals": [str(p.relative_to(ROOT)) for p in written],
                "mesh": str(paths["mesh"].relative_to(ROOT)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
