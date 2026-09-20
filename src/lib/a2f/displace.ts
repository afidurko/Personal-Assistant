import type { A2FWeights } from './arkit';
import {
  BROW_INNER,
  CHIN,
  JAW,
  LEFT_BROW,
  LEFT_EYE_LID_LOWER,
  LEFT_EYE_LID_UPPER,
  LIPS_LOWER_INNER,
  LIPS_LOWER_OUTER,
  LIPS_UPPER_INNER,
  LIPS_UPPER_OUTER,
  RIGHT_BROW,
  RIGHT_EYE_LID_LOWER,
  RIGHT_EYE_LID_UPPER,
} from './landmarks';

function add(out: Float32Array, i: number, x: number, y: number, z = 0) {
  const o = i * 3;
  out[o] = (out[o] ?? 0) + x;
  out[o + 1] = (out[o + 1] ?? 0) + y;
  out[o + 2] = (out[o + 2] ?? 0) + z;
}

function addMany(out: Float32Array, ids: number[], x: number, y: number, z = 0, falloff = 1) {
  for (const i of ids) add(out, i, x * falloff, y * falloff, z * falloff);
}

/**
 * Apply NVIDIA A2F ARKit weights onto a rest-pose MediaPipe mesh (Cam’s face).
 * Units are Three.js face space (~[-0.5, 0.5]).
 */
export function applyA2FDisplacements(
  rest: Float32Array,
  weights: A2FWeights,
  target: Float32Array,
): void {
  target.set(rest);
  const n = rest.length / 3;
  const scratch = new Float32Array(rest.length);

  const jaw = weights.JawOpen ?? 0;
  const smileL = weights.MouthSmileLeft ?? 0;
  const smileR = weights.MouthSmileRight ?? 0;
  const frownL = weights.MouthFrownLeft ?? 0;
  const frownR = weights.MouthFrownRight ?? 0;
  const funnel = weights.MouthFunnel ?? 0;
  const pucker = weights.MouthPucker ?? 0;
  const close = weights.MouthClose ?? 0;
  const stretchL = weights.MouthStretchLeft ?? 0;
  const stretchR = weights.MouthStretchRight ?? 0;
  const lowL = weights.MouthLowerDownLeft ?? 0;
  const lowR = weights.MouthLowerDownRight ?? 0;
  const upL = weights.MouthUpperUpLeft ?? 0;
  const upR = weights.MouthUpperUpRight ?? 0;
  const pressL = weights.MouthPressLeft ?? 0;
  const pressR = weights.MouthPressRight ?? 0;
  const blinkL = weights.EyeBlinkLeft ?? 0;
  const blinkR = weights.EyeBlinkRight ?? 0;
  const browIn = weights.BrowInnerUp ?? 0;
  const browDownL = weights.BrowDownLeft ?? 0;
  const browDownR = weights.BrowDownRight ?? 0;
  const browOutL = weights.BrowOuterUpLeft ?? 0;
  const browOutR = weights.BrowOuterUpRight ?? 0;
  const tongue = weights.TongueOut ?? 0;

  // Jaw — rotate/translate lower face (Audio2Face JawOpen)
  if (jaw > 0.001) {
    addMany(scratch, LIPS_LOWER_INNER, 0, -0.085 * jaw, 0.01 * jaw);
    addMany(scratch, LIPS_LOWER_OUTER, 0, -0.07 * jaw, 0.008 * jaw);
    addMany(scratch, CHIN, 0, -0.095 * jaw, 0.012 * jaw);
    addMany(scratch, JAW, 0, -0.055 * jaw, 0.006 * jaw);
    addMany(scratch, LIPS_UPPER_INNER, 0, 0.012 * jaw, 0);
    addMany(scratch, LIPS_UPPER_OUTER, 0, 0.008 * jaw, 0);
  }

  if (close > 0.001) {
    addMany(scratch, LIPS_UPPER_INNER, 0, -0.012 * close);
    addMany(scratch, LIPS_LOWER_INNER, 0, 0.012 * close);
  }

  addMany(scratch, LIPS_UPPER_INNER, 0, 0.018 * ((upL + upR) * 0.5));
  addMany(scratch, LIPS_UPPER_OUTER, 0, 0.012 * ((upL + upR) * 0.5));
  addMany(scratch, LIPS_LOWER_INNER, 0, -0.02 * ((lowL + lowR) * 0.5));
  addMany(scratch, LIPS_LOWER_OUTER, 0, -0.016 * ((lowL + lowR) * 0.5));

  // Corners — smile / frown / stretch
  add(scratch, 61, -0.028 * smileL - 0.03 * stretchL, 0.022 * smileL - 0.02 * frownL);
  add(scratch, 291, 0.028 * smileR + 0.03 * stretchR, 0.022 * smileR - 0.02 * frownR);
  add(scratch, 146, -0.012 * smileL, 0.01 * smileL);
  add(scratch, 375, 0.012 * smileR, 0.01 * smileR);
  add(scratch, 185, -0.01 * smileL, 0.012 * smileL);
  add(scratch, 409, 0.01 * smileR, 0.012 * smileR);

  // Funnel / pucker (O, U)
  const inward = funnel * 0.018 + pucker * 0.028;
  const forward = funnel * 0.02 + pucker * 0.03;
  addMany(scratch, LIPS_UPPER_OUTER, 0, 0.006 * (funnel + pucker), forward);
  addMany(scratch, LIPS_LOWER_OUTER, 0, -0.006 * (funnel + pucker), forward);
  add(scratch, 61, inward, 0, forward);
  add(scratch, 291, -inward, 0, forward);

  add(scratch, 61, 0.006 * pressL, 0);
  add(scratch, 291, -0.006 * pressR, 0);

  if (tongue > 0.001) {
    addMany(scratch, LIPS_LOWER_INNER, 0, -0.01 * tongue, 0.02 * tongue);
  }

  // Eyes
  addMany(scratch, LEFT_EYE_LID_UPPER, 0, -0.018 * blinkL);
  addMany(scratch, LEFT_EYE_LID_LOWER, 0, 0.012 * blinkL);
  addMany(scratch, RIGHT_EYE_LID_UPPER, 0, -0.018 * blinkR);
  addMany(scratch, RIGHT_EYE_LID_LOWER, 0, 0.012 * blinkR);

  // Brows
  addMany(scratch, BROW_INNER, 0, 0.016 * browIn, 0);
  addMany(scratch, LEFT_BROW, 0, 0.014 * browOutL - 0.014 * browDownL);
  addMany(scratch, RIGHT_BROW, 0, 0.014 * browOutR - 0.014 * browDownR);

  for (let i = 0; i < n; i++) {
    const o = i * 3;
    target[o] = (target[o] ?? 0) + (scratch[o] ?? 0);
    target[o + 1] = (target[o + 1] ?? 0) + (scratch[o + 1] ?? 0);
    target[o + 2] = (target[o + 2] ?? 0) + (scratch[o + 2] ?? 0);
  }
}

export function headPoseFromWeights(weights: A2FWeights): { yaw: number; pitch: number; roll: number } {
  return {
    yaw: (weights.HeadYaw ?? 0) * 0.22,
    pitch: (weights.HeadPitch ?? 0) * 0.16,
    roll: (weights.HeadRoll ?? 0) * 0.1,
  };
}
