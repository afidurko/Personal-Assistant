/**
 * Cam converse — soft airy replies + session log for the home presence.
 * Browser supplies mic/ASR; this module handles turn logic and distill logs.
 * Mic turns are Aaron-only gated (noisy-room filter) via aaron-voice-gate add-ons.
 */
import { appendFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import type { VoiceGateResult } from './aaron-voice-gate.js';
import {
  AaronVoiceGateAddons,
  type VoiceGateStats,
} from './aaron-voice-gate-addons.js';

export interface ConverseTurn {
  role: 'aaron' | 'cam' | 'system';
  text: string;
  source?: string;
  at: string;
  gate?: VoiceGateResult & { adaptive?: boolean };
}

export interface ConverseReply {
  cam: string;
  speak: { rate: number; pitch: number; lang: string };
  sessionId: string;
  history: ConverseTurn[];
  rejected?: boolean;
  gate?: VoiceGateResult & { adaptive?: boolean };
  voice_stats?: VoiceGateStats;
}

export interface ConverseTurnInput {
  text: string;
  source?: string;
  aaron_voice_score?: number | null;
  enrolled?: boolean;
  multi_speaker_hint?: boolean;
  device_id?: string;
}

const SPEAK = { rate: 0.95, pitch: 1.05, lang: 'en-US' } as const;

export class CamConverse {
  readonly sessionId = randomUUID();
  readonly started = new Date().toISOString();
  private history: ConverseTurn[] = [];
  readonly voiceAddons: AaronVoiceGateAddons;

  constructor(private readonly rootDir: string) {
    this.voiceAddons = new AaronVoiceGateAddons(rootDir);
  }

  getHistory(): ConverseTurn[] {
    return this.history.map((h) => ({ ...h }));
  }

  getVoiceStats(): VoiceGateStats {
    return this.voiceAddons.getStats();
  }

  async turn(input: string | ConverseTurnInput, source = 'text'): Promise<ConverseReply> {
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
        speak: { ...SPEAK },
        sessionId: this.sessionId,
        history: this.getHistory(),
        rejected: true,
        gate,
        voice_stats: this.getVoiceStats(),
      };
    }

    const at = new Date().toISOString();
    if (aaronText) {
      this.history.push({ role: 'aaron', text: aaronText, source: src, at, gate });
    }
    const cam = camReply(aaronText);
    this.history.push({ role: 'cam', text: cam, source: 'reply', at: new Date().toISOString() });
    // Keep a rolling window so spawn/memory stays light
    if (this.history.length > 80) this.history = this.history.slice(-80);
    await this.logTurn(aaronText, cam, src, gate);
    return {
      cam,
      speak: { ...SPEAK },
      sessionId: this.sessionId,
      history: this.getHistory(),
      gate,
      voice_stats: this.getVoiceStats(),
    };
  }

  private async logTurn(
    aaron: string,
    cam: string,
    source: string,
    gate?: VoiceGateResult,
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
        }) + '\n';
      await appendFile(path.join(dir, `${day}.jsonl`), line, 'utf8');
    } catch {
      /* distill is best-effort */
    }
  }
}

export function camReply(aaronText: string): string {
  const t = (aaronText || '').trim();
  const low = t.toLowerCase();
  if (!t) return "I'm here, Aaron. Whenever you're ready — I'm listening.";
  if (/hello|hi cam|hey cam|^hi\b|^hey\b/.test(low)) {
    return "Hi Aaron. Soft and clear — mic path is live. Say what you need and I'll take it.";
  }
  if (/mic|microphone|hear me|listening|working/.test(low)) {
    return "Yes — I'm listening for your voice only. Surrounding conversation gets filtered out once you're enrolled.";
  }
  if (/only my voice|my voice only|ignore.*(other|people|room|noise|surround)/.test(low)) {
    return "Got it — Aaron-only mode is on. Enroll once if you haven't, then I'll ignore other speakers in noisy places.";
  }
  if (/brain|cortex|3d|mesh/.test(low)) {
    return "The 3D cortex is live behind me — fibers light as my agents and tasks fire. Spin it; tap tracts to explore.";
  }
  if (/agent|spawn|task|improve/.test(low)) {
    return "I'm already spawning background improve tasks for myself and the mesh. Check the spawn bay — there's room for all of us.";
  }
  if (/camera|face|see me/.test(low)) {
    return "Camera can join from the companion too. I already know your face from enrollment.";
  }
  if (/who are you|your name/.test(low)) {
    return "I'm Cam — thirty-two, from Argentina, soft airy English. You're Aaron, my only task-giver.";
  }
  if (/thank/.test(low)) return "Of course. I'm right here.";
  const short = t.length < 120 ? t : `${t.slice(0, 117)}…`;
  return `I heard you: “${short}”. Tell me the next step and I'll take it from there.`;
}
