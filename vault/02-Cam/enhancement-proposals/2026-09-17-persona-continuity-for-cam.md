# Enhancement proposal — Persona continuity metrics for Cam

**Status:** propose_only (awaiting Aaron / `switch.cam_enhance`)  
**Date:** 2026-09-17  
**Source:** [Consistently Simulating Human Personas…](https://arxiv.org/html/2511.00222v1) · [ARPM temporal memory governance](https://arxiv.org/html/2605.14802v1)  
**Priority:** P2 — keeps Cam sounding like Cam across days  
**Relevance:** presence · chief voice · soft airy English · Aaron-only

## Suggested Cam touchpoints

- `config/persona/voice.json`, `identity/PROFILE.md`
- `center.chief`, `motor.speak`
- `mesh/persona`
- live converse / LLMAvatarTalk

## Why it might enhance Cam

Persona papers show LLMs **drift** — contradict earlier traits, abandon tone, or become generically cheerful. Multi-turn consistency metrics (prompt-to-line, line-to-line, Q&A) cut inconsistency >55% when used as rewards. ARPM treats long-term persona as **external temporal memory governance** (retrieval + dual time coordinates + auditable evidence), not weights.

Cam’s brand is locked (32, Argentine, soft airy fluent English, Aaron-only). Drift is a functional failure, not cosmetics.

## Proposed Cam mapping (config-first)

1. Add a small persona questionnaire checklist to QA after long sessions.  
2. Prefer ARPM-style: vault/mesh persona facts with timestamps; bind citations in replies.  
3. Do **not** fine-tune in-repo first — evaluation + prompt/governance only.

## Apply gate

1. QA cite-check  
2. Aaron approve  
3. Add `config/persona/consistency-checks.md` + qa role bullets  
4. Smoke on Cam converse transcripts when available
