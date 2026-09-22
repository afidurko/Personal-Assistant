#!/usr/bin/env python3
"""Cam agent teams — hierarchical orchestration that actually executes.

Aaron's design: Cam is the head agent; team leads head their own teams
and spawn subagents that work subtasks **in parallel** so work from
different teams lands on time. The team JSON under `config/teams/` was
descriptive only — nothing ran it. This module runs it:

    Cam (head)
      └─ picks a team lead for the goal
           └─ lead decomposes the goal into subtasks
                └─ subagents execute concurrently (thread pool)
                     └─ lead synthesizes results → message to Aaron

Subagents do real work with what's available on the machine:
vault/memory retrieval, GitHub code+repo search (api.github.com),
arXiv fetch when egress allows, workspace scans, math — and an LLM
synthesis pass when a model is connected. Failures degrade gracefully;
the task still completes with whatever the swarm gathered.

Stdlib only.
"""

from __future__ import annotations

import importlib.util
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "data" / "runtime"
TASKS_PATH = RUNTIME / "cam-tasks.json"
TEAMS_DIR = ROOT / "config" / "teams"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Team definitions: config/teams/*.json + built-in day-to-day teams
# ---------------------------------------------------------------------------

BUILTIN_TEAMS: list[dict] = [
    {
        "id": "team.research",
        "name": "Research Team",
        "keywords": ["research", "paper", "arxiv", "find out", "learn", "investigate",
                     "look up", "study", "explore", "compare"],
        "lead_role": "research-lead",
        "workers": ["vault-scout", "memory-scout", "arxiv-scout", "github-scout",
                    "scholar-scout", "apis-scout", "trends-scout"],
    },
    {
        "id": "team.memory",
        "name": "Memory Team",
        "keywords": ["remember", "memory", "notes", "vault", "recall", "history"],
        "lead_role": "memory-curator",
        "workers": ["vault-scout", "memory-scout"],
    },
    {
        "id": "team.ops",
        "name": "Ops Team",
        "keywords": ["system", "health", "status", "workspace", "repo", "scan",
                     "audit", "check", "fix"],
        "lead_role": "ops-lead",
        "workers": ["repo-scanner", "vault-scout", "runtime-auditor"],
    },
    {
        "id": "team.comms",
        "name": "Comms Team",
        "keywords": ["message", "draft", "write", "email", "brief", "summary",
                     "summarize", "compose"],
        "lead_role": "comms-lead",
        "workers": ["vault-scout", "memory-scout", "drafter"],
    },
]


def load_teams() -> list[dict]:
    teams = [dict(t) for t in BUILTIN_TEAMS]
    if TEAMS_DIR.exists():
        for fp in sorted(TEAMS_DIR.glob("*.json")):
            try:
                doc = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            words = re.findall(r"[a-z]{4,}", (doc.get("purpose") or "").lower())
            teams.append({
                "id": doc.get("id") or f"team.{fp.stem}",
                "name": doc.get("name") or fp.stem,
                "keywords": list(dict.fromkeys(words))[:12],
                "lead_role": doc.get("lead_role") or "lead",
                "workers": [m.get("role", "agent") for m in (doc.get("members") or [])][:6]
                           or ["vault-scout", "memory-scout"],
                "from_config": fp.name,
            })
    return teams


def pick_team(goal: str, teams: list[dict] | None = None) -> dict:
    teams = teams or load_teams()
    low = (goal or "").lower()
    best, best_score = None, 0
    for t in teams:
        score = sum(1 for k in t.get("keywords") or [] if k in low)
        if score > best_score:
            best, best_score = t, score
    return best or teams[0]


# ---------------------------------------------------------------------------
# Subagent work units (real work, graceful degradation)
# ---------------------------------------------------------------------------

def _http_json(url: str, timeout: float = 10.0, headers: dict | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": "cam-live/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def work_vault_scout(goal: str, ctx: dict) -> dict:
    from cam_brain import vault_search
    hits = vault_search(goal, limit=5)
    return {
        "summary": f"{len(hits)} vault notes matched",
        "findings": [f"{h['path']}: {h['snippet']}" for h in hits if h.get("snippet")],
    }


def work_memory_scout(goal: str, ctx: dict) -> dict:
    memory = ctx.get("memory")
    hits = memory.recall(goal, limit=5) if memory else []
    return {
        "summary": f"{len(hits)} memories matched",
        "findings": [h["text"] for h in hits],
    }


def work_arxiv_scout(goal: str, ctx: dict) -> dict:
    terms = " ".join(re.findall(r"[a-z0-9]{3,}", goal.lower())[:6]) or "ai assistant"
    url = ("https://export.arxiv.org/api/query?search_query=all:" +
           urllib.parse.quote(terms) + "&max_results=5&sortBy=submittedDate&sortOrder=descending")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "cam-live/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml = resp.read().decode("utf-8", errors="ignore")
        titles = re.findall(r"<title>(.*?)</title>", xml, re.S)[1:6]
        titles = [re.sub(r"\s+", " ", t).strip() for t in titles]
        return {"summary": f"{len(titles)} recent arXiv papers",
                "findings": titles}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"summary": "arXiv unreachable from this network", "findings": [],
                "degraded": str(exc)[:120]}


def work_github_scout(goal: str, ctx: dict) -> dict:
    terms = " ".join(re.findall(r"[a-z0-9]{3,}", goal.lower())[:5]) or "assistant"
    url = ("https://api.github.com/search/repositories?q=" +
           urllib.parse.quote(terms) + "&sort=stars&per_page=5")
    try:
        doc = _http_json(url)
        items = doc.get("items") or []
        return {
            "summary": f"{len(items)} GitHub repos matched",
            "findings": [f"{i['full_name']} (★{i['stargazers_count']}): "
                         f"{(i.get('description') or '')[:100]}" for i in items],
        }
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        return {"summary": "GitHub unreachable from this network", "findings": [],
                "degraded": str(exc)[:120]}


_HYPHEN_MODS: dict[str, object] = {}


def _load_tool(filename: str):
    """Import one of the hyphen-named tool scripts (scholar-search.py etc.)."""
    if filename in _HYPHEN_MODS:
        return _HYPHEN_MODS[filename]
    path = ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_").rstrip(".py"), path)
    if spec is None or spec.loader is None:
        raise ImportError(filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _HYPHEN_MODS[filename] = mod
    return mod


def _goal_terms(goal: str, n: int = 4) -> str:
    stop = {"research", "find", "look", "task", "about", "into", "with", "what", "the"}
    words = [w for w in re.findall(r"[a-z0-9]{3,}", goal.lower()) if w not in stop]
    return " ".join(words[:n])


def work_scholar_scout(goal: str, ctx: dict) -> dict:
    """Google Scholar via scripts/scholar-search.py (SerpAPI live, fixture offline)."""
    try:
        sch = _load_tool("scholar-search.py")
        query = _goal_terms(goal) or "ai assistants"
        cfg = sch.load_config()
        payload = None
        if (cfg.get("serpapi_key") or "").strip():
            try:
                payload = sch.fetch_serpapi({"engine": "google_scholar", "q": query})
            except Exception:
                payload = None
        if payload is None:
            payload = sch.offline_payload(query, None)
        results = (payload.get("organic_results") or payload.get("results") or [])[:5]
        findings = []
        for r in results:
            title = r.get("title") or r.get("name") or "untitled"
            snippet = (r.get("snippet") or "")[:100]
            findings.append(f"{title} — {snippet}".strip(" —"))
        mode = "live SerpAPI" if not payload.get("offline") else "offline fixture"
        return {"summary": f"{len(findings)} scholar results ({mode})", "findings": findings}
    except Exception as exc:
        return {"summary": "scholar tool unavailable", "findings": [], "degraded": str(exc)[:120]}


def work_apis_scout(goal: str, ctx: dict) -> dict:
    """Free/public API catalog via scripts/public-apis-search.py."""
    try:
        pas = _load_tool("public-apis-search.py")
        cfg = pas.load_config()
        try:
            text, provider = pas.read_catalog_text(cfg, offline=False, refresh=False)
        except Exception:
            text, provider = pas.read_catalog_text(cfg, offline=True, refresh=False)
        entries = pas.parse_catalog(text)
        hits = pas.filter_entries(
            entries, query=_goal_terms(goal), category=None, auth=None,
            https_only=False, cors=None)[:5]
        findings = [
            f"{e.get('name')} ({e.get('category')}, auth: {e.get('auth') or 'none'}): "
            f"{(e.get('description') or '')[:90]}" for e in hits]
        if provider.startswith("fixture"):
            provider = "offline fixture"
        return {"summary": f"{len(findings)} public APIs matched ({provider})",
                "findings": findings}
    except Exception as exc:
        return {"summary": "public-apis tool unavailable", "findings": [], "degraded": str(exc)[:120]}


def work_trends_scout(goal: str, ctx: dict) -> dict:
    """Google Trends open datasets via scripts/google-trends-search.py."""
    try:
        gts = _load_tool("google-trends-search.py")
        cfg = gts.load_config()
        try:
            entries, provider = gts.load_catalog(cfg, offline=False, refresh=False)
        except Exception:
            entries, provider = gts.load_catalog(cfg, offline=True, refresh=False)
        hits = gts.filter_entries(entries, query=_goal_terms(goal),
                                  year=None, ext=None, folder=None)[:5]
        findings = [f"{e.get('name')} ({e.get('year') or 'n/a'}): {e.get('path')}" for e in hits]
        return {"summary": f"{len(findings)} trends datasets matched ({provider})",
                "findings": findings}
    except Exception as exc:
        return {"summary": "google-trends tool unavailable", "findings": [], "degraded": str(exc)[:120]}


def work_repo_scanner(goal: str, ctx: dict) -> dict:
    counts: dict[str, int] = {}
    total = 0
    for p in ROOT.rglob("*"):
        if any(part in {".git", "node_modules", "integrations"} for part in p.parts):
            continue
        if p.is_file():
            total += 1
            counts[p.suffix or "(none)"] = counts.get(p.suffix or "(none)", 0) + 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
    return {
        "summary": f"workspace holds {total} files",
        "findings": [f"{ext}: {n} files" for ext, n in top],
    }


def work_runtime_auditor(goal: str, ctx: dict) -> dict:
    findings = []
    for name in ("cam-memory.json", "cam-inbox.jsonl", "cam-tasks.json", "cam-reminders.json"):
        p = RUNTIME / name
        findings.append(f"{name}: {'present, ' + str(p.stat().st_size) + ' bytes' if p.exists() else 'not created yet'}")
    return {"summary": "runtime stores audited", "findings": findings}


def work_drafter(goal: str, ctx: dict) -> dict:
    llm = ctx.get("llm")
    if llm:
        text = llm.chat([
            {"role": "system", "content": "You are Cam's comms drafter. Produce a short, "
             "clear draft for Aaron. Plain text."},
            {"role": "user", "content": goal},
        ], max_tokens=350)
        if text:
            return {"summary": "draft written with live LLM", "findings": [text]}
    words = re.findall(r"[A-Za-z0-9''\-]+", goal)
    return {
        "summary": "outline drafted (no live LLM)",
        "findings": [
            f"Draft outline for: {goal}",
            "1. Purpose — " + " ".join(words[:8]),
            "2. Key points — pulled from vault + memory findings in this task",
            "3. Ask / next step — Aaron decides",
        ],
    }


WORKERS: dict[str, Callable[[str, dict], dict]] = {
    "vault-scout": work_vault_scout,
    "memory-scout": work_memory_scout,
    "arxiv-scout": work_arxiv_scout,
    "github-scout": work_github_scout,
    "scholar-scout": work_scholar_scout,
    "apis-scout": work_apis_scout,
    "trends-scout": work_trends_scout,
    "repo-scanner": work_repo_scanner,
    "runtime-auditor": work_runtime_auditor,
    "drafter": work_drafter,
}

# roles from config/teams/*.json map onto the nearest real worker
ROLE_ALIASES = {
    "agi-scout": "arxiv-scout",
    "agi-analyst": "scholar-scout",
    "agi-synthesist": "drafter",
    "capability-broker": "runtime-auditor",
    "qa": "runtime-auditor",
    "memory-curator": "memory-scout",
}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class TeamOrchestrator:
    """Cam-as-head-agent task board with parallel subagent execution."""

    def __init__(self, *, memory=None, llm=None, notify: Callable[[dict], None] | None = None,
                 max_workers: int = 8) -> None:
        self.memory = memory
        self.llm = llm
        self.notify = notify
        self.teams = load_teams()
        self.tasks: list[dict] = []
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cam-agent")
        self._load()

    def _load(self) -> None:
        if TASKS_PATH.exists():
            try:
                self.tasks = list(json.loads(TASKS_PATH.read_text(encoding="utf-8")).get("tasks") or [])
            except (json.JSONDecodeError, OSError):
                self.tasks = []
        # anything stuck "running" from a previous process is stale
        for t in self.tasks:
            if t.get("status") == "running":
                t["status"] = "interrupted"

    def _save(self) -> None:
        TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        TASKS_PATH.write_text(
            json.dumps({"updated": utc_now(), "tasks": self.tasks[-100:]},
                       indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")

    def list_tasks(self, limit: int = 30) -> list[dict]:
        with self._lock:
            return [dict(t) for t in self.tasks[-limit:]]

    def running_count(self) -> int:
        with self._lock:
            return sum(1 for t in self.tasks if t.get("status") == "running")

    def get(self, task_id: str) -> dict | None:
        with self._lock:
            for t in self.tasks:
                if t["id"] == task_id:
                    return dict(t)
        return None

    # -- dispatch ----------------------------------------------------------------

    def dispatch(self, goal: str, wait: bool = False) -> dict:
        goal = (goal or "").strip()
        team = pick_team(goal, self.teams)
        roles = [ROLE_ALIASES.get(r, r) for r in (team.get("workers") or [])]
        roles = [r for r in roles if r in WORKERS] or ["vault-scout", "memory-scout"]
        roles = list(dict.fromkeys(roles))
        task = {
            "id": str(uuid.uuid4())[:8],
            "goal": goal,
            "team": team["id"],
            "team_name": team["name"],
            "lead": team.get("lead_role", "lead"),
            "head_agent": "Cam",
            "status": "running",
            "created": utc_now(),
            "subtasks": [
                {"id": f"{i+1}", "agent": role, "role": role, "status": "queued",
                 "summary": None, "findings": [], "elapsed_ms": None}
                for i, role in enumerate(roles)
            ],
            "subtask_count": len(roles),
            "result": None,
        }
        with self._lock:
            self.tasks.append(task)
            self._save()
        runner = self._pool.submit(self._run_task, task["id"])
        if wait:
            runner.result(timeout=120)
            return self.get(task["id"]) or task
        return dict(task)

    def _run_task(self, task_id: str) -> None:
        task = self.get(task_id)
        if not task:
            return
        goal = task["goal"]
        ctx = {"memory": self.memory, "llm": self.llm}
        t0 = time.monotonic()

        def run_sub(sub: dict) -> dict:
            s0 = time.monotonic()
            self._update_sub(task_id, sub["id"], status="running")
            try:
                out = WORKERS[sub["agent"]](goal, ctx)
                status = "done"
            except Exception as exc:  # subagent crash must not sink the team
                out = {"summary": f"agent error: {exc}", "findings": []}
                status = "failed"
            elapsed = int((time.monotonic() - s0) * 1000)
            self._update_sub(task_id, sub["id"], status=status,
                             summary=out.get("summary"),
                             findings=out.get("findings") or [],
                             degraded=out.get("degraded"),
                             elapsed_ms=elapsed)
            return out

        futures = [self._pool.submit(run_sub, dict(sub)) for sub in task["subtasks"]]
        for f in futures:
            try:
                f.result(timeout=90)
            except Exception:
                pass

        done = self.get(task_id) or task
        findings: list[str] = []
        for sub in done["subtasks"]:
            for line in sub.get("findings") or []:
                findings.append(f"[{sub['agent']}] {line}")
        wall_ms = int((time.monotonic() - t0) * 1000)
        agent_ms = sum(s.get("elapsed_ms") or 0 for s in done["subtasks"])
        synthesis = self._synthesize(goal, done, findings)
        self._update_task(task_id, status="done", finished=utc_now(),
                          wall_ms=wall_ms, agent_ms=agent_ms,
                          parallel_speedup=round(agent_ms / wall_ms, 2) if wall_ms else None,
                          result=synthesis)
        if self.notify:
            body = synthesis if len(synthesis) < 900 else synthesis[:880] + "…"
            self.notify({
                "subject": f"Task done · {done['team_name']}",
                "body": f"“{goal[:100]}” finished — {len(done['subtasks'])} subagents, "
                        f"{wall_ms} ms wall.\n\n{body}",
                "kind": "task_done",
                "meta": {"task_id": task_id},
            })

    def _synthesize(self, goal: str, task: dict, findings: list[str]) -> str:
        if self.llm:
            text = self.llm.chat([
                {"role": "system", "content":
                 "You are Cam's team lead. Synthesize the subagent findings into a short, "
                 "useful answer for Aaron. Cite which agent found what. Plain text."},
                {"role": "user", "content":
                 f"Goal: {goal}\n\nFindings:\n" + "\n".join(findings[:40])},
            ], max_tokens=450)
            if text:
                return text
        if not findings:
            return (f"The {task['team_name']} finished “{goal}” but found nothing solid "
                    "on this machine/network. Try rephrasing, or connect a live LLM for deeper work.")
        top = "\n".join("• " + f for f in findings[:12])
        return (f"{task['team_name']} report on “{goal}” "
                f"({len(task['subtasks'])} subagents in parallel):\n{top}")

    # -- state updates ---------------------------------------------------------

    def _update_sub(self, task_id: str, sub_id: str, **fields) -> None:
        with self._lock:
            for t in self.tasks:
                if t["id"] == task_id:
                    for s in t["subtasks"]:
                        if s["id"] == sub_id:
                            s.update({k: v for k, v in fields.items() if v is not None or k == "summary"})
                    break
            self._save()

    def _update_task(self, task_id: str, **fields) -> None:
        with self._lock:
            for t in self.tasks:
                if t["id"] == task_id:
                    t.update(fields)
                    break
            self._save()
