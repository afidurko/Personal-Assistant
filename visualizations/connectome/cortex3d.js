/* Cam 3D human brain — filled with columns, health neurons, orbit + rewind */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";

/** Approximate lateral coordinates on a human-ish cerebrum (x right, y up, z forward) */
const AREAS = [
  { id: "area.dlpfc", label: "DLPFC", ba: "BA9/46", p: [-1.35, 1.15, 0.85], r: 0.34, lobe: "frontal" },
  { id: "area.apfc", label: "aPFC", ba: "BA10", p: [-1.95, 1.05, 0.55], r: 0.26, lobe: "frontal" },
  { id: "area.ofc", label: "OFC", ba: "BA11", p: [-1.7, 0.15, 1.05], r: 0.22, lobe: "frontal" },
  { id: "area.broca", label: "Broca", ba: "BA44/45", p: [-1.15, 0.35, 1.25], r: 0.24, lobe: "frontal" },
  { id: "area.premotor", label: "PM/SMA", ba: "BA6", p: [-0.45, 1.2, 0.95], r: 0.18, lobe: "frontal" },
  { id: "area.motor", label: "M1", ba: "BA4", p: [0.05, 1.25, 0.8], r: 0.2, lobe: "frontal" },
  { id: "area.parietal", label: "Parietal", ba: "BA5/7", p: [0.95, 1.3, 0.25], r: 0.28, lobe: "parietal" },
  { id: "area.wernicke", label: "Wernicke+", ba: "BA22+", p: [1.05, 0.35, 1.05], r: 0.26, lobe: "temporal" },
  { id: "area.temporal", label: "Temporal", ba: "BA20/21", p: [0.55, -0.55, 1.35], r: 0.3, lobe: "temporal" },
  { id: "area.auditory", label: "Auditory", ba: "BA41/42", p: [0.15, -0.25, 1.2], r: 0.18, lobe: "temporal" },
  { id: "area.visual", label: "Visual", ba: "BA17–19", p: [0.15, 0.4, -1.45], r: 0.3, lobe: "occipital" },
  { id: "area.mtl", label: "MTL", ba: "memory", p: [0.35, -0.85, 0.45], r: 0.26, lobe: "limbic" },
  { id: "area.cingulate", label: "ACC", ba: "BA24/32", p: [-0.15, 1.45, 0.15], r: 0.22, lobe: "limbic" },
];

const TRACTS = [
  { id: "tract.arcuate", a: "area.wernicke", b: "area.broca" },
  { id: "tract.slf", a: "area.parietal", b: "area.dlpfc" },
  { id: "tract.uncinate", a: "area.ofc", b: "area.temporal" },
  { id: "tract.cingulum", a: "area.cingulate", b: "area.mtl" },
  { id: "tract.cingulum2", a: "area.mtl", b: "area.dlpfc", alias: "tract.cingulum" },
  { id: "tract.ilf", a: "area.visual", b: "area.temporal" },
  { id: "tract.ifof", a: "area.visual", b: "area.apfc" },
  { id: "tract.corticospinal", a: "area.premotor", b: "area.motor" },
];

const SPIKES = [
  { id: "sense.chat.aaron", label: "Aaron task", pathway: ["area.wernicke", "area.temporal", "area.mtl"], tracts: ["tract.arcuate", "tract.cingulum", "tract.cingulum2"], gold: true },
  { id: "sense.swiftguide.map", label: "SwiftGuide", pathway: ["area.apfc", "area.mtl"], tracts: ["tract.ifof", "tract.cingulum"], gold: true },
  { id: "sense.audio.transcript", label: "Speak/hear", pathway: ["area.auditory", "area.broca", "area.motor"], tracts: ["tract.arcuate", "tract.corticospinal"] },
  { id: "sense.careers.listing", label: "Jobs", pathway: ["area.temporal", "area.ofc"], tracts: ["tract.uncinate"] },
  { id: "sense.vision.detection", label: "Vision", pathway: ["area.visual", "area.temporal", "area.mtl"], tracts: ["tract.ilf", "tract.cingulum"] },
  { id: "health.scan", label: "Health scan", pathway: ["area.cingulate", "area.parietal", "area.dlpfc", "area.mtl"], tracts: ["tract.cingulum", "tract.cingulum2", "tract.slf"], gold: true, health: true },
];

