/* Cam Cortex — anatomical FreeSurfer shell + DTI tracts + live agents */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";
import { loadCamCortex, applyFsCameraUp, installGlassEnvironment } from "./cortex-anatomy.js";

/** Positions are FreeSurfer-like RAS (X=R+, Y=A+, Z=S+) matching cam-cortex.glb */
const AREAS = [
  { id: "area.dlpfc", label: "DLPFC", ba: "BA9/46", p: [-0.526, 1.49, 0.235], r: 0.28, lobe: "frontal" },
  { id: "area.apfc", label: "aPFC", ba: "BA10", p: [-0.234, 2.137, -0.834], r: 0.22, lobe: "frontal" },
  { id: "area.ofc", label: "OFC", ba: "BA11", p: [-0.518, 1.209, -0.855], r: 0.2, lobe: "frontal" },
  { id: "area.broca", label: "Broca", ba: "BA44/45", p: [-1.29, 1.139, -0.252], r: 0.22, lobe: "frontal" },
  { id: "area.premotor", label: "PM/SMA", ba: "BA6", p: [-0.922, 0.905, 0.759], r: 0.16, lobe: "frontal" },
  { id: "area.motor", label: "M1", ba: "BA4", p: [-0.91, 0.301, 0.787], r: 0.18, lobe: "frontal" },
  { id: "area.parietal", label: "Parietal", ba: "BA5/7", p: [-0.771, -0.858, 0.796], r: 0.24, lobe: "parietal" },
  { id: "area.wernicke", label: "Wernicke+", ba: "BA22+", p: [-1.41, -0.55, 0.474], r: 0.22, lobe: "temporoparietal" },
  { id: "area.temporal", label: "Temporal", ba: "BA20/21", p: [-1.328, -0.58, -0.683], r: 0.26, lobe: "temporal" },
  { id: "area.auditory", label: "Auditory", ba: "BA41/42", p: [-1.461, -0.007, -0.329], r: 0.16, lobe: "temporal" },
  { id: "area.visual", label: "Visual", ba: "BA17–19", p: [-0.532, -1.758, -0.048], r: 0.26, lobe: "occipital" },
  { id: "area.mtl", label: "MTL", ba: "memory", p: [-0.732, -0.308, -0.7], r: 0.22, lobe: "medial_temporal" },
  { id: "area.cingulate", label: "ACC", ba: "BA24/32", p: [-0.16, 0.266, 0.168], r: 0.2, lobe: "medial" },
];

let cortexApi = null;
let anatomyReady = false;

const TRACTS = [
  { id: "tract.arcuate", a: "area.wernicke", b: "area.broca", arch: "sylvian", fibers: 48, system: "arcuate_language", myelination: 0.82 },
  { id: "tract.af_anterior", a: "area.broca", b: "area.parietal", arch: "lateral_high", fibers: 36, system: "arcuate_language", myelination: 0.78 },
  { id: "tract.af_posterior", a: "area.wernicke", b: "area.parietal", arch: "lateral_high", fibers: 36, system: "arcuate_language", myelination: 0.76 },
  { id: "tract.slf3", a: "area.parietal", b: "area.broca", arch: "lateral_high", fibers: 28, system: "arcuate_language", myelination: 0.77 },
  { id: "tract.fat", a: "area.broca", b: "area.premotor", arch: "frontal_slant", fibers: 24, system: "arcuate_language", myelination: 0.75 },
  { id: "tract.slf", a: "area.parietal", b: "area.dlpfc", arch: "dorsal", fibers: 32, system: "arcuate_language", myelination: 0.8 },
  { id: "tract.slf1", a: "area.parietal", b: "area.premotor", arch: "dorsal", fibers: 24, system: "cingulum_system", myelination: 0.74 },
  { id: "tract.cingulum", a: "area.cingulate", b: "area.mtl", arch: "medial", fibers: 40, system: "cingulum_system", myelination: 0.81 },
  { id: "tract.cingulum2", a: "area.mtl", b: "area.dlpfc", alias: "tract.cingulum", arch: "medial", fibers: 28, system: "cingulum_system", myelination: 0.81 },
  { id: "tract.fornix", a: "area.mtl", b: "area.cingulate", arch: "fornix", fibers: 32, system: "cingulum_system", myelination: 0.84 },
  { id: "tract.uncinate", a: "area.ofc", b: "area.temporal", arch: "uncinate", fibers: 30, system: "anterior_ventral", myelination: 0.7 },
  { id: "tract.ifof", a: "area.visual", b: "area.apfc", arch: "long_ventral", fibers: 40, system: "anterior_ventral", myelination: 0.79 },
  { id: "tract.emc", a: "area.temporal", b: "area.broca", arch: "ventral", fibers: 26, system: "anterior_ventral", myelination: 0.72 },
  { id: "tract.ilf", a: "area.visual", b: "area.temporal", arch: "ventral", fibers: 36, system: "posterior_ventral", myelination: 0.78 },
  { id: "tract.mdlf", a: "area.auditory", b: "area.parietal", arch: "mid_temporal", fibers: 24, system: "posterior_ventral", myelination: 0.73 },
  { id: "tract.vof", a: "area.visual", b: "area.parietal", arch: "vertical", fibers: 22, system: "posterior_ventral", myelination: 0.71 },
  { id: "tract.forceps_minor", a: "area.dlpfc", b: "area.apfc", arch: "callosal_front", fibers: 40, system: "commissural", myelination: 0.85 },
  { id: "tract.forceps_major", a: "area.visual", b: "area.parietal", arch: "callosal_back", fibers: 36, system: "commissural", myelination: 0.83 },
  { id: "tract.corticospinal", a: "area.premotor", b: "area.motor", arch: "descending", fibers: 28, system: "projection", myelination: 0.9 },
  // callosal cross for left-right red glow
  { id: "tract.callosal_bridge", a: "area.dlpfc", b: "area.parietal", arch: "callosal_front", fibers: 50, system: "commissural", myelination: 0.86 },
];

