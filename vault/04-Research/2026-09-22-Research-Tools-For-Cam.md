# Research Brief — Tools for research assistance (Cam, 2026-09)

**Accessed:** 2026-09-22  
**Question:** Which research tools, literature APIs, and memory frameworks should Cam route through when Aaron asks for source-backed research — and which are worth wiring next?  
**Method:** Web survey (2026 comparisons + primary API docs quoted in them) checked against Cam's existing connectors (`sense.web.scholar`, `motor.public_apis`, `motor.google_trends`, MemoryBear).  
**Gate:** Propose-only for new integrations; today's change adds no external calls.

## Summary

- Combine free literature APIs rather than picking one: **Semantic Scholar Graph API** for AI/ML discovery, citation traversal and snippets; **OpenAlex** for cross-domain metadata, DOI resolution and citation edges; **Crossref** for DOI/publisher metadata; **arXiv Atom API** for fresh preprints; **Unpaywall** for legal OA PDFs. [1][2][3]
- Rate etiquette matters for a 24/7 agent: arXiv ≈ 1 request / 3 s; Semantic Scholar 1 req/s with a key (anonymous pool 429s often); Crossref polite pool with `mailto`; **OpenAlex became key-required and credit-metered in Feb 2026** (free key ≈ $1/day of usage). [1][3]
- Among agentic research products, reviewers converge on **Elicit** (systematic review / structured extraction), **Undermind** (slow, high-recall narrow technical search), **Consensus** (fast evidence-weighted yes/no), **Semantic Scholar** (best free discovery), **ResearchRabbit** (citation graph), with general Deep Research modes (OpenAI, Gemini, Perplexity) for web-wide synthesis. [4][5][6]
- For agent memory, the open-source field splits into fact extraction (**Mem0**), stateful runtime with tiers (**Letta**), bi-temporal knowledge graph (**Graphiti/Zep**), and evolving note networks (**A-MEM**, **MemOS/MemoryOS**); benchmarks (RealMem, EvoMemBench) find no universal winner and flag *fact revision* as the bottleneck. [7][8][9]

## Literature APIs Cam should know

| API | Best at | Auth / cost | Etiquette | Cam wiring |
|---|---|---|---|---|
| arXiv Atom API | newest preprints by category | none, free | 1 req / 3 s, single connection | already: `scripts/agi-research-scan.py` (`sense.web.arxiv`) |
| Semantic Scholar Graph | AI/ML search, citations both directions, snippets, batch lookup | optional key (`S2_API_KEY`) | 1 req/s with key; backoff on 429 | **proposed** beside Scholar in `scripts/scholar-search.py` |
| OpenAlex | cross-domain metadata, DOI / arXiv id resolution, `cites:` edges, cached full text | free key required (metered) | polite `mailto`; batch ids ≤ 50/req | **proposed** for DOI hygiene in scan proposals |
| Crossref REST | DOI + publisher metadata, fallback when others throttle | none | polite pool with `mailto` | proposed (via `public-apis` catalog first) |
| Unpaywall | legal OA PDF resolution | none (email) | 100k/day | proposed |
| Google Scholar (SerpAPI) | catch-all incl. books/theses | `SERPAPI_API_KEY` | vendor quota | already: `sense.web.scholar` |
| Google Trends data | public-interest time series | none | GitHub index | already: `motor.google_trends` |

Sources: [1] Firecrawl "5 Academic Search APIs Compared" (2026) · [2] IntuitionLabs "Research Paper APIs 2026" · [3] research-paper-lifecycle-skills `api-notes.md` (verified 2026-06).

## Agentic research assistants (products)

| Tool | Strength | Caveat | Use for Cam |
|---|---|---|---|
| Elicit | PRISMA-style screening, structured extraction to columns | paid tiers for scale | template for Cam's `Research Brief` tables |
| Undermind | 3–20 min deep search, citation chasing, "evidence strength" tags | slow; academic vs commercial pricing | model for a **slow-path** Cam research loop |
| Consensus | Consensus Meter on yes/no claims; inline citations | narrow; capped deep searches | fast evidence check pattern |
| Semantic Scholar | free discovery, TLDRs, citation graph | paper-level citations | API already free — wire it |
| ResearchRabbit / Connected Papers | citation-map exploration | UI-first | pattern for `paper_similarity_cluster` (`center.dl`) |
| Deep Research (OpenAI / Gemini / Perplexity) | broad web synthesis with reasoning trace | cost, variable citation quality | only via Aaron-approved keys; never outbound |

