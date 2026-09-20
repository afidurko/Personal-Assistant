# Cam Home Build — one home for all agents and environments

**Status:** master build plan (authorized by Aaron, 2026-09-20).
**Manifest:** [`config/system/build-plan.json`](../config/system/build-plan.json) — machine-readable, validated by `scripts/build-plan-check.py`.
**Stakes:** this home is the foundation everything else depends on. If this does not work, nothing else we made matters — so every phase has a hard exit check, and nothing is marked done without one passing.

This plan uses all existing memory: the organism bus (`config/system/pieces.json`),
the Brodmann connectome (`config/connectome/`), the workspace registry
(`config/workspaces/registry.json`), the persistence bundle, the vault, and the
mesh distillates. It invents nothing that memory already answers.

---

## 1. Priority ladder (hard order, encoded in the manifest)

| Rank | Priority | Meaning | Where it is enforced |
|---|---|---|---|
| **1** | `real_world_execution` | The assistant actually works with real-life integrations — it can **execute** (send, act, run) and **receive** (callbacks, replies, results). | `server/core/motor-executor.ts`, null stack synapses, Inkbox channels, connectome switches |
| **2** | `agi_assist` | Superman/AGI abilities exist **to assist priority 1** — research scan, sLM/DL cortex, Higgsfield training, unlimited subagent teams. Never an end in themselves. | `config/teams/`, `config/enhancement/`, `motor.higgsfield`, `switch.cam_enhance` |
| **3** | `human_ultimate_say` | Aaron has ultimate say. Cam and **every subagent it spawns inherit Aaron's morals and ethics** — privileges inherit only as a subset; `aaron_only` powers never transfer; kill switch always wins. | `config/swarm/privileges.json`, `switch.kill`, `requires_human` pipeline stages, `identity/` |
| **4** | `interactivity_presence` | Aaron can see what's running / working / needs help, suggest changes, and talk to a **living Cam avatar** with believable human-grade speech and facial muscles. Auto-enhancement keeps the project improving. | home UI + live activity feed, needs-attention, avatar tiers below, enhancement loop |

Rank order is a tie-breaker rule: when two work items compete, the lower rank
number wins resources. Priority 2 exists in service of priority 1; priorities 1
and 2 both stop instantly at priority 3's gates.

---

## 2. The home: what "new home for all agents and environments" means

This repository **is** the home. Nothing moves; everything docks.

```text
Personal-Assistant repo (this home)
├── Brain maps        config/connectome/  (areas, tracts, switches, motors)
├── Organism bus      config/system/pieces.json  → scripts/cam-system.py --smoke
├── Agent teams       config/teams/ + config/swarm/ (unlimited subagents, subset privileges)
├── All environments  config/workspaces/registry.json  (vault areas, scan workspaces,
│                     integration checkouts, Cline coding workspaces — every agent
│                     and every other environment registers here)
├── Memory            vault/ + mesh namespaces + MemoryBear + persistence bundle
├── Presence          server/ + src/ + companions/ + visualizations/ (home UI, converse, 3D cortex)
└── Effectors         integrations/*  (Cline, Jarvis, VoiceStudio, LLMAvatarTalk,
                      Higgsfield, Inkbox, public-apis, …)
```

**Docking rule:** an agent or environment is "home" when it (a) appears in
`config/workspaces/registry.json` or `config/system/pieces.json`, (b) has a
connectome node (sense/hotspot/motor), and (c) distills outcomes into mesh/vault.
The build-plan checker enforces that every piece referenced by this plan exists.

---

## 3. Cam avatar — full integration process (priority 4, built to human grade)

Persona source of truth stays `config/persona/voice.json` (32, Argentine,
soft airy calm English, blue eyes, brown hair) and the locked portrait
`identity/persona/cam-face.jpg`. Three tiers, one contract.

### 3.1 Muscle-grade spec (the bar every tier must hit)