const SPIKES = [
  { id: "sense.chat.aaron", label: "Aaron task", pathway: ["area.wernicke", "area.temporal", "area.mtl"], tracts: ["tract.arcuate", "tract.cingulum", "tract.cingulum2"], gold: true, agents: ["neuron.language_in", "neuron.semantic", "neuron.memory"] },
  { id: "sense.language.af", label: "AF language", pathway: ["area.wernicke", "area.parietal", "area.broca"], tracts: ["tract.arcuate", "tract.af_posterior", "tract.af_anterior"], gold: true, system: "arcuate_language", agents: ["neuron.comms", "neuron.speak_loop"] },
  { id: "sense.dual.ventral", label: "Ventral semantic", pathway: ["area.visual", "area.temporal", "area.ofc"], tracts: ["tract.ilf", "tract.emc", "tract.uncinate"], system: "anterior_ventral", agents: ["neuron.research", "neuron.boundary"] },
  { id: "sense.swiftguide.map", label: "SwiftGuide", pathway: ["area.apfc", "area.mtl"], tracts: ["tract.ifof", "tract.cingulum", "tract.fornix"], gold: true, agents: ["neuron.cartographer", "neuron.memory"] },
  { id: "sense.audio.transcript", label: "Speak/hear", pathway: ["area.auditory", "area.broca", "area.motor"], tracts: ["tract.arcuate", "tract.fat", "tract.corticospinal"], agents: ["neuron.asr", "neuron.speak_loop", "neuron.effector"] },
  { id: "sense.careers.listing", label: "Jobs", pathway: ["area.temporal", "area.ofc"], tracts: ["tract.uncinate"], agents: ["neuron.careers", "neuron.watch_loop"] },
  { id: "sense.vision.detection", label: "Vision", pathway: ["area.visual", "area.temporal", "area.mtl"], tracts: ["tract.ilf", "tract.vof", "tract.cingulum"], agents: ["neuron.vision", "neuron.enroll_loop"] },
  { id: "sense.memory.fornix", label: "Episodic recall", pathway: ["area.mtl", "area.cingulate", "area.dlpfc"], tracts: ["tract.fornix", "tract.cingulum", "tract.cingulum2"], agents: ["neuron.memory", "neuron.mesh_sync_loop"] },
  { id: "health.scan", label: "Health scan", pathway: ["area.cingulate", "area.parietal", "area.dlpfc", "area.mtl"], tracts: ["tract.cingulum", "tract.cingulum2", "tract.slf"], gold: true, health: true, agents: ["neuron.health_conductor", "neuron.qa_cycle"] },
];

const areaById = Object.fromEntries(AREAS.map((a) => [a.id, a]));
const logEl = document.getElementById("log");
const scrub = document.getElementById("scrub");
const chipT = document.getElementById("chip-t");
const chipErr = document.getElementById("chip-err");
const chipPlast = document.getElementById("chip-plast");
const chipNeuro = document.getElementById("chip-neuro");
const chipKill = document.getElementById("chip-kill");
const weightsEl = document.getElementById("weights");
const controlsEl = document.getElementById("controls");
const agentsEl = document.getElementById("agents");
const liveChip = document.getElementById("chip-live");

/** Resolve paths from this module so fetches work from any static-server root */
function repoUrl(rel, query = "") {
  const u = new URL(rel, import.meta.url);
  if (query) u.search = query.startsWith("?") ? query.slice(1) : query;
  return u.href;
}

let weights = Object.fromEntries(TRACTS.map((t) => [t.alias || t.id, 0.55]));
let myelination = Object.fromEntries(TRACTS.map((t) => [t.alias || t.id, t.myelination || 0.7]));
let events = [];
let cursor = 0;
let playing = false;
let killed = false;
let neuroColumns = [];
let catalogNeurons = [];
let errorCount = 0;
let healthStatus = {};
let fiberPulses = [];
let highlightedSystem = null;
let tractActivity = Object.fromEntries(TRACTS.map((t) => [t.id, 0]));
let areaActivity = Object.fromEntries(AREAS.map((a) => [a.id, 0]));
let agentActivity = {};
let liveFeed = null;
let autoSim = true;

const areaMeshes = {};
const tractLineGroups = {};

function log(html) {
  const d = document.createElement("div");
  d.className = "entry";
  d.innerHTML = html;
  logEl.prepend(d);
}

/** Standard DTI RGB: R=L↔R, G=A↔P (z), B=S↔I (y) */
function dtiColor(dir) {
  const d = dir.clone().normalize();
  const r = Math.abs(d.x);
  const g = Math.abs(d.z);
  const b = Math.abs(d.y);
  const s = r + g + b || 1;
  return new THREE.Color(r / s, g / s, b / s);
}

const viewport = document.getElementById("viewport");
const canvas = document.getElementById("c");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(0x05080a, 1);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;

const labelRenderer = new CSS2DRenderer();
labelRenderer.domElement.style.position = "absolute";
labelRenderer.domElement.style.inset = "0";
labelRenderer.domElement.style.pointerEvents = "none";
viewport.appendChild(labelRenderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x05080a, 0.022);

const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
applyFsCameraUp(camera);
camera.position.set(2.8, 5.5, 2.2);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.05;
controls.target.set(0, 0.1, 0.15);
controls.minDistance = 2.2;
controls.maxDistance = 14;
applyFsCameraUp(camera, controls);

scene.add(new THREE.AmbientLight(0xb8d4cc, 0.7));
const key = new THREE.DirectionalLight(0xfff5e8, 0.85);
key.position.set(3, 4, 6);
scene.add(key);
const fill = new THREE.DirectionalLight(0x88b0cc, 0.35);
fill.position.set(-4, -2, 2);
scene.add(fill);
const rim = new THREE.DirectionalLight(0x5fd4c4, 0.4);
rim.position.set(0, -5, 3);
scene.add(rim);
const bounce = new THREE.HemisphereLight(0xcfe8e0, 0x1a1008, 0.35);
scene.add(bounce);

installGlassEnvironment(renderer, scene);