const HEALTH_COLORS = {
  healthy: 0x5fd4c4,
  idle: 0x8a9a92,
  warning: 0xd4a84b,
  critical: 0xe07a5f,
};

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

let weights = Object.fromEntries(TRACTS.map((t) => [t.alias || t.id, 0.55]));
let events = [];
let cursor = 0;
let playing = false;
let killed = false;
let neuroColumns = [];
let neuronPoints = [];
let catalogNeurons = [];
let errorCount = 0;
let healthStatus = {};

const areaMeshes = {};
const tractMeshes = {};

function log(html) {
  const d = document.createElement("div");
  d.className = "entry";
  d.innerHTML = html;
  logEl.prepend(d);
}

function colorForWeight(w, errored = false) {
  if (errored) return new THREE.Color("#e07a5f");
  if (w < 0.2) return new THREE.Color("#5a5040");
  if (w > 0.75) return new THREE.Color("#5fd4c4");
  return new THREE.Color("#c4a574");
}

const viewport = document.getElementById("viewport");
const canvas = document.getElementById("c");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(0x0b1014, 1);

const labelRenderer = new CSS2DRenderer();
labelRenderer.domElement.style.position = "absolute";
labelRenderer.domElement.style.inset = "0";
labelRenderer.domElement.style.pointerEvents = "none";
viewport.appendChild(labelRenderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x0b1014, 0.028);

const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 100);
camera.position.set(5.4, 2.2, 4.6);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.target.set(0.1, 0.35, 0.35);
controls.minDistance = 3;
controls.maxDistance = 14;

scene.add(new THREE.AmbientLight(0xcbb89a, 0.5));
const key = new THREE.DirectionalLight(0x9fd9cf, 0.9);
key.position.set(4, 6, 3);
scene.add(key);
const rim = new THREE.DirectionalLight(0xe07a5f, 0.22);
rim.position.set(-5, 1, -3);
scene.add(rim);

const brain = new THREE.Group();
scene.add(brain);

function cortexMat(opacity = 0.55) {
  return new THREE.MeshStandardMaterial({
    color: 0xd4b8a0,
    roughness: 0.72,
    metalness: 0.05,
    transparent: true,
    opacity,
  });
}

function addEllipsoid(pos, scale, opacity = 0.5) {
  const g = new THREE.SphereGeometry(1, 40, 28);
  g.scale(...scale);
  const m = new THREE.Mesh(g, cortexMat(opacity));
  m.position.set(...pos);
  brain.add(m);
  return m;
}