| Dimension | Target |
|---|---|
| Facial rig | **ARKit-52 blendshape set** (industry standard; maps to FACS action units) |
| Speech muscles | Viseme set (≥15 visemes) with co-articulation smoothing — no flapping jaw |
| Micro-life | Blink 12–20/min, gaze saccades, breathing chest/nostril motion, idle micro-expressions |
| Frame rate | ≥25 fps sustained on the render host |
| Latency | First lip movement ≤ 500 ms after TTS audio starts |
| Believability exit check | Aaron watches a 60-second side-by-side (portrait vs. animated) and judges the speech and facial muscles believable at human grade |

### 3.2 Tier 1 — `hf_realtime` (primary; Hugging Face models, runs local)

The everyday avatar. All models are open weights pulled from Hugging Face into
a local cache (never committed to git).

```text
Aaron mic ──► Aaron voice gate (FunASR CAM++ voiceprint — existing switch.identity)
        ──► ASR: openai/whisper-large-v3 (HF) or VoiceStudio local ASR
        ──► Cam brain (nullclaw + connectome kernel — never the avatar's own LLM)
        ──► TTS: VoiceStudio local clone (primary) · hexgrad/Kokoro-82M (HF fallback)
        ──► audio + phoneme/viseme timeline
        ──► Face animation, two HF models composited:
              · TMElyralab/MuseTalk   — real-time audio-driven lip sync (speech muscles)
              · KwaiVGI/LivePortrait  — expression retargeting (brows, lids, gaze,
                                        blink, head pose — facial muscles) driven by
                                        an ARKit-blendshape control stream
        ──► render to home UI (`src/components/CamPresence.tsx`) + companions
```

Integration process (each step lands as its own PR with an exit check):

1. **Model provisioning** — `scripts/avatar-fetch-models.py`: resolves the HF
   model list from the manifest, downloads to a local cache dir, verifies
   checksums, refuses when egress is blocked (offline mode reports what is
   missing). Weights are opt-in downloads, like VoiceStudio's OmniVoice rule.
2. **Avatar service** — `scripts/cam-avatar-server.py` (localhost, sibling of
   `scripts/cam-converse-server.py`): `POST /avatar/speak {text}` → AvatarFrame
   timeline to the home UI. **Landed at tier 0**: `scripts/cam_avatar.py`
   procedural engine (15 visemes, co-articulation, blink/gaze/brow micro-life,
   ARKit-52 sparse frames) drives the Home Live SVG rig today; MuseTalk /
   LivePortrait upgrade the same endpoints in place when weights land.
3. **Connectome wiring** — new nodes `motor.avatar` (channel `hf_realtime`),
   `sense.avatar.state`, `hotspot.avatar`; gated by `switch.presence`, silenced
   by `switch.kill`. Mirrors the VoiceStudio motor pattern.
4. **Home UI binding** — `CamPresence.tsx` swaps the static portrait for the
   frame/blendshape stream when the avatar service is up; falls back to the
   portrait automatically (fail-soft, like the cortex GLB fallback).
5. **Checks** — `scripts/avatar-check.py` (offline contract: manifest models
   listed, portrait exists, service contract schema) + muscle-grade smoke that
   measures fps/latency/blink cadence on a canned utterance when weights are
   present.

### 3.3 Tier 2 — `studio_full_presence` (existing memory, unchanged)

LLMAvatarTalk on Aaron's GPU studio: RIVA ASR/TTS + NVIDIA **Audio2Face**
(true muscle simulation) + optional Unreal Metahuman body. Highest fidelity;
used when Aaron starts a presence session. Already documented in
`config/integrations/llmavatartalk.md`; the brain remains Cam/nullclaw.

### 3.4 Tier 3 — `custom_finetune` (Higgsfield path)

When Tier 1 quality plateaus, fine-tune the avatar identity on Aaron's terms:
LivePortrait/MuseTalk-family checkpoints fine-tuned on approved footage of the
Cam persona via **`integrations/higgsfield`** multi-node GPU training
(`motor.higgsfield`, dry-run default, live only under `switch.cam_enhance` +
`CAM_HIGGSFIELD_LIVE`). Output checkpoints feed back into Tier 1's model cache.
Serving hand-off via `integrations/litserve` per existing Higgsfield policy.

### 3.5 One contract for all tiers

