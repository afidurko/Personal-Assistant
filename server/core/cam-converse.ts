/**
 * Cam converse — soft airy replies + session log for the home presence.
 * Browser supplies mic/ASR; this module handles turn logic and distill logs.
 * Mic turns are Aaron-only gated (noisy-room filter) via aaron-voice-gate add-ons.
 *
 * Reply phrases come from config/persona/converse-overlays.json — the same file
 * the Python converse server and the web companion read — so every Cam host
 * answers with one voice. Edit the config, not this module.
 */
import { appendFile, mkdir } from 'node:fs/promises';
import { readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import type { VoiceGateResult } from './aaron-voice-gate.js';
import {
  AaronVoiceGateAddons,
  type VoiceGateStats,
} from './aaron-voice-gate-addons.js';
import {
  FALLBACK_OVERLAYS,
  checkOverlays,
  classifyIntents,
  explainReply,
  intentOrder,
  speakParams,
  type ConverseOverlaysConfig,
  type HistoryRow,
  type OverlayCheck,
  type ReplyExplanation,
  type ReplyKind,
  type ReplyTrace,
  type SpeakParams,
} from '../../shared/converseOverlays.js';

export const OVERLAYS_CONFIG_REL = 'config/persona/converse-overlays.json';

export interface ConverseTurn {
  role: 'aaron' | 'cam' | 'system';
  text: string;
  source?: string;
  at: string;
  gate?: VoiceGateResult & { adaptive?: boolean };
  overlay?: ReplyMeta;
}

export interface ReplyMeta {
  kind: ReplyKind;
  id: string | null;
  intents?: string[];
}

export interface ConverseReply {
  cam: string;
  speak: SpeakParams;
  sessionId: string;
  history: ConverseTurn[];
  rejected?: boolean;
  gate?: VoiceGateResult & { adaptive?: boolean };
  voice_stats?: VoiceGateStats;
  overlay?: ReplyMeta;
}

export interface ConverseTurnInput {
  text: string;
  source?: string;
  aaron_voice_score?: number | null;
  enrolled?: boolean;
  multi_speaker_hint?: boolean;
  device_id?: string;
}

/** Route facts the bridge can hand to the reply composer (slow-path plans). */
export interface ReplyContext {
  path?: 'fast' | 'slow';
  hotspot_id?: string | null;
  motor_plan?: string[] | null;
  intents?: string[];
}

export interface TurnOptions {
  /** Runs after the gate accepts and before the reply is composed. */
  beforeReply?: (aaronText: string) => Promise<ReplyContext | undefined | void>;
}

export interface OverlaysStatus {
  ok: boolean;
  config: string;
  version?: number;
  mtime: number | null;
  overlay_ids: string[];
  intent_order: string[];
  speak: SpeakParams;
  check: OverlayCheck;
  host: 'ts';
  fallback: boolean;
}

/** mtime-cached loader; safe to call per turn. */
export class OverlaysStore {
  private cache: ConverseOverlaysConfig | null = null;
  private mtime: number | null = null;
  private usingFallback = false;

  constructor(private readonly rootDir: string) {}

  get file(): string {
    return path.join(this.rootDir, OVERLAYS_CONFIG_REL);
  }

  invalidate(): void {
    this.cache = null;
    this.mtime = null;
  }

  load(): ConverseOverlaysConfig {
    let mtime: number | null = null;
    try {
      mtime = statSync(this.file).mtimeMs;
    } catch {
      mtime = null;
    }
    if (this.cache && mtime === this.mtime) return this.cache;
    try {
      this.cache = JSON.parse(readFileSync(this.file, 'utf8')) as ConverseOverlaysConfig;
      this.usingFallback = false;
    } catch {
      this.cache = FALLBACK_OVERLAYS;
      this.usingFallback = true;
    }
    this.mtime = mtime;
    return this.cache;
  }

  status(): OverlaysStatus {
    const cfg = this.load();
    const check = checkOverlays(cfg);
    return {
      ok: check.ok && !this.usingFallback,
      config: OVERLAYS_CONFIG_REL,
      version: cfg.version,
      mtime: this.mtime,
      overlay_ids: (cfg.overlays ?? []).map((r) => String(r.id)),
      intent_order: intentOrder(cfg),
      speak: speakParams(cfg),
      check,
      host: 'ts',
      fallback: this.usingFallback,
    };
  }
}

export class CamConverse {
  readonly sessionId = randomUUID();
  readonly started = new Date().toISOString();
  private history: ConverseTurn[] = [];
  readonly voiceAddons: AaronVoiceGateAddons;
  readonly overlays: OverlaysStore;

  constructor(private readonly rootDir: string) {
    this.voiceAddons = new AaronVoiceGateAddons(rootDir);
    this.overlays = new OverlaysStore(rootDir);
  }

  getHistory(): ConverseTurn[] {
    return this.history.map((h) => ({ ...h }));
  }

  getVoiceStats(): VoiceGateStats {
    return this.voiceAddons.getStats();
  }

  speak(): SpeakParams {
    return speakParams(this.overlays.load());
  }

  /** Dry reply — no gate, no history mutation, no log. For phrase editing. */
  preview(text: string, ctx: ReplyContext = {}): ComposedReply {
    return composeReply(text, ctx, null, this.overlays.load());
  }

  async turn(
    input: string | ConverseTurnInput,
    source = 'text',
    opts: TurnOptions = {},
  ): Promise<ConverseReply> {
    const req: ConverseTurnInput =
      typeof input === 'string' ? { text: input, source } : { source: 'text', ...input };
    const aaronText = (req.text || '').trim();
    const src = req.source || source || 'text';
    const gate = await this.voiceAddons.evaluateWithAddons({
      source: src,
      aaron_voice_score: req.aaron_voice_score,
      enrolled: req.enrolled,
      multi_speaker_hint: req.multi_speaker_hint,
    });

    if (!gate.accept) {
      const cam =
        gate.reason === 'enrollment_required'
          ? 'I only take Aaron’s voice on the mic. Enroll your voice once in a quiet moment, then try again.'
          : gate.reason === 'rejected_surrounding_speech'
            ? 'I heard other voices nearby and ignored them. Speak again when it’s you, Aaron.'
            : `I didn’t match that as your voice (score ${Math.round(gate.score * 100)}%). Surrounding speech stays filtered out.`;
      const at = new Date().toISOString();
      this.history.push({ role: 'system', text: cam, source: src, at, gate });
      if (this.history.length > 80) this.history = this.history.slice(-80);
      await this.voiceAddons.recordReject({
        at,
        source: src,
        score: gate.score,
        threshold: gate.threshold,
        reason: gate.reason,
        multi_speaker_hint: req.multi_speaker_hint,
        device_id: req.device_id,
      });
      await this.logTurn(aaronText, cam, src, gate);
      return {
        cam,
        speak: this.speak(),
        sessionId: this.sessionId,
        history: this.getHistory(),
        rejected: true,
        gate,
        voice_stats: this.getVoiceStats(),
      };
    }

    const ctx = (opts.beforeReply ? await opts.beforeReply(aaronText) : undefined) ?? {};
    const cfg = this.overlays.load();
    // History still ends at the previous turn here — repeat detection needs that.
    const { text: cam, kind, id, intents } = composeReply(aaronText, ctx, this.history, cfg);
    const meta: ReplyMeta = { kind, id, intents };

    const at = new Date().toISOString();
    if (aaronText) {
      this.history.push({ role: 'aaron', text: aaronText, source: src, at, gate });
    }
    this.history.push({ role: 'cam', text: cam, source: 'reply', at, overlay: meta });
    // Keep a rolling window so spawn/memory stays light
    if (this.history.length > 80) this.history = this.history.slice(-80);
    await this.logTurn(aaronText, cam, src, gate, meta);
    return {
      cam,
      speak: speakParams(cfg),
      sessionId: this.sessionId,
      history: this.getHistory(),
      gate,
      voice_stats: this.getVoiceStats(),
      overlay: meta,
    };
  }

  private async logTurn(
    aaron: string,
    cam: string,
    source: string,
    gate?: VoiceGateResult,
    overlay?: ReplyMeta,
  ): Promise<void> {
    try {
      const dir = path.join(this.rootDir, 'vault/10-Mesh-Distillates/converse');
      await mkdir(dir, { recursive: true });
      const day = new Date().toISOString().slice(0, 10);
      const line =
        JSON.stringify({
          ts: new Date().toISOString(),
          sessionId: this.sessionId,
          source,
          aaron,
          cam,
          gate,
          overlay,
        }) + '\n';
      await appendFile(path.join(dir, `${day}.jsonl`), line, 'utf8');
    } catch {
      /* distill is best-effort */
    }
  }
}

export type ComposedReply = ReplyExplanation & { intents: string[] };

/** One place that turns (text, route context, history, config) into a line. */
export function composeReply(
  aaronText: string,
  ctx: ReplyContext,
  history: HistoryRow[] | null,
  cfg: ConverseOverlaysConfig,
): ComposedReply {
  const intents = ctx.intents?.length ? ctx.intents : classifyIntents(aaronText, cfg);
  const trace: ReplyTrace = {
    intents,
    path: ctx.path ?? 'fast',
    hotspot_id: ctx.hotspot_id ?? null,
    motor_plan: ctx.motor_plan ?? null,
  };
  return { ...explainReply(aaronText, trace, history, cfg), intents };
}

let standaloneStore: OverlaysStore | null = null;

/**
 * Stateless reply from the shared config (no gate, no history). Reads the
 * config relative to cwd; pass `cfg` to pin one explicitly.
 */
export function camReply(
  aaronText: string,
  cfg?: ConverseOverlaysConfig,
  ctx: ReplyContext = {},
): string {
  const config = cfg ?? (standaloneStore ??= new OverlaysStore(process.cwd())).load();
  return composeReply(aaronText, ctx, null, config).text;
}
