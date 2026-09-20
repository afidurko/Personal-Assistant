/**
 * NVIDIA Audio2Face-3D / ACE ARKit blendshape contract.
 * Names match A2F-3D AnimationDataStream (docs.nvidia.com/ace/audio2face-3d).
 * Desk studio: integrations/llmavatartalk → PushAudio gRPC → Omniverse A2F.
 * Browser: same weight vector applied to Cam’s photo-fitted mesh.
 */

export const A2F_BLENDSHAPES = [
  'EyeBlinkLeft',
  'EyeLookDownLeft',
  'EyeLookInLeft',
  'EyeLookOutLeft',
  'EyeLookUpLeft',
  'EyeSquintLeft',
  'EyeWideLeft',
  'EyeBlinkRight',
  'EyeLookDownRight',
  'EyeLookInRight',
  'EyeLookOutRight',
  'EyeLookUpRight',
  'EyeSquintRight',
  'EyeWideRight',
  'JawForward',
  'JawLeft',
  'JawRight',
  'JawOpen',
  'MouthClose',
  'MouthFunnel',
  'MouthPucker',
  'MouthLeft',
  'MouthRight',
  'MouthSmileLeft',
  'MouthSmileRight',
  'MouthFrownLeft',
  'MouthFrownRight',
  'MouthDimpleLeft',
  'MouthDimpleRight',
  'MouthStretchLeft',
  'MouthStretchRight',
  'MouthRollLower',
  'MouthRollUpper',
  'MouthShrugLower',
  'MouthShrugUpper',
  'MouthPressLeft',
  'MouthPressRight',
  'MouthLowerDownLeft',
  'MouthLowerDownRight',
  'MouthUpperUpLeft',
  'MouthUpperUpRight',
  'BrowDownLeft',
  'BrowDownRight',
  'BrowInnerUp',
  'BrowOuterUpLeft',
  'BrowOuterUpRight',
  'CheekPuff',
  'CheekSquintLeft',
  'CheekSquintRight',
  'NoseSneerLeft',
  'NoseSneerRight',
  'TongueOut',
  'HeadRoll',
  'HeadPitch',
  'HeadYaw',
] as const;

export type A2FShape = (typeof A2F_BLENDSHAPES)[number];
export type A2FWeights = Partial<Record<A2FShape, number>>;

/** Oculus/A2F viseme ids → ARKit mix (same mapping A2F solved_arkit uses). */
export const VISEME_TO_A2F: Record<string, A2FWeights> = {
  sil: {},
  PP: { MouthClose: 0.85, MouthPressLeft: 0.45, MouthPressRight: 0.45, JawOpen: 0.02 },
  FF: { JawOpen: 0.12, MouthLowerDownLeft: 0.35, MouthLowerDownRight: 0.35, MouthUpperUpLeft: 0.2, MouthUpperUpRight: 0.2 },
  TH: { JawOpen: 0.16, MouthStretchLeft: 0.12, MouthStretchRight: 0.12 },
  DD: { JawOpen: 0.16, MouthClose: 0.1 },
  kk: { JawOpen: 0.22 },
  CH: { JawOpen: 0.2, MouthFunnel: 0.45, MouthPucker: 0.15 },
  SS: { JawOpen: 0.1, MouthSmileLeft: 0.18, MouthSmileRight: 0.18, MouthStretchLeft: 0.12, MouthStretchRight: 0.12 },
  nn: { JawOpen: 0.08, MouthClose: 0.25 },
  RR: { JawOpen: 0.16, MouthFunnel: 0.3 },
  aa: { JawOpen: 0.48, MouthLowerDownLeft: 0.18, MouthLowerDownRight: 0.18 },
  E: { JawOpen: 0.32, MouthSmileLeft: 0.38, MouthSmileRight: 0.38, MouthStretchLeft: 0.2, MouthStretchRight: 0.2 },
  I: { JawOpen: 0.2, MouthSmileLeft: 0.42, MouthSmileRight: 0.42 },
  O: { JawOpen: 0.42, MouthFunnel: 0.55, MouthPucker: 0.2 },
  U: { JawOpen: 0.22, MouthPucker: 0.7, MouthFunnel: 0.35 },
};

export const CHAR_TO_VISEME: Record<string, string> = {
  a: 'aa',
  e: 'E',
  i: 'I',
  o: 'O',
  u: 'U',
  y: 'I',
  b: 'PP',
  m: 'PP',
  p: 'PP',
  f: 'FF',
  v: 'FF',
  w: 'U',
  q: 'U',
  r: 'RR',
  s: 'SS',
  z: 'SS',
  t: 'DD',
  d: 'DD',
  n: 'nn',
  l: 'DD',
  c: 'kk',
  k: 'kk',
  g: 'kk',
  h: 'aa',
  j: 'CH',
  x: 'SS',
};

export function emptyWeights(): A2FWeights {
  const w: A2FWeights = {};
  for (const k of A2F_BLENDSHAPES) w[k] = 0;
  return w;
}

export function mixWeights(base: A2FWeights, add: A2FWeights, amount = 1): A2FWeights {
  const out: A2FWeights = { ...base };
  for (const [k, v] of Object.entries(add)) {
    const key = k as A2FShape;
    out[key] = Math.min(1.2, (out[key] ?? 0) + (v ?? 0) * amount);
  }
  return out;
}

export function lerpWeights(a: A2FWeights, b: A2FWeights, t: number): A2FWeights {
  const out = emptyWeights();
  for (const k of A2F_BLENDSHAPES) {
    const av = a[k] ?? 0;
    const bv = b[k] ?? 0;
    out[k] = av + (bv - av) * t;
  }
  return out;
}