Every tier consumes the same input (`text + emotion tag`) and emits the same
`AvatarFrame` stream (`blendshapes: Record<arkit_key, 0..1>`, `viseme`,
`audio_pts`). Tiers are swappable without touching the brain or the UI.

---

## 4. Updates auto-populate to this environment

Merged changes propagate without manual copying, over four channels:

| Channel | Mechanism | Already in memory |
|---|---|---|
| **Cloud agents / environments** | Every cloud agent boots from an environment build of `main`; merging a PR makes the next boot carry it. `.cursor/environment.json` install runs `scripts/cloud-agent-install.sh` → `cam-system.py --no-write` so a broken home fails loudly at boot. | yes |
| **Other workspaces** | Persistence bundle: `scripts/persist-export.py` / `persist-import.py` carry `.clinerules`, persona, registry to every registered workspace; `scripts/install-cline-rules.py` syncs policy. | yes |
| **Schedules / standing loops** | `scripts/sync-cline-schedules.py --apply-cache` re-syncs standing automations after merge; loop-engineering `daily-triage` (L1, report-only) catches drift within a day and writes to `STATE.md`. | yes |
| **Model/weight updates** | `scripts/avatar-fetch-models.py` re-resolves pinned HF revisions from the manifest; bumping a revision in `config/system/build-plan.json` auto-populates on next fetch. | planned (phase 4) |

Drift detector: `python3 scripts/build-plan-check.py` runs inside
`cam-system.py --smoke` (piece `piece.build_plan`), so any environment whose
checkout no longer matches the plan reports it at boot.

### 4b. Auto-sync **from** all projects and repos (inbound — a must)

The mirror direction: everything the home registers syncs back **into** it.
Motor: `scripts/auto-sync.py` (piece `piece.auto_sync`, runs at every boot and
on the daily L1 loop). Report-first; `--pull` fast-forwards only and re-pins
submodules; it refuses on a dirty tree and **never auto-merges** — merges stay
Aaron-gated per `.clinerules`.

| Source | Channel |
|---|---|
| Home repo itself | `origin/main` fetch → ahead/behind drift report; `--pull` ff-only under `switch.autonomy` |
| All 22 integration repos (`integrations/*` submodules) | `git submodule status` survey (uninitialized / drifted-from-pin / conflict) + `--pull` re-pin; `needs-attention.py --execute` auto-clears missing inits |
| All 19 coding workspaces | `config/workspaces/registry.json` coverage check + `needs-attention.py --connect` connectivity |
| Session memory from every workspace | `sync-cline-session.py export/import` → `mesh/cline` |
| Local tool memories | `sync-jarvis-memory.py` → `mesh/jarvis` |

Distillate lands in `vault/10-Mesh-Distillates/auto-sync/latest.json` so the
home UI and health scan can show sync state. A registered path that has gone
missing fails the check (exit 1) — that is drift the bus must not hide.

---

## 5. Build phases (technical order, each with a hard exit check)

### Phase 0 — Home foundation (this PR)
Encode the plan: manifest + checker + tests + bus wiring + the auto-sync motor.
**Exit:** `python3 scripts/build-plan-check.py` green · `cam-system.py --smoke` still green · `auto-sync.py` report runs offline · unit tests pass.

