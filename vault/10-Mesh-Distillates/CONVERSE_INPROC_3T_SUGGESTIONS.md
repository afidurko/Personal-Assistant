# Converse + in-process route — 3T add-on suggestions

Pass 1 (2026-09-20) was green at N=3,000,000,000,000 (0 hard fails).
Issues found were coverage gaps, not connectome/reason property failures.

## Fixes landed before pass 2

1. Wire `ci-static-gate.py` into the 3T campaign (static checks in one process).
2. Scale `aaron-voice-billion-fuzz.py` with `--physical` / modular_period_scaled.
3. cam-reason 3T workers assert `cam_inproc.route` (coding + enhance-hold) and converse overlays (`hi cam` fast, `can you see me` camera line).
4. Campaign units: reason/fast/InfiniteMind + Aaron voice/converse.
5. `workspace-integration-check` is now inside the static gate.

## Landed add-ons

| Add-on | Status |
|---|---|
| `config/persona/converse-overlays.json` | Landed — `speak_from_trace` reads persona config. |
| `scripts/converse-billion-fuzz.py` | Landed — overlay × intent matrix + catalog smoke. |
| In-process public-apis / google-trends search | Landed — `cam_inproc.public_apis_search` / `google_trends_search`. |
| FunASR enroll checksum in voice 3T | Landed — `VoiceStore.enroll_checksum` + reload verify. |
| dual_stream cache invalidation | Landed — mtime reload + `invalidate_dual_stream_cache()`. |

## One voice across hosts (system integration pass)

Before this pass Cam had three reply brains: `scripts/converse_overlays.py`
(Python converse server), a hard-coded `camReply` in `server/core/cam-converse.ts`
(TS home server behind the React stage), and `camReplyLocal` in
`companions/web/app.js` (on-device fallback). Same question, three different
lines. Now `config/persona/converse-overlays.json` (v2) is the only source:

| Surface | Wiring |
|---|---|
| Python converse server | `converse_overlays.explain_reply` → `/api/turn` returns `overlay {kind,id}` + `speak` from config. |
| TS home server | `shared/converseOverlays.ts` (pure mirror) + `OverlaysStore` mtime hot reload in `CamConverse`; `/api/turn` composes the reply *after* the connectome route so slow plans name hotspot + motors. |
| Web companion | `companions/web/converse-overlays.js` (UMD mirror) fetches the config, caches the last good copy in localStorage for offline turns. |
| React home | `useCamVoice` carries `overlay` → bubble tag (`overlay · camera`, `intent · greeting`, `plan · coding`, `repeat`) + MiniBrain label while answering. |
| Endpoints (both hosts) | `GET /api/converse/overlays`, `POST /api/converse/overlays/reload`, `POST /api/converse/preview` (dry reply; no gate / history / log). `/api/health.capabilities.converse_overlays`. |
| Config additions | `intent_rules` (regexes copied from `cam_reason._FAST_PATTERNS`, drift-checked), `intent_order`, `words` whole-word matcher, `speak`, `echo_repeat` (turn-history phrasing), `short_max`, overlays `cortex` / `agents` / `companion_devices`. |
| Parity guard | `scripts/converse-parity-check.py` runs the deterministic corpus through Python, TS (Node `--experimental-strip-types`) and JS and fails on any text/kind/id/intent drift. Wired into `ci-static-gate`, `ci-connectome.sh`, the 3T campaign, `pieces.json` (`piece.converse.check`), MCP `converse_overlays_check`, registry `tool.converse.overlays_check`. |

Edit the JSON, both servers pick it up on the next turn (mtime), companions
on next load. Run `python3 scripts/converse-parity-check.py` after phrase edits.

## Suggested add-ons (next cycle)

| Add-on | Why |
|---|---|
| Per-overlay `area` / `tracts` hints | Let the cortex light the phrase's pathway (e.g. `camera` → `area.visual`), not just the route's. |
| iOS companion Swift mirror | Add a Swift reader for the same JSON + a parity case so the phone never drifts. |
| Live FunASR CAM++ enroll | Checksum covers the store; host enroll still replaces hash_dev. |
| `quotes.quotable` / `exchange.open_er_api` | Allowlisted add-ons when ops asks. |

## Do not

- Put InfiniteMind on the fast gate.
- Fold 1M fuzz into the static gate.
- Free-spend GPU / outbound from Cline.