const brain = new THREE.Group();
scene.add(brain);

function makeLabel(text, cls = "label3d dti") {
  const div = document.createElement("div");
  div.className = cls;
  div.textContent = text;
  return new CSS2DObject(div);
}

function fasciculusCurve(t) {
  const A = new THREE.Vector3(...areaById[t.a].p);
  const B = new THREE.Vector3(...areaById[t.b].p);
  const mid = A.clone().add(B).multiplyScalar(0.5);
  const arch = t.arch || "dorsal";
  if (arch === "sylvian") {
    mid.y += 0.9;
    mid.x += 0.4;
    mid.z += 0.3;
  } else if (arch === "lateral_high") {
    mid.y += 0.75;
    mid.x += 0.55;
  } else if (arch === "dorsal") mid.y += 0.7;
  else if (arch === "medial") {
    mid.y += 0.4;
    mid.x *= 0.25;
  } else if (arch === "fornix") {
    mid.y += 1.05;
    mid.z -= 0.25;
  } else if (arch === "uncinate") {
    mid.y -= 0.4;
    mid.z += 0.5;
  } else if (arch === "long_ventral") {
    mid.y -= 0.3;
    mid.z += 0.2;
  } else if (arch === "ventral") mid.y -= 0.45;
  else if (arch === "mid_temporal") {
    mid.y += 0.2;
    mid.z += 0.4;
  } else if (arch === "vertical") mid.x += 0.25;
  else if (arch === "frontal_slant") {
    mid.y += 0.6;
    mid.z += 0.25;
  } else if (arch === "callosal_front" || arch === "callosal_back") {
    mid.x = 0;
    mid.y += arch === "callosal_front" ? 0.55 : 0.3;
  } else if (arch === "descending") mid.y -= 0.2;
  else mid.y += 0.5;
  return new THREE.QuadraticBezierCurve3(A, mid, B);
}

function offsetCurve(curve, idx, n, spread) {
  const pts = [];
  const steps = 36;
  const ang = (idx / Math.max(n, 1)) * Math.PI * 2;
  const rad = spread * (0.4 + (idx % 5) * 0.22);
  for (let i = 0; i <= steps; i++) {
    const u = i / steps;
    const p = curve.getPoint(u);
    const tng = curve.getTangent(u).normalize();
    const up = Math.abs(tng.y) > 0.92 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0);
    const nrm = new THREE.Vector3().crossVectors(tng, up).normalize();
    const bin = new THREE.Vector3().crossVectors(tng, nrm).normalize();
    p.addScaledVector(nrm, Math.cos(ang + u * 0.8) * rad);
    p.addScaledVector(bin, Math.sin(ang + u * 0.8) * rad * 0.85);
    pts.push(p);
  }
  return new THREE.CatmullRomCurve3(pts);
}

/** Build dense DTI-style Line segments for one fasciculus */
function buildDtiFasciculus(t) {
  const key = t.alias || t.id;
  const curve = fasciculusCurve(t);
  const group = new THREE.Group();
  group.userData = { id: t.id, alias: key, curve, system: t.system, lines: [], baseOpacity: 0.32 };
  const n = t.fibers || 28;
  const spread = 0.07;

  for (let i = 0; i < n; i++) {
    const fc = offsetCurve(curve, i, n, spread);
    const positions = [];
    const colors = [];
    const segs = 40;
    for (let s = 0; s <= segs; s++) {
      const u = s / segs;
      const p = fc.getPoint(u);
      const tang = fc.getTangent(u);
      positions.push(p.x, p.y, p.z);
      const c = dtiColor(tang);
      colors.push(c.r, c.g, c.b);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    const mat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.32,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const line = new THREE.Line(geo, mat);
    line.userData = { fiber: true };
    line.renderOrder = 0;
    group.add(line);
    group.userData.lines.push(line);
  }

  brain.add(group);
  tractLineGroups[t.id] = group;
  return group;
}

/** Ambient U-fibers + projection spray so the volume reads as a full DTI brain */
let ambientLines = null;
let lodHigh = true;

function buildAmbientConnectome(budget = 900) {
  if (ambientLines) {
    brain.remove(ambientLines);
    ambientLines.geometry.dispose();
    ambientLines.material.dispose();
    ambientLines = null;
  }
  const positions = [];
  const colors = [];
  // Local U-fibers between nearby areas
  for (let i = 0; i < AREAS.length; i++) {
    for (let j = i + 1; j < AREAS.length; j++) {
      const A = new THREE.Vector3(...AREAS[i].p);
      const B = new THREE.Vector3(...AREAS[j].p);
      if (A.distanceTo(B) > 2.2) continue;
      const copies = budget > 500 ? 6 : 2;
      for (let k = 0; k < copies; k++) {
        const mid = A.clone().add(B).multiplyScalar(0.5);
        mid.y += 0.15 + Math.random() * 0.35;
        mid.add(new THREE.Vector3((Math.random() - 0.5) * 0.3, (Math.random() - 0.5) * 0.2, (Math.random() - 0.5) * 0.3));
        const curve = new THREE.QuadraticBezierCurve3(A, mid, B);
        for (let s = 0; s < 12; s++) {
          const u0 = s / 12;
          const u1 = (s + 1) / 12;
          const p0 = curve.getPoint(u0);
          const p1 = curve.getPoint(u1);
          const dir = p1.clone().sub(p0);
          const c = dtiColor(dir);
          positions.push(p0.x, p0.y, p0.z, p1.x, p1.y, p1.z);
          colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
        }
      }
    }
  }
  // Projection spray toward brainstem (FS inferior-posterior)
  const stem = new THREE.Vector3(0, -0.6, -1.5);
  AREAS.forEach((a) => {
    const A = new THREE.Vector3(...a.p);
    const copies = budget > 500 ? 8 : 3;
    for (let k = 0; k < copies; k++) {
      const mid = A.clone().lerp(stem, 0.5);
      mid.x += (Math.random() - 0.5) * 0.4;
      const curve = new THREE.QuadraticBezierCurve3(A, mid, stem);
      for (let s = 0; s < 10; s++) {
        const p0 = curve.getPoint(s / 10);
        const p1 = curve.getPoint((s + 1) / 10);
        const c = dtiColor(p1.clone().sub(p0));
        positions.push(p0.x, p0.y, p0.z, p1.x, p1.y, p1.z);
        colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
      }
    }
  });
  // Dense random shell fibers for DTI hair volume (FS-shaped ellipsoid)
  for (let i = 0; i < budget; i++) {
    const u = Math.random() * Math.PI * 2;
    const v = Math.acos(2 * Math.random() - 1);
    const rr = 1.0 + Math.random() * 1.2;
    const x = Math.sin(v) * Math.cos(u) * rr * 1.15;
    const y = Math.sin(v) * Math.sin(u) * rr * 1.35;
    const z = Math.cos(v) * rr * 0.85;
    if (z < -1.6) continue;
    const len = 0.12 + Math.random() * 0.35;
    const dir = new THREE.Vector3(Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5).normalize();
    if (Math.abs(x) < 0.4) dir.set(Math.sign(Math.random() - 0.5) || 1, dir.y * 0.3, dir.z * 0.4).normalize();
    const p0 = new THREE.Vector3(x, y, z);
    const p1 = p0.clone().addScaledVector(dir, len);
    const c = dtiColor(dir);
    positions.push(p0.x, p0.y, p0.z, p1.x, p1.y, p1.z);
    colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  const mat = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 0.38,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });
  ambientLines = new THREE.LineSegments(geo, mat);
  ambientLines.userData = { ambient: true };
  ambientLines.renderOrder = 0;
  brain.add(ambientLines);
}