### Phase 1 — Real-world execute + receive (priority 1)
1. Stand up the null stack locally (nulltickets → nullclaw → nullboiler → nullhub) — durable synapses across process death (known blocker in `pieces.json`).
2. MemoryBear live API on the turn path (PR #12 lineage) — recall before act, distill after.
3. Flip `MotorExecutor` gated motors from dry-run to live one at a time behind their switches: `motor.inkbox` (outbound send/receive under `switch.outbound`), `motor.speak` (VoiceStudio local), careers/jobs last.
4. Receive loop: inbound channel events (email/SMS via Inkbox, iOS companion) land as sensory events → tickets → mesh.
**Exit:** one full round trip — Aaron asks, Cam executes a real outbound action under its switch, receives the real-world reply, and the reply is in mesh + visible in the home UI.

### Phase 2 — Superman/AGI assist (priority 2, in service of priority 1)
1. Local sLM/DL weights replace heuristic stubs on `motor.slm` / `motor.dl` (`config/enhancement/slm-dl.json`).
2. Daily `team.agi-research-scan` live → scored papers → enhancement proposals (`scripts/agi-research-scan.py`, `scripts/cam-enhance-propose.py`).
3. Higgsfield training goes from dry-run to first real fine-tune job (`switch.cam_enhance` + submodule init), litserve serving hand-off.
4. Capability/info teams run with unlimited subagents under subset privileges.
**Exit:** a measurable priority-1 metric (turn latency, recall hit rate, or task completion) improves because of a priority-2 component, recorded in `STATE.md`.

### Phase 3 — Human ultimate say + ethics inheritance (priority 3, verified continuously)
1. Ethics inheritance manifest: `config/swarm/privileges.json` subset rule extended with an explicit ethics block sourced from `identity/` — every spawned subagent carries it; `aaron_only` never transfers.
2. `requires_human: true` stages enforced in every pipeline that touches outbound / money / jobs / enhance-apply.
3. Kill-switch drill in CI: `scripts/flight-envelope.py` rehearses `switch.kill` and verifies every motor holds.
**Exit:** automated drill proves: any lineage of subagents can be terminated by an ancestor; no gated motor fires with its switch off; enhance-apply blocks without Aaron.

### Phase 4 — Interactivity + living avatar + auto-enhancement (priority 4)
1. Home UI "mission" panels: what's running (live activity feed), what's working (health scan), what needs help (`scripts/needs-attention.py`), and a **suggest-changes queue** Aaron can write into that becomes tickets.
2. Avatar Tier 1 (`hf_realtime`) integration steps 1–5 from section 3.2.
3. Auto-enhancement closed loop: research scan → proposal → Aaron approves via `switch.cam_enhance` → `scripts/apply-cam-enhancements.py` → plasticity records the improvement.
4. Model auto-update channel (`avatar-fetch-models.py` pinned-revision flow).
**Exit:** Aaron opens the home, sees live status, submits a suggestion that becomes a ticket, and holds a spoken conversation with a moving Cam whose speech and facial muscles pass the section 3.1 believability check.

### Phase 5 — Full presence + custom identity (stretch)
Tier 2 studio bring-up on Aaron's GPU machine; Tier 3 Higgsfield fine-tune of the avatar identity.
**Exit:** Aaron chooses a tier per session and the swap is seamless (one contract).

---

## 6. Dependency and risk register

| Risk | Mitigation |
|---|---|
| Null stack not in checkout (blocker #7) | Phase 1 step 1 is first; until then bridge keeps in-process kernel + file mesh (already shipped) |
| Restricted egress blocks HF downloads | `avatar-fetch-models.py` offline mode reports missing weights without failing the bus; weights fetched on Aaron's machines |
| Avatar becomes a second brain | Hard rule inherited from LLMAvatarTalk policy: ASR text → Cam brain → TTS; avatar services never call their own LLM in production |
| GPU-poor hosts | Tier ladder degrades gracefully: Tier 1 → VoiceStudio audio + static portrait → text |
| Ethics drift in deep subagent trees | Subset-only privilege inheritance + lineage terminate (HAAS pattern, `scripts/swarm-check.py`), drilled in Phase 3 |
| Plan drift from reality | `piece.build_plan` check runs in every smoke; missing paths fail the bus |

---

## 7. Verify

```bash
python3 scripts/build-plan-check.py            # plan ↔ repo consistency
python3 scripts/build-plan-check.py --json     # machine-readable report
python3 scripts/auto-sync.py                   # inbound drift from all projects/repos
python3 scripts/swarm-check.py                 # privileges + ethics inheritance drill
python3 scripts/cam-home-live.py               # live app → http://127.0.0.1:8790
python3 scripts/cam-avatar-server.py           # AvatarFrame service → :8791
python3 -m unittest scripts.test_build_plan scripts.test_cam_avatar scripts.test_cam_home_live
python3 scripts/cam-system.py --smoke          # whole organism, includes piece.build_plan + piece.auto_sync + piece.avatar
```
