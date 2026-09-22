#!/usr/bin/env python3
"""Ethics gate for Cam's research + predictive cortex (static, offline).

Checks that the measures in config/ethics/research-ethics.json are real, not
aspirational:

* config present, principles + protected contexts + redaction patterns compile
* redaction actually strips emails / phones / tokens from an experience record
* protected contexts resolve to human_judgment_required and never suggest automation
* thin evidence abstains; the prediction card carries every required field
* prequential report exposes calibration parity + abstention rate
* research briefs since the ethics date carry `## Sources` with accessed dates
* tracked research artefacts (fixture, briefs, distillates) contain no PII/secrets
* agi-research-scan honours arXiv rate etiquette + identifying User-Agent
* human-primacy gates (switch.cam_enhance / switch.kill) still exist and are wired

Exit 0 = pass (soft findings allowed), 1 = hard failure.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    soft: list[str] = []
    detail: dict = {}

    eth_path = ROOT / "config/ethics/research-ethics.json"
    if not eth_path.exists():
        print(json.dumps({"id": "research-ethics-check", "ok": False, "errors": ["missing config/ethics/research-ethics.json"]}, indent=2))
        return 1
    eth = load(eth_path)

    for key in ("principles", "protected_contexts", "redaction", "abstention", "calibration_parity", "source_etiquette", "citation_discipline", "prediction_card"):
        if key not in eth:
            errors.append(f"ethics config missing:{key}")
    ids = [p.get("id") for p in eth.get("principles") or []]
    for must in ("honesty", "human_primacy", "no_persons_as_targets", "data_minimisation", "right_to_forget", "source_respect"):
        if must not in ids:
            errors.append(f"principle missing:{must}")
    for rel in (eth.get("check"), eth.get("brief")):
        if rel and not (ROOT / rel).exists():
            errors.append(f"missing:{rel}")
    for rel in eth.get("applies_to") or []:
        if not (ROOT / rel).exists():
            soft.append(f"applies_to path missing:{rel}")

    patterns = (eth.get("redaction") or {}).get("patterns") or {}
    for kind, pat in patterns.items():
        try:
            re.compile(pat)
        except re.error as exc:
            errors.append(f"redaction pattern {kind} invalid: {exc}")

    # --- behavioural checks against the library ------------------------------
    try:
        import cam_experience as ce

        # secret-shaped samples are assembled at runtime so no literal ever sits in the repo
        fake_token = "sk_" + "live_" + "x" * 24
        exp = ce.make_experience(
            ok=True,
            hotspot="hotspot.coding",
            notes=f"ping aaron@example.com or +1 (555) 010-9999, token {fake_token}",
            ref="scripts/research-ethics-check.py",
        )
        leaked = [k for k, pat in patterns.items() if re.search(pat, exp["notes"])]
        if leaked:
            errors.append(f"redaction leaked: {leaked}")
        if not exp.get("redacted"):
            errors.append("redaction did not mark the record")
        detail["redaction_sample"] = exp["notes"]

        exps, _counts = ce.load_experiences(offline=True)
        ev = ce.prequential(exps, ce.load_config())
        model = ev["model"]
        metrics = ev["metrics"]
        if "parity" not in metrics or "abstention_rate" not in metrics:
            errors.append("prequential metrics lack parity/abstention_rate")
        detail["abstention_rate"] = metrics.get("abstention_rate")
        detail["parity_flagged"] = (metrics.get("parity") or {}).get("flagged")

        prot = model.predict({"hotspot": "hotspot.careers_submit", "center": "center.careers", "motors": ["motor.jobs"]})
        stance = (eth.get("protected_contexts") or {}).get("stance", "human_judgment_required")
        if not prot["protected_context"] or prot["advice"]["stance"] != stance:
            errors.append(f"protected context not honoured: {prot['advice']}")
        if prot["advice"]["suggest_qa_hold"]:
            errors.append("protected context suggested automation")
        if "%" in prot["narration"] and prot["evidence_level"] == "prior":
            errors.append("protected narration quoted a number with no experience")

        unknown = model.predict({"hotspot": "hotspot.never_seen_before_xyz"})
        if not unknown["advice"]["abstain"]:
            errors.append("thin evidence did not abstain")
        for field in (eth.get("prediction_card") or {}).get("required_fields") or []:
            if field == "gate":
                continue  # gate is stamped by the CLI envelope, not the model
            if field not in unknown:
                errors.append(f"prediction card missing field:{field}")
        if not unknown.get("limitations"):
            errors.append("prediction card has no stated limitations")
        detail["abstain_narration"] = unknown["narration"]
    except Exception as exc:  # noqa: BLE001
        errors.append(f"behaviour:{type(exc).__name__}: {exc}")

    # --- citation discipline ----------------------------------------------------
    cite = eth.get("citation_discipline") or {}
    since = str(cite.get("since") or "0000-00-00")
    missing_sources: list[str] = []
    checked = 0
    for rel in cite.get("research_dirs") or []:
        for md in sorted((ROOT / rel).glob("*.md")):
            stamp = md.name[:10]
            if not re.match(r"\d{4}-\d{2}-\d{2}", stamp) or stamp < since:
                continue
            checked += 1
            text = md.read_text(encoding="utf-8")
            for section in cite.get("require_sections") or []:
                if section not in text:
                    missing_sources.append(f"{md.relative_to(ROOT)} lacks {section}")
            if cite.get("require_accessed_date") and not re.search(r"accessed \d{4}-\d{2}-\d{2}", text):
                missing_sources.append(f"{md.relative_to(ROOT)} lacks accessed dates")
    errors.extend(missing_sources)
    detail["briefs_checked"] = checked

    # --- PII / secret scan over tracked research artefacts ------------------------
    scan_paths = [ROOT / "scripts/testdata/sample-experiences.jsonl"]
    scan_paths += list((ROOT / "vault/04-Research").glob("2026-*.md"))
    scan_paths += list((ROOT / "vault/10-Mesh-Distillates/predictive-cortex").glob("*.json"))
    hits: list[str] = []
    for path in scan_paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for kind in ("email", "token", "bearer", "ssn"):
            pat = patterns.get(kind)
            if pat and re.search(pat, text):
                hits.append(f"{path.relative_to(ROOT)}:{kind}")
    errors.extend(f"pii/secret in tracked artefact {h}" for h in hits)
    detail["artefacts_scanned"] = len(scan_paths)

    # --- source etiquette -------------------------------------------------------
    etiq = eth.get("source_etiquette") or {}
    team = load(ROOT / "config/teams/agi-research-scan.json")
    arxiv = next((s for s in team.get("sources") or [] if s.get("id") == "arxiv"), {})
    want = float(etiq.get("arxiv_min_interval_s", 3.0))
    if float(arxiv.get("min_interval_s", 0)) < want:
        errors.append(f"arxiv min_interval_s < {want}")
    scan_src = (ROOT / "scripts/agi-research-scan.py").read_text(encoding="utf-8")
    if "min_interval_s" not in scan_src or "time.sleep" not in scan_src:
        errors.append("agi-research-scan does not pace arXiv requests")
    ua = etiq.get("user_agent_must_identify")
    if ua and ua not in scan_src:
        errors.append(f"agi-research-scan User-Agent does not identify as {ua}")
    for host in etiq.get("bulk_crawl_forbidden") or []:
        if host in scan_src:
            errors.append(f"agi-research-scan touches forbidden host {host}")

    # --- human primacy gates ------------------------------------------------------
    switches = load(ROOT / "config/connectome/switches.json")
    sw_ids = {s.get("id") for s in switches.get("switches") or []}
    for must in ("switch.kill", "switch.cam_enhance"):
        if must not in sw_ids:
            errors.append(f"missing {must}")
    pc = load(ROOT / "config/enhancement/predictive-cortex.json")
    if pc.get("act_gate") != "switch.cam_enhance":
        errors.append("predictive cortex act_gate is not switch.cam_enhance")
    if pc.get("ethics") != "config/ethics/research-ethics.json":
        soft.append("predictive-cortex.json does not point at the ethics config")
    ce_src = (ROOT / "scripts/cam_experience.py").read_text(encoding="utf-8")
    if "CAM_KILL" not in ce_src:
        errors.append("cam_experience ignores CAM_KILL")

    out = {
        "id": "research-ethics-check",
        "ok": not errors,
        "principles": ids,
        "detail": detail,
        "soft": soft,
        "errors": errors,
    }
    print(json.dumps(out, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