const isMobile = /Mobi|Android/i.test(navigator.userAgent) || Math.min(window.innerWidth, window.innerHeight) < 700;
lodHigh = !isMobile;

/** Area markers — subtle when anatomical shell is present */
const areaLabels = {};
AREAS.forEach((a) => {
  const mat = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.0,
    depthWrite: false,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(a.r * 0.12, 12, 10), mat);
  mesh.position.set(...a.p);
  mesh.visible = false;
  brain.add(mesh);
  const lab = makeLabel(`${a.label}`);
  lab.position.set(a.p[0], a.p[1] + a.r * 0.15, a.p[2] + a.r * 0.1);
  brain.add(lab);
  areaMeshes[a.id] = mesh;
  areaLabels[a.id] = lab;
});

function clearTractsAndAmbient() {
  Object.keys(tractLineGroups).forEach((id) => {
    const g = tractLineGroups[id];
    brain.remove(g);
    g.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      if (o.material) o.material.dispose();
    });
    delete tractLineGroups[id];
  });
  if (ambientLines) {
    brain.remove(ambientLines);
    ambientLines.geometry.dispose();
    ambientLines.material.dispose();
    ambientLines = null;
  }
}

function rebuildConnectomeFibers() {
  clearTractsAndAmbient();
  TRACTS.forEach(buildDtiFasciculus);
  buildAmbientConnectome(lodHigh ? 700 : 220);
}

function reanchorAreasFromCortex() {
  if (!cortexApi?.centroids) return;
  AREAS.forEach((a) => {
    const c = cortexApi.centroids[a.id];
    if (!c) return;
    a.p = c;
    areaById[a.id].p = c;
    const m = areaMeshes[a.id];
    if (m) m.position.set(...c);
    const lab = areaLabels[a.id];
    if (lab) lab.position.set(c[0], c[1] + a.r * 0.15, c[2] + a.r * 0.1);
  });
}

async function bootAnatomy() {
  // Suggestive: keep AREAS centroids + lobe colors aligned with config before shell load
  let lobeColors = null;
  try {
    const cdoc = await fetch(repoUrl("../../config/connectome/anatomy-centroids.json")).then((r) => r.json());
    const cents = cdoc.centroids || {};
    lobeColors = cdoc.lobe_colors || null;
    AREAS.forEach((a) => {
      if (cents[a.id]) {
        a.p = cents[a.id];
        areaById[a.id].p = cents[a.id];
      }
    });
  } catch (_) {
    /* offline — hardcoded AREAS remain */
  }
  try {
    cortexApi = await loadCamCortex(brain, {
      url: new URL("./assets/cam-cortex.glb", import.meta.url).href,
      lobeColors: lobeColors || undefined,
    });
    reanchorAreasFromCortex();
    anatomyReady = true;
    cortexApi.setTranslucency(0.82);
    log(`<span class="center">CORTEX</span> glass shell · ${Object.keys(cortexApi.parcels).length} parcels · CC BY-SA`);
  } catch (e) {
    anatomyReady = false;
    // Show fallback spheres if GLB missing
    Object.values(areaMeshes).forEach((m) => {
      m.visible = true;
      m.material.opacity = 0.2;
    });
    log(`<span class="motor">CORTEX</span> shell missing — fiber fallback (${e.message || e})`);
  }
  rebuildConnectomeFibers();
  refreshTracts();
}

bootAnatomy();

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
renderer.domElement.addEventListener("pointerdown", (ev) => {
  if (!cortexApi) return;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const areaId = cortexApi.pickArea(raycaster);
  if (!areaId) return;
  const a = areaById[areaId];
  setAreaLit(areaId, "lit");
  areaActivity[areaId] = Math.max(areaActivity[areaId] || 0, 0.85);
  controls.target.set(...(a?.p || [0, 0, 0]));
  log(`<span class="center">AREA</span> ${a?.label || areaId} · ${a?.ba || ""}`);
  // Pulse tracts touching this area
  TRACTS.filter((t) => t.a === areaId || t.b === areaId).forEach((t) => pulseAlongTract(t.id));
});

function resize() {
  const w = viewport.clientWidth;
  const h = viewport.clientHeight;
  renderer.setSize(w, h, false);
  labelRenderer.setSize(w, h);
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);
resize();