Sources: [4] Official A.I Ranking (tested Jul 2026) · [5] Awesome Agents "Best AI Research Assistants 2026" · [6] AI Research Assistant Comparison 2026 (10 tools).

## Memory frameworks (for experience + research recall)

| Framework | Model of memory | Fit with Cam |
|---|---|---|
| Mem0 | extract facts → ADD/UPDATE/DELETE/NOOP by similarity | close to `mesh/facts` curator rules |
| Letta (MemGPT) | core / recall / archival tiers | mirrors HMO primary/secondary/archive already applied |
| Graphiti (Zep) | bi-temporal graph, `valid_at`/`invalid_at` | candidate for *when was this true* on Aaron facts |
| A-MEM | evolving linked notes | resembles the Obsidian vault + smart-second-brain |
| MemOS / MemoryOS | OS-style scheduling of memory types | pattern for MemoryBear tiers |
| MemRL | RL-learned utility (Q-values) of episodic memories | directly relevant to **which experiences to reuse** |

Sources: [7] digitalapplied / dreaming.press comparisons (2026) · [8] RealMem (Findings of ACL 2026) · [9] EvoMemBench arXiv:2605.18421 · MemRL arXiv:2601.03192.

## Counter-arguments / risks

- Comparison blogs disagree on scores and pricing; treat their rankings as pointers, verify against each vendor's docs before wiring.
- Key-metered APIs (OpenAlex) turn "free" into a budget line — model cost per question, and prefer `public-apis` catalog entries first.
- Adopting a memory *framework* wholesale conflicts with "prompts + config over new code"; adopt interfaces (validity windows, utility scores) inside MemoryBear/mesh instead.

## Recommendation

1. Wire Semantic Scholar + OpenAlex lookups behind `sense.web.scholar` as a fallback chain (propose-only PR; keys via Aaron secrets).  
2. Adopt Elicit-style extraction columns in the `Research Brief` template for scan proposals.  
3. Borrow MemRL's idea — score each stored experience by realised utility — inside Cam's predictive cortex (`surprise`, `td_value`) rather than adding a new framework.

## Sources

- https://www.firecrawl.dev/blog/ai-agents-search-academic-papers — accessed 2026-09-22  
- https://intuitionlabs.ai/articles/research-paper-apis-scientific-literature — accessed 2026-09-22  
- https://github.com/ShaishavMaisuria/research-paper-lifecycle-skills/blob/main/skills/find-papers/references/api-notes.md — accessed 2026-09-22  
- https://github.com/alisoroushmd/academic-research-mcp — accessed 2026-09-22  
- https://officialairanking.com/rankings/2026-07-31-the-ai-academic-research-assistants-we-recommend/ — accessed 2026-09-22  
- https://awesomeagents.ai/tools/best-ai-research-assistants-2026/ — accessed 2026-09-22  
- https://perplexityaimagazine.com/ai-tools/ai-research-assistant-comparison-2026/ — accessed 2026-09-22  
- https://aitrendtool.com/tools/undermind — accessed 2026-09-22  
- https://www.digitalapplied.com/blog/open-source-agent-memory-mem0-letta-zep-compared — accessed 2026-09-22  
- https://dreaming.press/posts/open-source-agent-memory-libraries-mem0-zep-letta-cognee.html — accessed 2026-09-22  
- https://aclanthology.org/2026.findings-acl.703.pdf — RealMem — accessed 2026-09-22  
- https://arxiv.org/abs/2605.18421 — EvoMemBench — accessed 2026-09-22  
- https://arxiv.org/abs/2601.03192 — MemRL — accessed 2026-09-22  
