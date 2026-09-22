/**
 * Aaron voice gate reject stats + adaptive noise helpers (server).
 */
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import {
  evaluateAaronVoiceGate,
  loadAaronVoiceGatePolicy,
  type AaronVoiceGatePolicy,
  type VoiceGateRequest,
  type VoiceGateResult,
} from './aaron-voice-gate.js';

export interface VoiceRejectEvent {
  at: string;
  source: string;
  score: number;
  threshold: number;
  reason: string;
  multi_speaker_hint?: boolean;
  device_id?: string;
}

export interface VoiceGateStats {
  rejects: number;
  accepts: number;
  last_reject_at: string | null;
  last_reason: string | null;
  adaptive_raised: boolean;
  multi_speaker_streak: number;
}

const DEFAULT_STATS: VoiceGateStats = {
  rejects: 0,
  accepts: 0,
  last_reject_at: null,
  last_reason: null,
  adaptive_raised: false,
  multi_speaker_streak: 0,
};

export class AaronVoiceGateAddons {
  private stats: VoiceGateStats = { ...DEFAULT_STATS };
  private acceptsSinceRaise = 0;
  private cooldownAccepts = 3;

  constructor(private readonly rootDir: string) {}

  async loadPolicy(): Promise<AaronVoiceGatePolicy & { addons?: Record<string, unknown> }> {
    return loadAaronVoiceGatePolicy(this.rootDir) as Promise<
      AaronVoiceGatePolicy & { addons?: Record<string, unknown> }
    >;
  }

  getStats(): VoiceGateStats {
    return { ...this.stats };
  }

  /**
   * Evaluate with optional adaptive threshold bump after multi-speaker streaks.
   * Pass note=false for probe spikes that will be followed by /api/turn.
   */
  async evaluateWithAddons(
    req: VoiceGateRequest,
    opts: { note?: boolean } = {},
  ): Promise<VoiceGateResult & { adaptive?: boolean }> {
    const note = opts.note !== false;
    const policy = await this.loadPolicy();
    const addons = (policy as { addons?: { adaptive_noise?: Record<string, unknown> } }).addons;
    const adaptive = addons?.adaptive_noise;
    const base = evaluateAaronVoiceGate(req, policy);

    if (!adaptive || adaptive.enabled === false) {
      if (note) this.noteResult(base, req);
      return base;
    }

    this.cooldownAccepts = Number(adaptive.cooldown_accepts ?? 3);
    let effective = { ...policy };
    const raised =
      this.stats.adaptive_raised ||
      (this.stats.multi_speaker_streak >= Number(adaptive.streak_to_raise ?? 2) &&
        Boolean(req.multi_speaker_hint));

    if (raised) {
      effective = {
        ...policy,
        noisy_threshold: Number(adaptive.raised_threshold ?? 0.91),
        noisy_environment_mode: true,
      };
    }

    const result = evaluateAaronVoiceGate(req, effective);
    if (note) this.noteResult(result, req, raised);
    return { ...result, adaptive: raised };
  }

  private noteResult(result: VoiceGateResult, req: VoiceGateRequest, adaptive = false): void {
    if (result.accept) {
      this.stats.accepts += 1;
      this.acceptsSinceRaise += 1;
      if (this.stats.adaptive_raised && this.acceptsSinceRaise >= this.cooldownAccepts) {
        this.stats.adaptive_raised = false;
        this.stats.multi_speaker_streak = 0;
        this.acceptsSinceRaise = 0;
      }
      if (!req.multi_speaker_hint) this.stats.multi_speaker_streak = 0;
      return;
    }
    this.stats.rejects += 1;
    this.stats.last_reject_at = new Date().toISOString();
    this.stats.last_reason = result.reason;
    this.acceptsSinceRaise = 0;
    if (req.multi_speaker_hint || result.reason === 'rejected_surrounding_speech') {
      this.stats.multi_speaker_streak += 1;
    }
    if (adaptive || this.stats.multi_speaker_streak >= 2) {
      this.stats.adaptive_raised = true;
    }
  }

  async recordReject(event: VoiceRejectEvent): Promise<void> {
    const dir = path.join(this.rootDir, 'data', 'runtime');
    await mkdir(dir, { recursive: true });
    const file = path.join(dir, 'aaron-voice-rejects.jsonl');
    await appendFile(file, JSON.stringify(event) + '\n', 'utf8');
    const statsPath = path.join(dir, 'aaron-voice-stats.json');
    await writeFile(statsPath, JSON.stringify(this.getStats(), null, 2) + '\n', 'utf8');
  }

  async saveProfile(profile: unknown): Promise<string> {
    const out = path.join(this.rootDir, 'identity', 'aaron', 'local', 'voice-profile.json');
    await mkdir(path.dirname(out), { recursive: true });
    const doc = {
      subject: 'Aaron',
      saved_at: new Date().toISOString(),
      source: 'cam_voice_gate_addon',
      profile,
    };
    await writeFile(out, JSON.stringify(doc, null, 2) + '\n', 'utf8');
    return out;
  }

  async loadSavedProfile(): Promise<unknown | null> {
    try {
      const raw = await readFile(
        path.join(this.rootDir, 'identity', 'aaron', 'local', 'voice-profile.json'),
        'utf8',
      );
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }
}