function setAreaLit(id, mode) {
  const m = areaMeshes[id];
  const act = areaActivity[id] || 0;
  if (m?.visible) {
    if (mode === "lit") {
      m.material.color.set("#5fd4ff");
      m.material.opacity = 0.85;
      areaActivity[id] = Math.max(act, 0.9);
    } else if (mode === "error") {
      m.material.color.set("#ff5533");
      m.material.opacity = 0.9;
    } else if (mode === "feedback") {
      m.material.color.set("#ffe066");
      m.material.opacity = 0.75;
      areaActivity[id] = Math.max(act, 0.7);
    } else {
      m.material.color.setRGB(0.6 + act * 0.4, 0.7 + act * 0.3, 1);
      m.material.opacity = 0.12 + act * 0.55;
    }
  }
  if (mode === "lit") areaActivity[id] = Math.max(areaActivity[id] || 0, 0.9);
  else if (mode === "feedback") areaActivity[id] = Math.max(areaActivity[id] || 0, 0.7);
  if (cortexApi) {
    const heat = areaActivity[id] || 0;
    cortexApi.setParcelHeat(id, heat, mode === "off" ? "idle" : mode);
  }
}

function setTractGlow(tractId, intensity) {
  const g = tractLineGroups[tractId];
  if (!g) return;
  tractActivity[tractId] = Math.max(tractActivity[tractId] || 0, intensity);
  const op = 0.28 + intensity * 0.7;
  g.userData.lines.forEach((ln) => {
    ln.material.opacity = op;
  });
}

function decayActivity(dt) {
  Object.keys(tractActivity).forEach((id) => {
    tractActivity[id] = Math.max(0, (tractActivity[id] || 0) - dt * 0.25);
    const g = tractLineGroups[id];
    if (!g) return;
    const dimmed = highlightedSystem && g.userData.system !== highlightedSystem;
    const op = dimmed ? 0.06 : 0.26 + tractActivity[id] * 0.72;
    g.userData.lines.forEach((ln) => {
      ln.material.opacity = op;
    });
    g.visible = !dimmed || tractActivity[id] > 0.2;
  });
  Object.keys(areaActivity).forEach((id) => {
    areaActivity[id] = Math.max(0, (areaActivity[id] || 0) - dt * 0.2);
    setAreaLit(id, "off");
  });
  if (cortexApi) cortexApi.decayHeats(areaActivity);
  Object.keys(agentActivity).forEach((id) => {
    agentActivity[id] = Math.max(0, (agentActivity[id] || 0) - dt * 0.15);
  });
}

function pulseAlongTract(tractId) {
  const g = tractLineGroups[tractId];
  if (!g?.userData?.curve) return;
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(0.04, 8, 6),
    new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.95, blending: THREE.AdditiveBlending })
  );
  mesh.userData = { curve: g.userData.curve, u: 0, speed: 0.55, tractId };
  brain.add(mesh);
  fiberPulses.push(mesh);
  setTractGlow(tractId, 1);
}

function refreshTracts(errorIds = new Set()) {
  TRACTS.forEach((t) => {
    if (errorIds.has(t.id) || errorIds.has(t.alias || t.id)) {
      const g = tractLineGroups[t.id];
      g?.userData.lines.forEach((ln) => {
        ln.material.opacity = 0.9;
        // tint toward coral by rebuilding would be heavy — bump opacity only
      });
    }
  });
  renderWeights();
  renderAgents();
}

function renderWeights() {
  weightsEl.innerHTML = "";
  Object.entries(weights)
    .sort((a, b) => (tractActivity[a[0]] || 0) - (tractActivity[b[0]] || 0) || b[1] - a[1])
    .reverse()
    .slice(0, 12)
    .forEach(([id, w]) => {
      const act = tractActivity[id] || 0;
      const row = document.createElement("div");
      row.className = "weight-row" + (act > 0.3 ? " active" : "");
      row.innerHTML = `<span>${id.replace("tract.", "")}</span><i style="width:${Math.round(Math.max(w, act) * 100)}%"></i><em>${act > 0.05 ? "LIVE" : w.toFixed(2)}</em>`;
      weightsEl.appendChild(row);
    });
}

function renderAgents() {
  if (!agentsEl) return;
  agentsEl.innerHTML = "";
  const rows = Object.entries(agentActivity)
    .filter(([, v]) => v > 0.05)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 14);
  if (!rows.length) {
    agentsEl.innerHTML = `<div class="agent-row dim">awaiting standing loops…</div>`;
    return;
  }
  rows.forEach(([id, v]) => {
    const n = catalogNeurons.find((x) => x.id === id);
    const row = document.createElement("div");
    row.className = "agent-row on";
    row.innerHTML = `<b>${id.replace("neuron.", "")}</b><span>${n?.kind || "agent"} · ${(n?.area || "").replace("area.", "")}</span><i style="width:${Math.round(v * 100)}%"></i>`;
    row.style.cursor = "pointer";
    row.title = "Fly to cortical area";
    row.addEventListener("click", () => {
      const areaId = n?.area;
      if (!areaId || !areaById[areaId]) return;
      const p = areaById[areaId].p;
      controls.target.set(...p);
      setAreaLit(areaId, "lit");
      areaActivity[areaId] = Math.max(areaActivity[areaId] || 0, 0.9);
      TRACTS.filter((t) => t.a === areaId || t.b === areaId).forEach((t) => pulseAlongTract(t.id));
      log(`<span class="center">AGENT</span> ${id} → ${areaId}`);
    });
    agentsEl.appendChild(row);
  });
}

function highlightSystem(sys) {
  highlightedSystem = highlightedSystem === sys ? null : sys;
  refreshTracts();
  log(`<span class="center">MESH</span> system filter: ${highlightedSystem || "all"}`);
}

function clearLights() {
  AREAS.forEach((a) => setAreaLit(a.id, "off"));
}

