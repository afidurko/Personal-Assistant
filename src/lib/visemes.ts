/**
 * Lightweight viseme schedule from spoken text — drives Cam’s mouth shapes.
 * Not phonetic ASR; good enough for speech-synced facial motion in the browser.
 */

export type VisemeId = 'rest' | 'closed' | 'smile' | 'wide' | 'open' | 'round' | 'narrow' | 'teeth';

export interface VisemeFrame {
  at: number; // 0..1 progress through utterance
  id: VisemeId;
  open: number; // 0..1 jaw
}

const CHAR_VISEME: Record<string, VisemeId> = {
  a: 'open',
  e: 'wide',
  i: 'wide',
  o: 'round',
  u: 'round',
  y: 'wide',
  b: 'closed',
  m: 'closed',
  p: 'closed',
  f: 'teeth',
  v: 'teeth',
  w: 'narrow',
  q: 'narrow',
  r: 'narrow',
  s: 'teeth',
  z: 'teeth',
  t: 'teeth',
  d: 'teeth',
  n: 'closed',
  l: 'wide',
  c: 'teeth',
  k: 'open',
  g: 'open',
  h: 'open',
  j: 'wide',
  x: 'teeth',
};

/** Build a timeline of visemes from text. */
export function buildVisemeSchedule(text: string): VisemeFrame[] {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (!cleaned) return [{ at: 0, id: 'rest', open: 0 }];

  const frames: VisemeFrame[] = [{ at: 0, id: 'smile', open: 0.08 }];
  const letters = cleaned.toLowerCase().split('');
  const n = Math.max(1, letters.length);

  for (let i = 0; i < letters.length; i++) {
    const ch = letters[i]!;
    if (ch === ' ' || ch === ',' || ch === '.' || ch === '!' || ch === '?' || ch === ';' || ch === ':') {
      frames.push({ at: (i + 1) / n, id: 'rest', open: 0.02 });
      continue;
    }
    if (!/[a-z]/.test(ch)) continue;
    const id = CHAR_VISEME[ch] || 'open';
    const open =
      id === 'closed' || id === 'rest'
        ? 0.02
        : id === 'teeth'
          ? 0.18
          : id === 'narrow'
            ? 0.22
            : id === 'wide'
              ? 0.35
              : id === 'round'
                ? 0.42
                : id === 'open'
                  ? 0.55
                  : 0.2;
    frames.push({ at: (i + 0.5) / n, id, open });
  }
  frames.push({ at: 1, id: 'smile', open: 0.1 });
  return frames;
}

export function sampleViseme(frames: VisemeFrame[], progress: number): VisemeFrame {
  if (!frames.length) return { at: 0, id: 'rest', open: 0 };
  const p = Math.min(1, Math.max(0, progress));
  let prev = frames[0]!;
  for (let i = 1; i < frames.length; i++) {
    const f = frames[i]!;
    if (p <= f.at) {
      const span = Math.max(1e-6, f.at - prev.at);
      const t = (p - prev.at) / span;
      return {
        at: p,
        id: t < 0.5 ? prev.id : f.id,
        open: prev.open + (f.open - prev.open) * t,
      };
    }
    prev = f;
  }
  return frames[frames.length - 1]!;
}

/** Estimate utterance duration in ms from text + speech rate. */
export function estimateSpeechMs(text: string, rate = 0.95): number {
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  const base = Math.max(900, words * 380 + text.length * 18);
  return base / Math.max(0.6, rate);
}

export type FaceExpression =
  | 'idle'
  | 'listen'
  | 'think'
  | 'type'
  | 'speak'
  | 'smile'
  | 'concern'
  | 'ignored';

export function expressionFromStatus(
  status: string,
  typing: boolean,
): FaceExpression {
  if (typing) return 'type';
  switch (status) {
    case 'listening':
    case 'enrolling':
    case 'requesting':
      return 'listen';
    case 'thinking':
      return 'think';
    case 'speaking':
      return 'speak';
    case 'ignored':
      return 'ignored';
    case 'error':
      return 'concern';
    default:
      return 'idle';
  }
}
