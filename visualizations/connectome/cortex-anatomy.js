/* Anatomical Cam cortex shell — near-glass FreeSurfer DK parcels → area.* heat */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const LOBE_OF = {
  "area.dlpfc": "frontal",
  "area.apfc": "frontal",
  "area.ofc": "frontal",
  "area.broca": "frontal",
  "area.premotor": "frontal",
  "area.motor": "frontal",
  "area.parietal": "parietal",
  "area.wernicke": "temporoparietal",
  "area.temporal": "temporal",
  "area.auditory": "temporal",
  "area.visual": "occipital",
  "area.cingulate": "medial",
  "area.mtl": "medial_temporal",
  "area.mtl.hippocampus": "medial_temporal",
  "fill.insula": "fill",
  "deep.amygdala": "deep",
  "deep.thalamus": "deep",
  "deep.striatum": "deep",
  "deep.cerebellum": "deep",
  "deep.brainstem": "deep",
  "deep.callosum": "deep",
};

/** Soft lobe tints — pale so the glass shell stays readable */
const DEFAULT_LOBE_COLORS = {
  frontal: "#9ecfc4",
  parietal: "#9ab8d4",
  temporal: "#d4c49a",
  occipital: "#a8c49a",
  temporoparietal: "#b0c8d4",
  limbic: "#d4b0a0",
  medial: "#c8a0b0",
  medial_temporal: "#c8b090",
  deep: "#a0b0ac",
  fill: "#9aada8",
};

/** Resting glass — translucent but still a brain silhouette */
const GLASS = {
  cortexOpacity: 0.26,
  cortexTransmission: 0.78,
  deepOpacity: 0.14,
  deepTransmission: 0.88,
  litOpacityBoost: 0.28,
  roughness: 0.22,
  thickness: 1.1,
  ior: 1.3,
};

/** Map mesh name → Cam area activity key */
export function activityKeyForMesh(name) {
  if (!name) return null;
  if (name === "area.mtl.hippocampus") return "area.mtl";
  if (name.startsWith("area.")) return name;
  return null;
}

export function applyFsCameraUp(camera, controls) {
  // GLB is FreeSurfer-like: X=R+, Y=A+, Z=S+
  camera.up.set(0, 0, 1);
  if (controls) {
    controls.target.set(0, 0.15, 0.05);
    controls.update();
  }
}

/** Install a dim room env so MeshPhysical transmission refracts something */
export function installGlassEnvironment(renderer, scene) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = env;
  // environmentIntensity lands in newer Three; soft-fail on r160
  if ("environmentIntensity" in scene) scene.environmentIntensity = 0.45;
  pmrem.dispose();
  return env;
}

function makeGlassMaterial(base, deep) {
  return new THREE.MeshPhysicalMaterial({
    color: base.clone().multiplyScalar(deep ? 0.9 : 1.08),
    emissive: new THREE.Color(0x1a3028),
    emissiveIntensity: deep ? 0.02 : 0.06,
    roughness: GLASS.roughness,
    metalness: 0,
    transmission: deep ? GLASS.deepTransmission : GLASS.cortexTransmission,
    thickness: deep ? 0.55 : GLASS.thickness,
    ior: GLASS.ior,
    transparent: true,
    opacity: deep ? GLASS.deepOpacity : GLASS.cortexOpacity,
    depthWrite: false,
    side: THREE.DoubleSide,
    envMapIntensity: 0.55,
    clearcoat: 0.35,
    clearcoatRoughness: 0.35,
    attenuationColor: base.clone(),
    attenuationDistance: deep ? 2.5 : 1.6,
  });
}

/**
 * Load cam-cortex.glb into `parent`, mirror left parcels, return API.
 */
