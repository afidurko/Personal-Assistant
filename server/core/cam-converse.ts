/**
 * Cam converse — soft airy replies + session log for the home presence.
 * Browser supplies mic/ASR; this module handles turn logic and distill logs.
 */
import { appendFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

export interface ConverseTurn {
  role: 'aaron' | 'cam';
  text: string;
  source?: string;
  at: string;
}

export interface ConverseReply {
  cam: string;
  speak: { rate: number; pitch: number; lang: string };
  sessionId: string;
  history: ConverseTurn[];
}

const SPEAK = { rate: 0.95, pitch: 1.05, lang: 'en-US' } as const;

export class CamConverse {
  readonly sessionId = randomUUID();
  readonly started = new Date().toISOString();
  private history: ConverseTurn[] = [];

  constructor(private readonly rootDir: string) {}

  getHistory(): ConverseTurn[] {
    return this.history.map((h) => ({ ...h }));
  }

  async turn(text: string, source = 'text'): Promise<ConverseReply> {
    const aaronText = (text || '').trim();
    const at = new Date().toISOString();
    if (aaronText) {
      this.history.push({ role: 'aaron', text: aaronText, source, at });
    }
    const cam = camReply(aaronText);
    this.history.push({ role: 'cam', text: cam, source: 'reply', at: new Date().toISOString() });
    // Keep a rolling window so spawn/memory stays light
    if (this.history.length > 80) this.history = this.history.slice(-80);
    await this.logTurn(aaronText, cam, source);
    return {
      cam,
      speak: { ...SPEAK },
      sessionId: this.sessionId,
      history: this.getHistory(),
    };
  }

  private async logTurn(aaron: string, cam: string, source: string): Promise<void> {
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
    return "Yes — I'm listening to the room. Keep talking; I'll answer when you pause.";
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