/** Human brain built from lobe masses (not a sphere) */
function buildHumanBrain() {
  // Hemispheres — slightly flattened ovals like a real cerebrum
  addEllipsoid([-0.58, 0.5, 0.12], [1.42, 1.0, 1.62], 0.26);
  addEllipsoid([0.58, 0.5, 0.12], [1.42, 1.0, 1.62], 0.26);
  // Frontal poles (more pointed)
  addEllipsoid([-1.65, 0.48, 0.95], [0.9, 0.72, 0.78], 0.34);
  addEllipsoid([1.65, 0.48, 0.95], [0.9, 0.72, 0.78], 0.34);
  addEllipsoid([-0.15, 0.65, 1.25], [0.5, 0.4, 0.38], 0.22);
  // Temporal lobes hang lower + forward
  addEllipsoid([-1.05, -0.65, 1.05], [0.75, 0.58, 0.9], 0.38);
  addEllipsoid([1.05, -0.65, 1.05], [0.75, 0.58, 0.9], 0.38);
  addEllipsoid([-1.35, -0.95, 0.55], [0.4, 0.32, 0.45], 0.3);
  addEllipsoid([1.35, -0.95, 0.55], [0.4, 0.32, 0.45], 0.3);
  // Occipital bulge
  addEllipsoid([0.05, 0.35, -1.35], [0.95, 0.75, 0.55], 0.3);
  addEllipsoid([-0.85, 0.3, -1.05], [0.55, 0.55, 0.5], 0.28);
  addEllipsoid([0.85, 0.3, -1.05], [0.55, 0.55, 0.5], 0.28);
  // Parietal crown
  addEllipsoid([0.0, 1.35, -0.05], [1.15, 0.42, 1.0], 0.24);
  // Insula / medial hint
  addEllipsoid([0.0, 0.15, 0.35], [0.35, 0.55, 0.7], 0.18);
  // Cerebellum (two lobes + vermis)
  addEllipsoid([0.55, -0.95, -0.95], [0.7, 0.45, 0.5], 0.42);
  addEllipsoid([-0.55, -0.95, -0.95], [0.7, 0.45, 0.5], 0.42);
  addEllipsoid([0.0, -0.85, -1.05], [0.35, 0.35, 0.4], 0.38);
  // Brainstem + pons
  const pons = new THREE.Mesh(
    new THREE.SphereGeometry(0.28, 16, 12),
    new THREE.MeshStandardMaterial({ color: 0xb89a86, roughness: 0.85, transparent: true, opacity: 0.55 })
  );
  pons.position.set(0.0, -1.15, -0.35);
  pons.scale.set(1.1, 0.7, 1.2);
  brain.add(pons);
  const stem = new THREE.Mesh(
    new THREE.CylinderGeometry(0.14, 0.2, 1.0, 12),
    new THREE.MeshStandardMaterial({ color: 0xb89a86, roughness: 0.8, transparent: true, opacity: 0.55 })
  );
  stem.position.set(0.0, -1.55, -0.15);
  stem.rotation.x = 0.28;
  brain.add(stem);

  // Soft gyral ridges (read as folds, not cards)
  for (let i = 0; i < 14; i++) {
    const ang = (i / 14) * Math.PI * 2;
    const ridge = new THREE.Mesh(
      new THREE.TorusGeometry(1.55 + (i % 3) * 0.08, 0.035, 6, 48, Math.PI * 0.55),
      new THREE.MeshBasicMaterial({ color: 0xc9b09a, transparent: true, opacity: 0.12 })
    );
    ridge.position.set(Math.cos(ang) * 0.15, 0.55 + Math.sin(i) * 0.15, Math.sin(ang) * 0.1);
    ridge.rotation.set(0.4 + i * 0.05, ang, 0.2);
    brain.add(ridge);
  }

  // Soft outer silhouette wire for read
  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(2.55, 40, 28),
    new THREE.MeshBasicMaterial({ color: 0xe6d5b8, wireframe: true, transparent: true, opacity: 0.04 })
  );
  shell.scale.set(1.35, 0.95, 1.2);
  shell.position.set(0.0, 0.15, 0.05);
  brain.add(shell);

  // Longitudinal fissure hint
  const fissure = new THREE.Mesh(
    new THREE.BoxGeometry(0.05, 1.9, 2.6),
    new THREE.MeshBasicMaterial({ color: 0x0b1014, transparent: true, opacity: 0.4 })
  );
  fissure.position.set(0, 0.5, 0.05);
  brain.add(fissure);
}

buildHumanBrain();

function makeLabel(text) {
  const div = document.createElement("div");
  div.className = "label3d";
  div.textContent = text;
  return new CSS2DObject(div);
}