function applyEvent(ev) {
  if (!ev) return;
  if (ev.type === "synapse") {
    setAreaLit(ev.from, ev.status === "error" ? "error" : "lit");
    setAreaLit(ev.to, ev.status === "error" ? "error" : "lit");
    if (ev.status === "error") {
      errorCount += 1;
      chipErr.textContent = `errors: ${errorCount}`;
      chipErr.classList.add("on");
      log(`<span class="motor">ERR</span> ${ev.from} → ${ev.to}`);
    }
  } else if (ev.type === "ltp") {
    (ev.tracts || []).forEach((tid) => {
      weights[tid] = Math.min(1, (weights[tid] || 0.55) + 0.08 * (ev.gain || 1));
      myelination[tid] = Math.min(0.98, (myelination[tid] || 0.7) + 0.01);
      pulseAlongTract(tid);
    });
    Object.keys(weights).forEach((tid) => {
      if (!(ev.tracts || []).includes(tid)) weights[tid] = Math.max(0.05, weights[tid] - 0.01);
    });
    (ev.pathway || []).filter((x) => x.startsWith("area.")).forEach((id) => setAreaLit(id, "feedback"));
    chipPlast.textContent = "LTP + myelin";
    chipPlast.classList.add("on");
    log(`<span class="center">LTP</span> ${(ev.tracts || []).join(", ")}`);
    persistWeights();
    refreshTracts();
  } else if (ev.type === "error") {
    errorCount += 1;
    chipErr.textContent = `errors: ${errorCount}`;
    chipErr.classList.add("on");
    const errSet = new Set(ev.tracts || []);
    if (ev.code === "kill") {
      killed = true;
      chipKill.classList.add("on");
      chipKill.textContent = "KILL";
      Object.keys(weights).forEach((tid) => {
        weights[tid] = Math.max(0.05, weights[tid] - 0.12);
      });
      log(`<span class="motor">KILL</span> LTD on tracts`);
    } else if (ev.code === "missing_edge") {
      (ev.tracts || []).forEach((tid) => {
        weights[tid] = Math.max(0.05, (weights[tid] || 0.55) - 0.12);
        setTractGlow(tid, 1);
      });
      log(`<span class="motor">TRACT ERR</span> ${(ev.tracts || []).join(", ")}`);
    }
    refreshTracts(errSet);
  } else if (ev.type === "prune") {
    weights[ev.tract] = Math.min(weights[ev.tract] || 0.1, 0.1);
    refreshTracts(new Set([ev.tract]));
    log(`<span class="back">PRUNE</span> ${ev.tract}`);
  } else if (ev.type === "neurogenesis" || ev.type === "neurogenesis_mature") {
    spawnNeuroColumn(ev.column || "neuron.mtl_new", ev.stage || "immature");
    chipNeuro.classList.add("on");
    chipNeuro.textContent = ev.stage || "neurogenesis";
    log(`<span class="center">NEUROGENESIS</span> ${ev.column || ""} · ${ev.stage || ""}`);
  } else if (ev.type === "health_scan") {
    setAreaLit("area.cingulate", ev.status === "ok" ? "lit" : "error");
    setAreaLit("area.parietal", "lit");
    setAreaLit("area.dlpfc", "feedback");
    ["tract.cingulum", "tract.cingulum2", "tract.slf"].forEach((tid) => pulseAlongTract(tid));
    log(`<span class="center">HEALTH</span> ${ev.overall || ev.status} · ${(ev.neurons || []).length} neurons`);
    chipPlast.textContent = "health";
    chipPlast.classList.add("on");
  }
}

function spawnNeuroColumn(id, stage) {
  const mtl = areaById["area.mtl"];
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(stage === "mature" ? 0.07 : 0.05, 10, 8),
    new THREE.MeshBasicMaterial({
      color: stage === "mature" ? 0x5fd4ff : 0xffe066,
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
    })
  );
  const ang = Math.random() * Math.PI * 2;
  mesh.position.set(mtl.p[0] + Math.cos(ang) * 0.3, mtl.p[1] + 0.2, mtl.p[2] + Math.sin(ang) * 0.3);
  mesh.userData = { id, neuro: true, stage };
  brain.add(mesh);
  neuroColumns.push(mesh);
  setAreaLit("area.mtl", "feedback");
}

function seek(t) {
  cursor = Math.max(0, Math.min(t, Math.max(events.length - 1, 0)));
  scrub.value = String(cursor);
  chipT.textContent = `t=${cursor}/${Math.max(events.length - 1, 0)}`;
  weights = Object.fromEntries(TRACTS.map((tr) => [tr.alias || tr.id, 0.55]));
  myelination = Object.fromEntries(TRACTS.map((tr) => [tr.alias || tr.id, tr.myelination || 0.7]));
  errorCount = 0;
  killed = false;
  chipKill.classList.remove("on");
  chipKill.textContent = "kill armed";
  chipErr.textContent = "errors: 0";
  chipErr.classList.remove("on");
  neuroColumns.splice(0).forEach((m) => brain.remove(m));
  fiberPulses.splice(0).forEach((m) => brain.remove(m));
  clearLights();
  for (let i = 0; i <= cursor; i++) applyEvent(events[i]);
  refreshTracts();
}

function pushLocalEvent(ev) {
  events.push({ ...ev, t: events.length });
  scrub.max = String(Math.max(events.length - 1, 0));
  seek(events.length - 1);
}

function fireAgents(agentIds = [], intensity = 0.85) {
  agentIds.forEach((id) => {
    agentActivity[id] = Math.max(agentActivity[id] || 0, intensity);
  });
  renderAgents();
}

