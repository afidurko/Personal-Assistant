import { LEFT_EYE, LIPS_INNER_LOOP, RIGHT_EYE, type CamA2FMesh } from './landmarks';

export interface CamA2FFit {
  mouthCenter: { x: number; y: number };
  mouthSize: { x: number; y: number };
  eyeL: { x: number; y: number };
  eyeR: { x: number; y: number };
  eyeSize: { x: number; y: number };
}

function meanUv(mesh: CamA2FMesh, ids: number[]) {
  let x = 0;
  let y = 0;
  let n = 0;
  for (const i of ids) {
    if (i * 2 + 1 >= mesh.uvs.length) continue;
    x += mesh.uvs[i * 2] ?? 0;
    y += mesh.uvs[i * 2 + 1] ?? 0;
    n += 1;
  }
  return { x: x / Math.max(1, n), y: y / Math.max(1, n) };
}

function spanUv(mesh: CamA2FMesh, ids: number[]) {
  let minX = 1;
  let maxX = 0;
  let minY = 1;
  let maxY = 0;
  for (const i of ids) {
    if (i * 2 + 1 >= mesh.uvs.length) continue;
    const x = mesh.uvs[i * 2] ?? 0;
    const y = mesh.uvs[i * 2 + 1] ?? 0;
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  }
  return { x: Math.max(0.04, maxX - minX), y: Math.max(0.02, maxY - minY) };
}

export function fitFromMesh(mesh: CamA2FMesh): CamA2FFit {
  const loop = mesh.mouthLoop?.length ? mesh.mouthLoop : LIPS_INNER_LOOP;
  const mouthCenter = meanUv(mesh, loop);
  const mouthSize = spanUv(mesh, loop);
  return {
    mouthCenter,
    mouthSize: { x: mouthSize.x * 0.98, y: Math.max(0.018, mouthSize.y) },
    eyeL: meanUv(mesh, LEFT_EYE),
    eyeR: meanUv(mesh, RIGHT_EYE),
    eyeSize: { x: 0.07, y: 0.045 },
  };
}