AREAS.forEach((a) => {
  const mat = new THREE.MeshStandardMaterial({
    color: 0x2f4a42,
    emissive: 0x0a1814,
    roughness: 0.5,
    metalness: 0.12,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(a.r, 22, 16), mat);
  mesh.position.set(...a.p);
  brain.add(mesh);
  const lab = makeLabel(`${a.label}\n${a.ba}`);
  lab.position.set(a.p[0], a.p[1] + a.r + 0.14, a.p[2]);
  brain.add(lab);
  areaMeshes[a.id] = mesh;
});

function curveBetween(a, b) {
  const A = new THREE.Vector3(...areaById[a].p);
  const B = new THREE.Vector3(...areaById[b].p);
  const mid = A.clone().add(B).multiplyScalar(0.5);
  mid.y += 0.45;
  return new THREE.QuadraticBezierCurve3(A, mid, B);
}

TRACTS.forEach((t) => {
  const curve = curveBetween(t.a, t.b);
  const w = weights[t.alias || t.id] || 0.55;
  const tube = new THREE.Mesh(
    new THREE.TubeGeometry(curve, 40, 0.018 + w * 0.045, 8, false),
    new THREE.MeshStandardMaterial({
      color: colorForWeight(w),
      emissive: colorForWeight(w),
      emissiveIntensity: 0.18,
      transparent: true,
      opacity: 0.88,
    })
  );
  tube.userData = { id: t.id, alias: t.alias || t.id, curve };
  brain.add(tube);
  tractMeshes[t.id] = tube;
});

/** Fill cortex with catalog neurons + ambient interneurons */
function fillNeurons(catalog = []) {
  neuronPoints.forEach((m) => brain.remove(m));
  neuronPoints = [];
  const positions = [];
  const colors = [];
  const meta = [];

  function addDot(p, color, size, metaRow) {
    positions.push(p.x, p.y, p.z);
    const c = new THREE.Color(color);
    colors.push(c.r, c.g, c.b);
    meta.push(metaRow);
  }

  // Catalog neurons clustered on their area
  catalog.forEach((n, i) => {
    const area = areaById[n.area];
    if (!area) return;
    const ang = (i * 2.4) + (n.id.length % 7);
    const rad = area.r + 0.12 + (i % 5) * 0.04;
    const p = new THREE.Vector3(
      area.p[0] + Math.cos(ang) * rad,
      area.p[1] + Math.sin(ang * 0.7) * rad * 0.6,
      area.p[2] + Math.sin(ang) * rad
    );
    const isHealth = /health|vitals|drift|vuln|arch_scan|submodule|hygiene|conductor|persist|tailscale|integration|improve|connectome_check/.test(n.id);
    const st = healthStatus[n.id];
    const col = st ? HEALTH_COLORS[st] || 0x5fd4c4 : isHealth ? 0xd4a84b : n.kind === "loop" ? 0xc4a574 : 0x5fd4c4;
    addDot(p, col, n.kind === "loop" ? 0.045 : 0.038, { id: n.id, area: n.area, kind: n.kind });
  });

  // Ambient filler neurons across brain volume (fill)
  for (let i = 0; i < 420; i++) {
    const u = Math.random() * Math.PI * 2;
    const v = Math.acos(2 * Math.random() - 1);
    const rr = 0.7 + Math.random() * 1.7;
    // deform into brainier envelope
    const x = Math.sin(v) * Math.cos(u) * rr * 1.25 + (Math.random() - 0.5) * 0.15;
    const y = Math.cos(v) * rr * 0.85 + 0.25 + (Math.random() - 0.5) * 0.1;
    const z = Math.sin(v) * Math.sin(u) * rr * 1.05 + 0.15;
    // prefer cortex shell
    if (y < -1.6) continue;
    addDot(new THREE.Vector3(x, y, z), 0x3d5a50, 0.02, { id: `ambient_${i}`, kind: "interneuron" });
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
  const mat = new THREE.PointsMaterial({
    size: 0.055,
    vertexColors: true,
    transparent: true,
    opacity: 0.92,
    depthWrite: false,
    sizeAttenuation: true,
  });
  const pts = new THREE.Points(geo, mat);
  pts.userData = { meta };
  brain.add(pts);
  neuronPoints.push(pts);
}

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
  if (!m) return;
  if (mode === "lit") {
    m.material.emissive.set("#5fd4c4");
    m.material.emissiveIntensity = 0.7;
  } else if (mode === "error") {
    m.material.emissive.set("#e07a5f");
    m.material.emissiveIntensity = 0.85;
  } else if (mode === "feedback") {
    m.material.emissive.set("#d4a84b");
    m.material.emissiveIntensity = 0.6;
  } else {
    m.material.emissive.set("#0a1814");
    m.material.emissiveIntensity = 0.2;
  }
}

function refreshTracts(errorIds = new Set()) {
  TRACTS.forEach((t) => {
    const mesh = tractMeshes[t.id];
    const key = t.alias || t.id;
    const w = weights[key] ?? 0.55;
    const errored = errorIds.has(t.id) || errorIds.has(key);
    const curve = mesh.userData.curve;
    mesh.geometry.dispose();
    mesh.geometry = new THREE.TubeGeometry(curve, 40, 0.014 + w * 0.055, 8, false);
    mesh.material.color.copy(colorForWeight(w, errored));
    mesh.material.emissive.copy(colorForWeight(w, errored));
    mesh.material.emissiveIntensity = errored ? 0.75 : 0.12 + w * 0.4;
    mesh.material.opacity = w < 0.15 ? 0.25 : 0.9;
  });
  renderWeights();
}

function renderWeights() {
  weightsEl.innerHTML = "";
  Object.entries(weights)
    .sort((a, b) => b[1] - a[1])
    .forEach(([id, w]) => {
      const row = document.createElement("div");
      row.className = "weight-row";
      row.innerHTML = `<span>${id.replace("tract.", "")}</span><i style="width:${Math.round(w * 100)}%"></i><em>${w.toFixed(2)}</em>`;
      weightsEl.appendChild(row);
    });
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
    });
    Object.keys(weights).forEach((tid) => {
      if (!(ev.tracts || []).includes(tid)) weights[tid] = Math.max(0.05, weights[tid] - 0.015);
    });
    (ev.pathway || []).filter((x) => x.startsWith("area.")).forEach((id) => setAreaLit(id, "feedback"));
    chipPlast.textContent = "LTP +";
    chipPlast.classList.add("on");
    log(`<span class="center">LTP</span> ${(ev.tracts || []).join(", ")}`);
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
    log(`<span class="center">HEALTH</span> ${ev.overall || ev.status} · ${(ev.neurons || []).length} neurons`);
    chipPlast.textContent = "health";
    chipPlast.classList.add("on");
  }
}

