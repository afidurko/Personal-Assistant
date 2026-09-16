/* Cam 3D Brodmann cortex — orbit, rewindable plasticity tape, neurogenesis */
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DRenderer, CSS2DObject } from "three/addons/renderers/CSS2DRenderer.js";

const AREAS = [
  { id: "area.dlpfc", label: "DLPFC", ba: "BA9/46", p: [-1.2, 0.9, 0.6], r: 0.38 },
  { id: "area.apfc", label: "aPFC", ba: "BA10", p: [-1.8, 1.1, 0.2], r: 0.28 },
  { id: "area.ofc", label: "OFC", ba: "BA11", p: [-1.6, 0.2, 0.9], r: 0.24 },
  { id: "area.broca", label: "Broca", ba: "BA44/45", p: [-1.0, 0.15, 1.1], r: 0.26 },
  { id: "area.premotor", label: "PM/SMA", ba: "BA6", p: [-0.4, 0.7, 0.9], r: 0.2 },
  { id: "area.motor", label: "M1", ba: "BA4", p: [0.1, 0.75, 0.85], r: 0.22 },
  { id: "area.parietal", label: "Parietal", ba: "BA5/7", p: [0.9, 1.1, 0.3], r: 0.3 },
  { id: "area.wernicke", label: "Wernicke+", ba: "BA22+", p: [1.0, 0.25, 0.95], r: 0.28 },
  { id: "area.temporal", label: "Temporal", ba: "BA20/21", p: [0.5, -0.35, 1.15], r: 0.3 },
  { id: "area.auditory", label: "Auditory", ba: "BA41/42", p: [0.05, -0.55, 1.05], r: 0.2 },
  { id: "area.visual", label: "Visual", ba: "BA17–19", p: [1.9, 0.2, -0.2], r: 0.32 },
  { id: "area.mtl", label: "MTL", ba: "memory", p: [0.2, -0.95, 0.35], r: 0.28 },
  { id: "area.cingulate", label: "ACC", ba: "BA24/32", p: [-0.35, 1.35, 0.05], r: 0.24 },
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
  { id: "sense.vault.hit", label: "Vault", pathway: ["area.mtl", "area.dlpfc"], tracts: ["tract.cingulum2"] },
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

let weights = Object.fromEntries(TRACTS.map((t) => [t.alias || t.id, 0.55]));
let events = [];
let cursor = 0;
let playing = false;
let killed = false;
let neuroColumns = [];
let errorCount = 0;

const areaMeshes = {};
const tractMeshes = {};
const pulseSprites = [];

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

// --- Scene ---
const viewport = document.getElementById("viewport");
const canvas = document.getElementById("c");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setClearColor(0x0c1210, 1);

const labelRenderer = new CSS2DRenderer();
labelRenderer.domElement.style.position = "absolute";
labelRenderer.domElement.style.inset = "0";
labelRenderer.domElement.style.pointerEvents = "none";
viewport.appendChild(labelRenderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x0c1210, 0.035);

const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
camera.position.set(4.2, 2.4, 5.2);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.target.set(0, 0.2, 0.3);
controls.minDistance = 2.5;
controls.maxDistance = 12;

scene.add(new THREE.AmbientLight(0xb8a888, 0.55));
const key = new THREE.DirectionalLight(0x5fd4c4, 0.85);
key.position.set(3, 5, 2);
scene.add(key);
const fill = new THREE.DirectionalLight(0xe07a5f, 0.25);
fill.position.set(-4, -1, -2);
scene.add(fill);

const brain = new THREE.Group();
scene.add(brain);

// Brain shell
{
  const geo = new THREE.SphereGeometry(2.35, 48, 32);
  geo.scale(1.15, 0.92, 1.05);
  const mat = new THREE.MeshStandardMaterial({
    color: 0x1a2a24,
    transparent: true,
    opacity: 0.22,
    roughness: 0.85,
    metalness: 0.05,
    wireframe: false,
  });
  brain.add(new THREE.Mesh(geo, mat));
  brain.add(
    new THREE.Mesh(
      geo.clone(),
      new THREE.MeshBasicMaterial({ color: 0xe6d5b8, wireframe: true, transparent: true, opacity: 0.08 })
    )
  );
}

function makeLabel(text) {
  const div = document.createElement("div");
  div.className = "label3d";
  div.textContent = text;
  return new CSS2DObject(div);
}

AREAS.forEach((a) => {
  const mat = new THREE.MeshStandardMaterial({
    color: 0x2a4038,
    emissive: 0x0a1814,
    roughness: 0.55,
    metalness: 0.15,
  });
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(a.r, 24, 16), mat);
  mesh.position.set(...a.p);
  mesh.userData = { id: a.id };
  brain.add(mesh);
  const lab = makeLabel(`${a.label}\n${a.ba}`);
  lab.position.set(...a.p);
  lab.position.y += a.r + 0.12;
  brain.add(lab);
  areaMeshes[a.id] = mesh;
});

