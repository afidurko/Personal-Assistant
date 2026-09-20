/** MediaPipe Face Mesh index groups used to apply Audio2Face ARKit deltas. */

export const LIPS_UPPER_OUTER = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291];
export const LIPS_LOWER_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291];
export const LIPS_UPPER_INNER = [78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308];
export const LIPS_LOWER_INNER = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308];
export const LIPS_INNER_LOOP = [
  78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191,
];

export const LEFT_EYE = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246];
export const RIGHT_EYE = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398];
export const LEFT_EYE_LID_UPPER = [159, 158, 157, 173, 246, 161, 160];
export const LEFT_EYE_LID_LOWER = [145, 144, 163, 7, 33, 154, 153];
export const RIGHT_EYE_LID_UPPER = [386, 387, 388, 466, 263, 249, 390];
export const RIGHT_EYE_LID_LOWER = [374, 373, 380, 381, 382, 384, 385];

export const LEFT_BROW = [70, 63, 105, 66, 107, 55, 65, 52, 53, 46];
export const RIGHT_BROW = [300, 293, 334, 296, 336, 285, 295, 282, 283, 276];
export const BROW_INNER = [107, 66, 105, 336, 296, 334];

export const CHIN = [152, 377, 400, 378, 379, 365, 397, 288, 176, 149, 150, 136, 172, 58, 132, 93];
export const JAW = [172, 136, 150, 149, 176, 148, 152, 377, 400, 378, 379, 365, 397, 288, 361, 323];
export const NOSE_TIP = 1;
export const LEFT_MOUTH_CORNER = 61;
export const RIGHT_MOUTH_CORNER = 291;

export const FACE_OVAL = [
  10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148,
  176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
];

export interface CamA2FMesh {
  version: number;
  engine: string;
  source: string;
  width: number;
  height: number;
  positions: number[];
  uvs: number[];
  indices: number[];
  mouthLoop: number[];
}

export function pointInPoly(x: number, y: number, poly: Array<{ x: number; y: number }>): boolean {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i]!.x;
    const yi = poly[i]!.y;
    const xj = poly[j]!.x;
    const yj = poly[j]!.y;
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-9) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

/** Remove triangles whose centroid sits inside the open mouth (so jaw can actually open). */
export function punchMouthHole(
  positions: number[],
  indices: number[],
  mouthLoop: number[],
): number[] {
  const poly = mouthLoop.map((i) => ({
    x: positions[i * 3] ?? 0,
    y: positions[i * 3 + 1] ?? 0,
  }));
  const out: number[] = [];
  for (let t = 0; t < indices.length; t += 3) {
    const a = indices[t]!;
    const b = indices[t + 1]!;
    const c = indices[t + 2]!;
    const cx = ((positions[a * 3] ?? 0) + (positions[b * 3] ?? 0) + (positions[c * 3] ?? 0)) / 3;
    const cy =
      ((positions[a * 3 + 1] ?? 0) + (positions[b * 3 + 1] ?? 0) + (positions[c * 3 + 1] ?? 0)) / 3;
    if (pointInPoly(cx, cy, poly)) continue;
    out.push(a, b, c);
  }
  return out;
}