function spawnNeuroColumn(id, stage) {
  const mtl = areaById["area.mtl"];
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(stage === "mature" ? 0.09 : 0.065, 12, 10),
    new THREE.MeshStandardMaterial({
      color: stage === "mature" ? 0x5fd4c4 : 0xd4a84b,
      emissive: stage === "mature" ? 0x5fd4c4 : 0xd4a84b,
      emissiveIntensity: 0.95,
    })
  );
  const ang = Math.random() * Math.PI * 2;
  mesh.position.set(mtl.p[0] + Math.cos(ang) * 0.35, mtl.p[1] + 0.22, mtl.p[2] + Math.sin(ang) * 0.35);
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
  errorCount = 0;
  killed = false;
  chipKill.classList.remove("on");
  chipKill.textContent = "kill armed";
  chipErr.textContent = "errors: 0";
  chipErr.classList.remove("on");
  neuroColumns.splice(0).forEach((m) => brain.remove(m));
  clearLights();
  for (let i = 0; i <= cursor; i++) applyEvent(events[i]);
  refreshTracts();
}

function pushLocalEvent(ev) {
  events.push({ ...ev, t: events.length });
  scrub.max = String(Math.max(events.length - 1, 0));
  seek(events.length - 1);
}

async function fireSpike(spike, injectError = false) {
  if (killed) {
    log(`<span class="motor">BLOCKED</span> kill active`);
    return;
  }
  log(`<span class="in">IN</span> ${spike.id}`);
  clearLights();
  if (spike.health) {
    try {
      const r = await fetch("../../vault/10-Mesh-Distillates/system-health.json").then((x) => x.json());
      (r.checks || []).forEach((c) => {
        healthStatus[c.neuron] = c.status;
      });
      fillNeurons(catalogNeurons);
      pushLocalEvent({
        type: "health_scan",
        status: r.overall === "critical" ? "warn" : "ok",
        overall: r.overall,
        neurons: r.neurons_fired || [],
      });
      (spike.pathway || []).forEach((id) => setAreaLit(id, "lit"));
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
    await new Promise((r) => setTimeout(r, 260));
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

function renderControls() {
  SPIKES.forEach((s) => {
    const b = document.createElement("button");
    b.textContent = s.label;
    if (s.gold) b.className = "gold";
    b.addEventListener("click", () => fireSpike(s, false));
    controlsEl.appendChild(b);
  });
  const err = document.createElement("button");
  err.textContent = "Inject tract error";
  err.className = "danger";
  err.addEventListener("click", () => fireSpike(SPIKES[3], true));
  controlsEl.appendChild(err);

  const neuro = document.createElement("button");
  neuro.textContent = "Neurogenesis";
  neuro.className = "gold";
  neuro.addEventListener("click", () => {
    pushLocalEvent({
      type: "neurogenesis",
      column: `neuron.mtl_new_${neuroColumns.length + 1}`,
      area: "area.mtl",
      stage: "immature",
      status: "ok",
    });
  });
  controlsEl.appendChild(neuro);

  const mature = document.createElement("button");
  mature.textContent = "Mature columns";
  mature.addEventListener("click", () => {
    neuroColumns.forEach((m) => {
      m.userData.stage = "mature";
      m.material.color.set("#5fd4c4");
      m.material.emissive.set("#5fd4c4");
    });
    pushLocalEvent({ type: "neurogenesis_mature", stage: "mature", status: "ok" });
  });
  controlsEl.appendChild(mature);

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
    seek(0);
    log(`<span class="center">RESET</span> plasticity tape cleared`);
  });
  controlsEl.appendChild(reset);
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
    const [w, t, c, n, h] = await Promise.all([
      fetch("../../vault/10-Mesh-Distillates/tract-weights.json").then((r) => r.json()).catch(() => ({})),
      fetch("../../vault/10-Mesh-Distillates/plasticity-timeline.json").then((r) => r.json()).catch(() => ({})),
      fetch("../../vault/10-Mesh-Distillates/neurogenesis-columns.json").then((r) => r.json()).catch(() => ({})),
      fetch("../../config/connectome/neurons.json").then((r) => r.json()),
      fetch("../../vault/10-Mesh-Distillates/system-health.json").then((r) => r.json()).catch(() => null),
    ]);
    catalogNeurons = n.neurons || [];
    if (h?.checks) {
      h.checks.forEach((c0) => {
        healthStatus[c0.neuron] = c0.status;
      });
      log(`<span class="center">HEALTH</span> loaded overall=${h.overall}`);
    }
    fillNeurons(catalogNeurons);
    log(`<span class="center">NEURONS</span> ${catalogNeurons.length} catalog + ambient fill`);
    if (w.weights) weights = { ...weights, ...w.weights };
    if (t.events?.length) {
      events = t.events;
      scrub.max = String(events.length - 1);
      seek(events.length - 1);
      log(`<span class="center">LOADED</span> ${events.length} tape events`);
    } else refreshTracts();
    (c.columns || []).forEach((col) => spawnNeuroColumn(col.id, col.label || "immature"));
  } catch (e) {
    fillNeurons([]);
    log(`<span class="center">SEED</span> ${e.message || "offline"}`);
    refreshTracts();
  }
}

renderControls();
loadSeed();

let lastPlay = 0;
function animate(now) {
  requestAnimationFrame(animate);
  controls.update();
  brain.rotation.y += 0.0008;
  if (playing && events.length && now - lastPlay > 450) {
    lastPlay = now;
    if (cursor < events.length - 1) seek(cursor + 1);
    else {
      playing = false;
      document.getElementById("btn-play").textContent = "▶";
    }
  }
  neuroColumns.forEach((m, i) => {
    m.position.y = areaById["area.mtl"].p[1] + 0.22 + Math.sin(now * 0.004 + i) * 0.05;
  });
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}
requestAnimationFrame(animate);

log(`<span class="center">READY</span> human cortex · filled neurons · drag to orbit · scrub to rewind`);
