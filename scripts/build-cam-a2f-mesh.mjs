/**
 * Fit NVIDIA Audio2Face ARKit mesh to Cam’s real portrait.
 * Uses MediaPipe Face Landmarker (same topology A2F solved_arkit expects).
 */
import fs from 'node:fs';
import path from 'node:path';
import puppeteer from 'puppeteer-core';
import Delaunator from 'delaunator';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const PHOTO = '/identity/persona/cam-face.jpg';
const OUT = path.join(ROOT, 'public/avatars/cam-a2f-mesh.json');

const LIPS_INNER_LOOP = [
  78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191,
];

function punchMouth(positions, indices, loop) {
  const poly = loop.map((i) => ({ x: positions[i * 3], y: positions[i * 3 + 1] }));
  const inside = (x, y) => {
    let ok = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const xi = poly[i].x;
      const yi = poly[i].y;
      const xj = poly[j].x;
      const yj = poly[j].y;
      const hit = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-9) + xi;
      if (hit) ok = !ok;
    }
    return ok;
  };
  const out = [];
  for (let t = 0; t < indices.length; t += 3) {
    const a = indices[t];
    const b = indices[t + 1];
    const c = indices[t + 2];
    const cx = (positions[a * 3] + positions[b * 3] + positions[c * 3]) / 3;
    const cy = (positions[a * 3 + 1] + positions[b * 3 + 1] + positions[c * 3 + 1]) / 3;
    if (inside(cx, cy)) continue;
    out.push(a, b, c);
  }
  return out;
}

const browser = await puppeteer.launch({
  executablePath: '/usr/local/bin/google-chrome',
  headless: 'new',
  args: [
    '--no-sandbox',
    '--use-gl=angle',
    '--use-angle=swiftshader-webgl',
    '--enable-webgl',
    '--ignore-gpu-blocklist',
    '--enable-unsafe-swiftshader',
  ],
});

try {
  const page = await browser.newPage();
  page.setDefaultTimeout(90000);
  await page.goto('http://127.0.0.1:5173/?v=a2f-mesh', { waitUntil: 'domcontentloaded' });

  const mesh = await page.evaluate(async (photoUrl) => {
    const vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.17/+esm');
    const files = await vision.FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.17/wasm',
    );
    const landmarker = await vision.FaceLandmarker.createFromOptions(files, {
      baseOptions: {
        modelAssetPath:
          'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
      },
      runningMode: 'IMAGE',
      numFaces: 1,
      outputFacialTransformationMatrixes: true,
    });
    const img = await new Promise((resolve, reject) => {
      const el = new Image();
      el.crossOrigin = 'anonymous';
      el.onload = () => resolve(el);
      el.onerror = () => reject(new Error('photo load failed'));
      el.src = photoUrl;
    });
    const res = landmarker.detect(img);
    const face = res.faceLandmarks?.[0];
    if (!face) throw new Error('no face landmarks');
    return {
      width: img.naturalWidth,
      height: img.naturalHeight,
      points: face.map((p) => ({ x: p.x, y: p.y, z: p.z })),
    };
  }, PHOTO);

  const aspect = mesh.width / mesh.height;
  const n = Math.min(468, mesh.points.length);
  const positions = [];
  const uvs = [];
  const pts2 = [];
  for (let i = 0; i < n; i++) {
    const p = mesh.points[i];
    const x = (p.x - 0.5) * aspect;
    const y = 0.5 - p.y;
    const z = -p.z * 0.55;
    positions.push(x, y, z);
    uvs.push(p.x, 1 - p.y);
    pts2.push([x, y]);
  }
  const d = Delaunator.from(pts2);
  const indices = punchMouth(positions, Array.from(d.triangles), LIPS_INNER_LOOP.filter((i) => i < n));

  const payload = {
    version: 1,
    engine: 'audio2face',
    source: 'identity/persona/cam-face.jpg',
    width: mesh.width,
    height: mesh.height,
    positions,
    uvs,
    indices,
    mouthLoop: LIPS_INNER_LOOP.filter((i) => i < n),
  };
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(payload));
  console.log(
    JSON.stringify({
      wrote: OUT,
      verts: n,
      tris: indices.length / 3,
      size: mesh.width + 'x' + mesh.height,
    }),
  );
} finally {
  await browser.close();
}