function curveBetween(a, b) {
  const A = new THREE.Vector3(...areaById[a].p);
  const B = new THREE.Vector3(...areaById[b].p);
  const mid = A.clone().add(B).multiplyScalar(0.5);
  mid.add(new THREE.Vector3(0, 0.55, 0));
  return new THREE.QuadraticBezierCurve3(A, mid, B);
}

TRACTS.forEach((t) => {
  const curve = curveBetween(t.a, t.b);
  const w = weights[t.alias || t.id] || 0.55;
  const tube = new THREE.Mesh(
    new THREE.TubeGeometry(curve, 32, 0.02 + w * 0.05, 8, false),
    new THREE.MeshStandardMaterial({
      color: colorForWeight(w),
      emissive: colorForWeight(w),
      emissiveIntensity: 0.15,
      transparent: true,
      opacity: 0.85,
    })
  );
  tube.userData = { id: t.id, alias: t.alias || t.id, curve };
  brain.add(tube);
  tractMeshes[t.id] = tube;
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
  if (!m) return;
  if (mode === "lit") {
    m.material.emissive.set("#5fd4c4");
    m.material.emissiveIntensity = 0.65;
  } else if (mode === "error") {
    m.material.emissive.set("#e07a5f");
    m.material.emissiveIntensity = 0.8;
  } else if (mode === "feedback") {
    m.material.emissive.set("#d4a84b");
    m.material.emissiveIntensity = 0.55;
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
    mesh.geometry = new THREE.TubeGeometry(curve, 32, 0.015 + w * 0.06, 8, false);
    mesh.material.color.copy(colorForWeight(w, errored));
    mesh.material.emissive.copy(colorForWeight(w, errored));
    mesh.material.emissiveIntensity = errored ? 0.7 : 0.12 + w * 0.4;
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
  pulseSprites.splice(0).forEach((p) => scene.remove(p));
}

function applyEvent(ev, highlightErrors = true) {
  if (!ev) return;
  if (ev.type === "synapse") {
    setAreaLit(ev.from, ev.status === "error" ? "error" : "lit");
    setAreaLit(ev.to, ev.status === "error" ? "error" : "lit");
    if (ev.status === "error" && highlightErrors) {
      errorCount += 1;
      chipErr.textContent = `errors: ${errorCount}`;
      chipErr.classList.add("on");
      log(`<span class="motor">ERR</span> missing_edge ${ev.from} → ${ev.to}`);
    }
  } else if (ev.type === "ltp") {
    (ev.tracts || []).forEach((tid) => {
      weights[tid] = Math.min(1, (weights[tid] || 0.55) + 0.08 * (ev.gain || 1));
    });
    // heterosynaptic mild LTD
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
      log(`<span class="motor">KILL</span> LTD on all tracts`);
    } else if (ev.code === "qa_veto") {
      setAreaLit("area.cingulate", "error");
      log(`<span class="motor">QA VETO</span> ACC hold`);
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
  }
}

function spawnNeuroColumn(id, stage) {
  const mtl = areaById["area.mtl"];
  const geo = new THREE.SphereGeometry(stage === "mature" ? 0.1 : 0.07, 12, 10);
  const mat = new THREE.MeshStandardMaterial({
    color: stage === "mature" ? 0x5fd4c4 : 0xd4a84b,
    emissive: stage === "mature" ? 0x5fd4c4 : 0xd4a84b,
    emissiveIntensity: 0.9,
  });
  const mesh = new THREE.Mesh(geo, mat);
  const ang = Math.random() * Math.PI * 2;
  mesh.position.set(mtl.p[0] + Math.cos(ang) * 0.4, mtl.p[1] + 0.25, mtl.p[2] + Math.sin(ang) * 0.4);
  mesh.userData = { id, neuro: true, stage };
  brain.add(mesh);
  neuroColumns.push(mesh);
  setAreaLit("area.mtl", "feedback");
}

function seek(t) {
  cursor = Math.max(0, Math.min(t, Math.max(events.length - 1, 0)));
  scrub.value = String(cursor);
  chipT.textContent = `t=${cursor}/${Math.max(events.length - 1, 0)}`;
  // rebuild state from start for accurate rewind
  weights = Object.fromEntries(TRACTS.map((tr) => [tr.alias || tr.id, 0.55]));
  errorCount = 0;
  killed = false;
  chipKill.classList.remove("on");
  chipKill.textContent = "kill armed";
  chipErr.textContent = "errors: 0";
  chipErr.classList.remove("on");
  neuroColumns.splice(0).forEach((m) => brain.remove(m));
  clearLights();
  for (let i = 0; i <= cursor; i++) applyEvent(events[i], true);
  refreshTracts();
}

function pushLocalEvent(ev) {
  events.push({ ...ev, t: events.length });
  scrub.max = String(Math.max(events.length - 1, 0));
  seek(events.length - 1);
}

async function fireSpike(spike, injectError = false) {
  if (killed && spike.id !== "__unkill__") {
    log(`<span class="motor">BLOCKED</span> kill active`);
    return;
  }
  log(`<span class="in">IN</span> ${spike.id}`);
  clearLights();
  const path = spike.pathway;
  for (let i = 0; i < path.length; i++) {
    const from = i === 0 ? path[0] : path[i - 1];
    const to = path[i];
    const isErr = injectError && i === path.length - 1;
    pushLocalEvent({
      type: "synapse",
      from,
      to,
      status: isErr ? "error" : "ok",
      code: isErr ? "missing_edge" : null,
    });
    await new Promise((r) => setTimeout(r, 280));
  }
  if (injectError) {
    pushLocalEvent({ type: "error", code: "missing_edge", status: "error", tracts: spike.tracts });
  } else {
    pushLocalEvent({
      type: "ltp",
      tracts: spike.tracts,
      pathway: path,
      gain: neuroColumns.some((c) => c.userData.stage !== "mature") ? 1.4 : 1.0,
      status: "ok",
    });
  }
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
  kill.addEventListener("click", () => {
    pushLocalEvent({ type: "error", code: "kill", status: "error" });
  });
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
    const [w, t, c] = await Promise.all([
      fetch("../../vault/10-Mesh-Distillates/tract-weights.json").then((r) => r.json()),
      fetch("../../vault/10-Mesh-Distillates/plasticity-timeline.json").then((r) => r.json()),
      fetch("../../vault/10-Mesh-Distillates/neurogenesis-columns.json").then((r) => r.json()),
    ]);
    if (w.weights) weights = { ...weights, ...w.weights };
    if (t.events?.length) {
      events = t.events;
      scrub.max = String(events.length - 1);
      seek(events.length - 1);
      log(`<span class="center">LOADED</span> ${events.length} tape events from mesh distillates`);
    }
    (c.columns || []).forEach((col) => spawnNeuroColumn(col.id, col.label || "immature"));
  } catch (e) {
    log(`<span class="center">SEED</span> starting empty tape (${e.message || "offline"})`);
    refreshTracts();
  }
}

renderControls();
loadSeed();

let lastPlay = 0;
function animate(now) {
  requestAnimationFrame(animate);
  controls.update();
  brain.rotation.y += 0.0012;
  if (playing && events.length && now - lastPlay > 450) {
    lastPlay = now;
    if (cursor < events.length - 1) seek(cursor + 1);
    else {
      playing = false;
      document.getElementById("btn-play").textContent = "▶";
    }
  }
  neuroColumns.forEach((m, i) => {
    m.position.y = areaById["area.mtl"].p[1] + 0.25 + Math.sin(now * 0.004 + i) * 0.05;
  });
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}
requestAnimationFrame(animate);

log(`<span class="center">READY</span> 3D cortex · drag to spin · scrub to rewind tract errors`);