async function fireSpike(spike, injectError = false) {
  if (killed) {
    log(`<span class="motor">BLOCKED</span> kill active`);
    return;
  }
  log(`<span class="in">TASK</span> ${spike.id}`);
  clearLights();
  fireAgents(spike.agents || [], 1);
  if (spike.system) highlightSystem(spike.system);
  if (spike.health) {
    try {
      const r = await fetch(repoUrl("../../vault/10-Mesh-Distillates/system-health.json")).then((x) => x.json());
      (r.checks || []).forEach((c) => {
        healthStatus[c.neuron] = c.status;
        agentActivity[c.neuron] = c.status === "healthy" ? 0.5 : c.status === "idle" ? 0.2 : 0.95;
      });
      clearLights();
      for (const id of spike.pathway || []) {
        setAreaLit(id, r.overall === "critical" ? "error" : r.overall === "warning" ? "feedback" : "lit");
        await new Promise((res) => setTimeout(res, 160));
      }
      (spike.tracts || []).forEach((tid) => pulseAlongTract(tid));
      pushLocalEvent({
        type: "health_scan",
        status: r.overall === "critical" ? "warn" : "ok",
        overall: r.overall,
        neurons: r.neurons_fired || [],
      });
      renderAgents();
      return;
    } catch (e) {
      log(`<span class="motor">HEALTH</span> distillate missing — run system-health-scan.py`);
    }
  }
  const path = spike.pathway;
  for (let i = 0; i < path.length; i++) {
    const from = i === 0 ? path[0] : path[i - 1];
    const to = path[i];
    const isErr = injectError && i === path.length - 1;
    pushLocalEvent({ type: "synapse", from, to, status: isErr ? "error" : "ok", code: isErr ? "missing_edge" : null });
    (spike.tracts || []).forEach((tid) => pulseAlongTract(tid));
    await new Promise((r) => setTimeout(r, 220));
  }
  if (injectError) pushLocalEvent({ type: "error", code: "missing_edge", status: "error", tracts: spike.tracts });
  else
    pushLocalEvent({
      type: "ltp",
      tracts: spike.tracts,
      pathway: path,
      gain: neuroColumns.some((c) => c.userData.stage !== "mature") ? 1.4 : 1.0,
      status: "ok",
    });
}

/** Apply live-activity.json — standing agents light their tracts */
function applyLiveFeed(feed) {
  liveFeed = feed;
  if (liveChip) {
    liveChip.textContent = `${feed.firing_count || 0} agents`;
    liveChip.classList.add("on");
  }
  (feed.firing || []).forEach((f) => {
    agentActivity[f.neuron] = Math.max(agentActivity[f.neuron] || 0, f.intensity || 0.4);
    if (f.area) {
      areaActivity[f.area] = Math.max(areaActivity[f.area] || 0, f.intensity || 0.4);
      setAreaLit(f.area, (f.intensity || 0) > 0.55 ? "lit" : "feedback");
    }
    (f.tracts || []).forEach((tid) => {
      setTractGlow(tid, (f.intensity || 0.4) * 0.85);
      if ((f.intensity || 0) > 0.6 && Math.random() < 0.35) pulseAlongTract(tid);
    });
  });
  renderAgents();
  renderWeights();
}

async function pollLiveActivity() {
  try {
    const r = await fetch(repoUrl("../../vault/10-Mesh-Distillates/live-activity.json", `t=${Date.now()}`)).then((x) => x.json());
    applyLiveFeed(r);
  } catch (_) {
    /* offline */
  }
}

function persistWeights() {
  // Best-effort: browsers can't write to vault; stash in localStorage + log
  try {
    localStorage.setItem(
      "cam.tractWeights",
      JSON.stringify({ weights, myelination, at: Date.now() })
    );
  } catch (_) {
    /* private mode */
  }
}

function setCameraView(mode) {
  brain.rotation.z = 0;
  applyFsCameraUp(camera, controls);
  // FreeSurfer axes: X=R+, Y=A+, Z=S+
  if (mode === "coronal") {
    // from anterior
    camera.position.set(0.15, 6.4, 0.85);
    controls.target.set(0, 0.1, 0.1);
  } else if (mode === "axial") {
    camera.up.set(0, 1, 0);
    camera.position.set(0.1, 0.2, 6.8);
    controls.target.set(0, 0.1, 0.05);
  } else if (mode === "sagittal") {
    // from right (language lateral)
    camera.position.set(6.2, 0.35, 0.9);
    controls.target.set(-0.4, 0.15, 0.1);
  }
  controls.update();
  log(`<span class="center">VIEW</span> ${mode}`);
}

function renderControls() {
  const groups = [
    { title: "Tasks", ids: ["sense.chat.aaron", "sense.language.af", "sense.dual.ventral", "sense.swiftguide.map", "sense.audio.transcript", "sense.careers.listing", "sense.vision.detection", "sense.memory.fornix", "health.scan"] },
  ];
  groups.forEach((g) => {
    const lab = document.createElement("div");
    lab.className = "ctrl-group";
    lab.textContent = g.title;
    controlsEl.appendChild(lab);
    g.ids.forEach((id) => {
      const s = SPIKES.find((x) => x.id === id);
      if (!s) return;
      const b = document.createElement("button");
      b.textContent = s.label;
      if (s.gold) b.className = "gold";
      b.addEventListener("click", () => fireSpike(s, false));
      controlsEl.appendChild(b);
    });
  });

  const sysLab = document.createElement("div");
  sysLab.className = "ctrl-group";
  sysLab.textContent = "Systems";
  controlsEl.appendChild(sysLab);
  ["arcuate_language", "anterior_ventral", "posterior_ventral", "cingulum_system", "commissural"].forEach((sys) => {
    const b = document.createElement("button");
    b.textContent = sys.replace(/_/g, " ");
    b.addEventListener("click", () => highlightSystem(sys));
    controlsEl.appendChild(b);
  });

  const util = document.createElement("div");
  util.className = "ctrl-group";
  util.textContent = "Utility";
  controlsEl.appendChild(util);

  const err = document.createElement("button");
  err.textContent = "Inject tract error";
  err.className = "danger";
  err.addEventListener("click", () => fireSpike(SPIKES[0], true));
  controlsEl.appendChild(err);

  const neuro = document.createElement("button");
  neuro.textContent = "Neurogenesis";
  neuro.className = "gold";
  neuro.addEventListener("click", () => {
    pushLocalEvent({ type: "neurogenesis", column: `neuron.mtl_new_${neuroColumns.length + 1}`, area: "area.mtl", stage: "immature", status: "ok" });
  });
  controlsEl.appendChild(neuro);

  const kill = document.createElement("button");
  kill.textContent = "Kill switch";
  kill.className = "danger";
  kill.addEventListener("click", () => pushLocalEvent({ type: "error", code: "kill", status: "error" }));
  controlsEl.appendChild(kill);

  const reset = document.createElement("button");
  reset.textContent = "Reset tape";
  reset.addEventListener("click", () => {
    events = [];
    scrub.max = "0";
    highlightedSystem = null;
    seek(0);
    log(`<span class="center">RESET</span> plasticity tape cleared`);
  });
  controlsEl.appendChild(reset);

  document.getElementById("view-coronal")?.addEventListener("click", () => setCameraView("coronal"));
  document.getElementById("view-axial")?.addEventListener("click", () => setCameraView("axial"));
  document.getElementById("view-sagittal")?.addEventListener("click", () => setCameraView("sagittal"));
  document.getElementById("view-lod")?.addEventListener("click", () => {
    lodHigh = !lodHigh;
    buildAmbientConnectome(lodHigh ? 700 : 220);
    log(`<span class="center">LOD</span> ${lodHigh ? "high" : "low"} ambient fibers`);
  });

  let glassHigh = true;
  const glassBtn = document.getElementById("view-glass");
  glassBtn?.addEventListener("click", () => {
    if (!cortexApi?.setTranslucency) return;
    glassHigh = !glassHigh;
    cortexApi.setTranslucency(glassHigh ? 0.82 : 0.28);
    glassBtn.classList.toggle("on", glassHigh);
    log(`<span class="center">GLASS</span> shell ${glassHigh ? "near-clear" : "solid"}`);
  });
}