export async function loadCamCortex(parent, opts = {}) {
  const url = opts.url || "./assets/cam-cortex.glb";
  const lobeColors = { ...DEFAULT_LOBE_COLORS, ...(opts.lobeColors || {}) };
  const loader = new GLTFLoader();
  const gltf = await loader.loadAsync(url);

  const root = new THREE.Group();
  root.name = "cam-cortex-shell";
  root.renderOrder = 2;
  parent.add(root);

  const parcels = {};
  const centroids = {};

  gltf.scene.traverse((obj) => {
    if (!obj.isMesh) return;
    const name = obj.name || obj.parent?.name;
    if (!name) return;

    const lobe = LOBE_OF[name] || "fill";
    const deep = name.startsWith("deep.");
    const base = new THREE.Color(lobeColors[lobe] || lobeColors.fill);
    const mat = makeGlassMaterial(base, deep);
    obj.material = mat;
    obj.castShadow = false;
    obj.receiveShadow = false;
    obj.renderOrder = deep ? 1 : 2;

    const geo = obj.geometry;
    geo.computeBoundingBox();
    const c = new THREE.Vector3();
    geo.boundingBox.getCenter(c);
    centroids[name] = [c.x, c.y, c.z];

    const areaKey = activityKeyForMesh(name);
    const restOpacity = deep ? GLASS.deepOpacity : GLASS.cortexOpacity;
    parcels[name] = { mesh: obj, mat, base, areaKey, lobe, deep, restOpacity };

    const skipMirror = name === "deep.brainstem" || name === "deep.callosum";
    if (!skipMirror) {
      const mirror = obj.clone();
      mirror.material = makeGlassMaterial(base, deep);
      mirror.scale.x *= -1;
      mirror.name = `${name}__R`;
      mirror.renderOrder = obj.renderOrder;
      (obj.parent || gltf.scene).add(mirror);
      parcels[name].mirror = mirror;
      parcels[name].mirrorMat = mirror.material;
    }
  });

  root.add(gltf.scene);

  function applyMatState(mat, p, activity, mode) {
    const rest = p.restOpacity;
    const baseTx = p.deep ? GLASS.deepTransmission : GLASS.cortexTransmission;
    if (mode === "error") {
      mat.emissive.set("#ff5533");
      mat.emissiveIntensity = 1.15;
      mat.opacity = Math.min(0.78, rest + GLASS.litOpacityBoost + 0.12);
      mat.transmission = Math.max(0.4, baseTx - 0.3);
      mat.color.copy(p.base);
    } else if (mode === "feedback") {
      mat.emissive.set("#ffe066");
      mat.emissiveIntensity = 0.5 + activity * 0.85;
      mat.opacity = rest + GLASS.litOpacityBoost * (0.5 + activity * 0.5);
      mat.transmission = baseTx * (1 - activity * 0.25);
      mat.color.copy(p.base).lerp(new THREE.Color("#fff6d0"), activity * 0.3);
    } else if (mode === "lit" || activity > 0.05) {
      mat.emissive.set("#5fd4ff");
      mat.emissiveIntensity = 0.4 + activity * 1.2;
      mat.opacity = rest + GLASS.litOpacityBoost * activity;
      mat.transmission = baseTx * (1 - activity * 0.32);
      mat.color.copy(p.base).lerp(new THREE.Color("#e8fff8"), activity * 0.45);
    } else {
      mat.emissive.set("#1a3028");
      mat.emissiveIntensity = p.deep ? 0.02 : 0.06;
      mat.opacity = rest;
      mat.transmission = baseTx;
      mat.color.copy(p.base);
    }
  }

  function setParcelHeat(areaId, activity, mode = "idle") {
    const keys = Object.keys(parcels).filter((n) => {
      const k = parcels[n].areaKey;
      return k === areaId || n === areaId;
    });
    keys.forEach((n) => {
      const p = parcels[n];
      const mats = [p.mat, p.mirrorMat].filter(Boolean);
      mats.forEach((mat) => applyMatState(mat, p, activity, mode));
    });
  }

  function decayHeats(areaActivity) {
    Object.keys(areaActivity || {}).forEach((id) => {
      setParcelHeat(id, areaActivity[id] || 0, "idle");
    });
  }

  /** Global glass dial 0..1 (1 = near-clear shell that still holds silhouette) */
  function setTranslucency(amount = 0.85) {
    const t = Math.max(0, Math.min(1, amount));
    Object.values(parcels).forEach((p) => {
      const rest = p.deep
        ? THREE.MathUtils.lerp(0.32, 0.1, t)
        : THREE.MathUtils.lerp(0.55, 0.2, t);
      p.restOpacity = rest;
      const mats = [p.mat, p.mirrorMat].filter(Boolean);
      mats.forEach((mat) => {
        mat.opacity = rest;
        mat.transmission = THREE.MathUtils.lerp(0.35, 0.85, t);
        mat.emissiveIntensity = THREE.MathUtils.lerp(0.02, 0.07, t);
      });
    });
  }

  function pickArea(raycaster) {
    const meshes = [];
    Object.values(parcels).forEach((p) => {
      meshes.push(p.mesh);
      if (p.mirror) meshes.push(p.mirror);
    });
    const hits = raycaster.intersectObjects(meshes, false);
    if (!hits.length) return null;
    const n = hits[0].object.name.replace(/__R$/, "");
    return parcels[n]?.areaKey || (n.startsWith("area.") ? n : null);
  }

  function areaCentroids() {
    const out = { ...centroids };
    if (centroids["area.mtl"] && centroids["area.mtl.hippocampus"]) {
      const a = centroids["area.mtl"];
      const b = centroids["area.mtl.hippocampus"];
      out["area.mtl"] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2];
    }
    return out;
  }

  return {
    root,
    parcels,
    centroids: areaCentroids(),
    setParcelHeat,
    decayHeats,
    setTranslucency,
    pickArea,
    lobeColors,
    glass: GLASS,
  };
}
