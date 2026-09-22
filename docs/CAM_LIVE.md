# Cam Live — the day-to-day assistant that actually runs

> One command. No build step. No cloud dependency. Gets smarter when you
> connect a model, but never goes dumb or deaf without one.

```bash
python3 scripts/cam-live-server.py
# → open http://127.0.0.1:8899
```

## Why this exists (what was broken before)

| Symptom Aaron hit | Root cause | Fix |
| --- | --- | --- |
| "Reasoning core isn't working" | `cam_reply()` was keyword→canned-phrase matching; `cam_reason.py` was an explicit *dry-run stub* that never produced answers | `scripts/cam_brain.py` — a real reasoning core: live LLM when configured, capable local cortex always (memory, vault retrieval, math, time, reminders, tasks) |
| "It's not listening" | Mic turns were rejected with HTTP 403 unless a FunASR voice enrollment existed — and enrollment deps were never installed | Open-mic fallback: without an enrolled profile, Cam accepts your mic (both in Cam Live and the old converse server). Enroll later to get Aaron-only verification back |
| "It's not sending me messages" | No delivery path existed; outbound was gated behind the empty Inkbox submodule | `scripts/cam_messages.py` — real inbox + reminders that fire + browser notifications + optional push (ntfy/webhook) gated by `switch.outbound` |
| "Object recognition… nothing" | PaddleDetection / Pupil are empty submodules; camera frames were logged as "spikes" and discarded | `scripts/cam_vision.py` + the live UI: in-browser coco-ssd (80 real classes) when online, numpy local visual cortex (color/shape/position identification) when offline |
| "Agents/teams never do anything" | `config/teams/*.json` was descriptive only — no executor | `scripts/cam_teams.py` — Cam is head agent; team leads decompose goals; subagents execute **in parallel** (thread pool) and report back to your inbox |

## Talk to Cam

Everything works by chat (typed or voice — mic button uses the browser's
speech recognition; replies are spoken via speech synthesis):

- `remember that my dentist is Tuesday at 3pm` — durable memory (`data/runtime/cam-memory.json`)
- `do you remember my dentist?` — recall
- `remind me to take out the trash in 20 minutes` / `…at 5pm` — fires a
  message + notification when due
- `note: pick up dry cleaning Friday` — appends to today's note in
  `vault/00-Inbox/` (opens in Obsidian, searchable immediately)
- `weather in Buffalo` — live conditions + today's range via open-meteo
  (keyless). Say `remember that I live in <city>` once and plain
  `weather?` uses your city
- `brief` / `daily brief` — on-demand day summary; Cam also sends one
  proactive Daily Brief message each morning (default 8am NY; set
  `CAM_BRIEF_HOUR`, or `-1` to disable)
- `task: research small language models for the home lab` — dispatches a
  team; subagents work in parallel; results land in Messages
- `what do you see?` — answers from the latest camera detections
- `what is 17 * 4 + 12` · `what time is it` · `status`
- anything else — answered by the connected LLM with memory/vault
  grounding, or by the grounded local cortex if no model is connected

## Connecting a real language model (recommended)

Any one of these makes open-ended conversation fully live:

```bash
# local, private, free — install Ollama on your machine, then:
ollama pull llama3.2            # Cam auto-detects http://127.0.0.1:11434

# or any OpenAI-compatible server (LM Studio, llama.cpp, vLLM, OpenRouter):
export CAM_LLM_BASE_URL=http://127.0.0.1:1234/v1
export CAM_LLM_MODEL=your-model  CAM_LLM_API_KEY=...   # key optional

# or hosted:
export OPENAI_API_KEY=sk-...        # optional CAM_OPENAI_MODEL
export ANTHROPIC_API_KEY=sk-ant-... # optional CAM_ANTHROPIC_MODEL
```

The header pill shows which brain is active (`brain: ollama` vs
`brain: local cortex`).

## Getting messages on your phone (optional, off by default)

Per `.clinerules`, outbound stays off until Aaron flips it:

```bash
export CAM_OUTBOUND=on
export CAM_NTFY_TOPIC=aarons-cam        # install the ntfy app, subscribe to the topic
# and/or
export CAM_WEBHOOK_URL=https://…        # any JSON webhook (Slack/Discord/…)
```

Every inbox message then also pushes to your phone. Attempts are logged
to `data/runtime/cam-outbox.jsonl`.

## Object identification

- **Online browser** → the UI loads TensorFlow.js coco-ssd and labels 80
  real object classes (person, cup, laptop, dog…) with boxes, live if
  you tick "live". Detections are posted to the server so the brain can
  answer "what do you see?".
- **Offline / restricted network** → frames go to the numpy visual
  cortex on the server, which segments salient regions and identifies
  them honestly by size/color/shape/position ("large red rectangular
  object, center", "skin-tone region — person candidate").
- No camera? Use **Analyze image…** to identify objects in any photo.

## Agent teams

Teams come from `config/teams/*.json` plus built-ins (Research, Memory,
Ops, Comms). Dispatch from the UI panel or by chatting `task: …`.
Each task shows its team, lead, and every subagent's live status and
elapsed time; `parallel speedup ×N` shows the win from running
subagents concurrently. Results are synthesized (LLM when available)
and delivered to Messages.

The Research Team now runs **7 parallel scouts**, including three
previously-dormant integrations wired in as subagents:

- `scholar-scout` — Google Scholar via `scripts/scholar-search.py`
  (live with `SERPAPI` key, offline fixtures otherwise)
- `apis-scout` — the public-apis catalog (`scripts/public-apis-search.py`)
- `trends-scout` — Google Trends open datasets (`scripts/google-trends-search.py`)
- plus vault, memory, arXiv, and GitHub scouts

## Sending Cam messages from other scripts and loops

Any cron job, loop, or script can drop a message into your inbox:

```bash
python3 scripts/cam-notify.py --subject "Nightly triage" --body "3 findings…"
```

`scripts/loop-run.py` already does this — every loop run now lands a
report in Messages instead of only a JSONL nobody reads.

## InfiniteMind slow-path reasoning

`cam_reason.py`'s slow path enriches with the InfiniteMind
logic/abduction adapter when the submodule is present. Run once:

```bash
git submodule update --init integrations/infinitemind
```

This also turns the 7 `test_cam_infinitemind` tests green.

## Voice identity (Aaron-only mode)

Out of the box Cam listens openly so she is never deaf. To restore
strict Aaron-only verification: enroll with `scripts/aaron-voice-enroll.py`,
and set `"open_mic_when_not_enrolled": false` in
`config/identity/aaron-voice-gate.json`. Enrolled profiles are verified
exactly as before.

## Files

- `scripts/cam-live-server.py` — the app (stdlib HTTP server, port 8899)
- `scripts/cam_brain.py` · `cam_teams.py` · `cam_messages.py` · `cam_vision.py`
- `companions/live/` — the web UI (vanilla JS, no build)
- `data/runtime/cam-*.json*` — memory, inbox, tasks, reminders (gitignored)
- `scripts/test_cam_live.py` — 26 tests covering all of the above