document.getElementById("btn-play").addEventListener("click", () => {
  playing = !playing;
  document.getElementById("btn-play").textContent = playing ? "⏸" : "▶";
});
document.getElementById("btn-rew").addEventListener("click", () => {
  playing = false;
  seek(cursor - 1);
});
document.getElementById("btn-fwd").addEventListener("click", () => {
  playing = false;
  seek(cursor + 1);
});
scrub.addEventListener("input", () => {
  playing = false;
  seek(Number(scrub.value));
});

async function loadSeed() {
  try {
    const [w, t, c, n, h, live] = await Promise.all([
      fetch(repoUrl("../../vault/10-Mesh-Distillates/tract-weights.json")).then((r) => r.json()).catch(() => ({})),
      fetch(repoUrl("../../vault/10-Mesh-Distillates/plasticity-timeline.json")).then((r) => r.json()).catch(() => ({})),
      fetch(repoUrl("../../vault/10-Mesh-Distillates/neurogenesis-columns.json")).then((r) => r.json()).catch(() => ({})),
      fetch(repoUrl("../../config/connectome/neurons.json")).then((r) => r.json()),
      fetch(repoUrl("../../vault/10-Mesh-Distillates/system-health.json")).then((r) => r.json()).catch(() => null),
      fetch(repoUrl("../../vault/10-Mesh-Distillates/live-activity.json")).then((r) => r.json()).catch(() => null),
    ]);
    catalogNeurons = n.neurons || [];
    if (h?.checks) {
      h.checks.forEach((c0) => {
        healthStatus[c0.neuron] = c0.status;
      });
      log(`<span class="center">HEALTH</span> overall=${h.overall}`);
    }
    log(`<span class="center">DTI</span> ${TRACTS.length} fasciculi · anatomical cortex · live agents`);
    try {
      const cached = JSON.parse(localStorage.getItem("cam.tractWeights") || "null");
      if (cached?.weights) weights = { ...weights, ...cached.weights };
      if (cached?.myelination) myelination = { ...myelination, ...cached.myelination };
    } catch (_) {
      /* ignore */
    }
    if (w.weights) weights = { ...weights, ...w.weights };
    if (t.events?.length) {
      events = t.events;
      scrub.max = String(events.length - 1);
      seek(events.length - 1);
      log(`<span class="center">LOADED</span> ${events.length} tape events`);
    } else refreshTracts();
    (c.columns || []).forEach((col) => spawnNeuroColumn(col.id, col.label || "immature"));
    if (live) applyLiveFeed(live);
  } catch (e) {
    log(`<span class="center">SEED</span> ${e.message || "offline"}`);
    refreshTracts();
  }
}

renderControls();
loadSeed();
setInterval(pollLiveActivity, 2500);

let lastPlay = 0;
let lastDecay = performance.now();
let viewMode = 0; // cycle coronal / axial / sagittal-ish on soft auto

function animate(now) {
  requestAnimationFrame(animate);
  const dt = Math.min(0.05, (now - lastDecay) / 1000);
  lastDecay = now;
  controls.update();
  brain.rotation.z += autoSim ? 0.0009 : 0.0003;
  decayActivity(dt);

  if (playing && events.length && now - lastPlay > 450) {
    lastPlay = now;
    if (cursor < events.length - 1) seek(cursor + 1);
    else {
      playing = false;
      document.getElementById("btn-play").textContent = "▶";
    }
  }
  neuroColumns.forEach((m, i) => {
    m.position.y = areaById["area.mtl"].p[1] + 0.2 + Math.sin(now * 0.004 + i) * 0.04;
  });
  for (let i = fiberPulses.length - 1; i >= 0; i--) {
    const p = fiberPulses[i];
    p.userData.u += (p.userData.speed || 0.5) * dt;
    if (p.userData.u >= 1) {
      brain.remove(p);
      fiberPulses.splice(i, 1);
      continue;
    }
    p.position.copy(p.userData.curve.getPoint(p.userData.u));
  }
  // Soft area pulse from agent activity
  AREAS.forEach((a) => {
    const m = areaMeshes[a.id];
    if (!m) return;
    const act = areaActivity[a.id] || 0;
    if (act > 0.05) {
      const s = 1 + Math.sin(now * 0.008) * 0.08 * act;
      m.scale.setScalar(s);
    }
  });

  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}
requestAnimationFrame(animate);

log(`<span class="center">READY</span> DTI tractography · live agents · RGB fibers · orbit`);
