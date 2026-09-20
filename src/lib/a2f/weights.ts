import {
  CHAR_TO_VISEME,
  VISEME_TO_A2F,
  emptyWeights,
  lerpWeights,
  mixWeights,
  type A2FWeights,
} from './arkit';
import type { FaceExpression } from '@/lib/visemes';

export interface A2FKey {
  at: number;
  weights: A2FWeights;
}

export function expressionWeights(expr: FaceExpression, t = 0): A2FWeights {
  const w = emptyWeights();
  const blink = Math.max(0, Math.sin(t * 0.8) * 0.015);
  w.EyeBlinkLeft = blink;
  w.EyeBlinkRight = blink;
  switch (expr) {
    case 'listen':
      w.BrowInnerUp = 0.18;
      w.MouthSmileLeft = 0.12;
      w.MouthSmileRight = 0.12;
      w.HeadPitch = 0.04 * Math.sin(t * 0.7);
      break;
    case 'think':
    case 'type':
      w.BrowInnerUp = 0.28;
      w.BrowDownLeft = 0.08;
      w.EyeSquintLeft = 0.08;
      w.EyeSquintRight = 0.06;
      w.MouthClose = 0.1;
      w.HeadYaw = 0.05 * Math.sin(t * 0.45);
      break;
    case 'speak':
      w.MouthSmileLeft = 0.1;
      w.MouthSmileRight = 0.1;
      w.BrowOuterUpLeft = 0.08;
      w.BrowOuterUpRight = 0.08;
      break;
    case 'concern':
    case 'ignored':
      w.BrowDownLeft = 0.35;
      w.BrowDownRight = 0.35;
      w.MouthFrownLeft = 0.28;
      w.MouthFrownRight = 0.28;
      break;
    default:
      w.MouthSmileLeft = 0.08;
      w.MouthSmileRight = 0.08;
      w.HeadYaw = 0.03 * Math.sin(t * 0.35);
      w.HeadPitch = 0.02 * Math.sin(t * 0.28);
  }
  return w;
}

export function buildA2FSchedule(text: string): A2FKey[] {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  if (!cleaned) return [{ at: 0, weights: emptyWeights() }];
  const keys: A2FKey[] = [{ at: 0, weights: mixWeights(emptyWeights(), VISEME_TO_A2F.sil) }];
  const letters = cleaned.toLowerCase().split('');
  const n = Math.max(1, letters.length);
  for (let i = 0; i < letters.length; i++) {
    const ch = letters[i]!;
    const at = (i + 0.5) / n;
    if (' .,!?;:'.includes(ch)) {
      keys.push({ at, weights: emptyWeights() });
      continue;
    }
    if (!/[a-z]/.test(ch)) continue;
    const vis = CHAR_TO_VISEME[ch] || 'aa';
    keys.push({ at, weights: { ...VISEME_TO_A2F[vis] } });
  }
  keys.push({ at: 1, weights: mixWeights(emptyWeights(), { MouthSmileLeft: 0.1, MouthSmileRight: 0.1 }) });
  return keys;
}

export function sampleA2F(keys: A2FKey[], progress: number): A2FWeights {
  if (!keys.length) return emptyWeights();
  const p = Math.min(1, Math.max(0, progress));
  let prev = keys[0]!;
  for (let i = 1; i < keys.length; i++) {
    const k = keys[i]!;
    if (p <= k.at) {
      const span = Math.max(1e-6, k.at - prev.at);
      return lerpWeights(prev.weights, k.weights, (p - prev.at) / span);
    }
    prev = k;
  }
  return keys[keys.length - 1]!.weights;
}

export function composeA2F(opts: {
  expr: FaceExpression;
  speaking: boolean;
  progress: number;
  schedule: A2FKey[];
  timeSec: number;
}): A2FWeights {
  const base = expressionWeights(opts.expr, opts.timeSec);
  if (!opts.speaking || opts.progress < 0) {
    // Occasional blink while idle
    const cycle = opts.timeSec % 4.2;
    if (cycle > 4.0) {
      const b = Math.sin(((cycle - 4.0) / 0.2) * Math.PI);
      base.EyeBlinkLeft = b;
      base.EyeBlinkRight = b;
    }
    return base;
  }
  const speech = sampleA2F(opts.schedule, opts.progress);
  return mixWeights(base, speech, 1);
}
