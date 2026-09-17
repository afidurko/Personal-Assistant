/* Anatomical Cam cortex shell — FreeSurfer DK parcels → area.* heat */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

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

const DEFAULT_LOBE_COLORS = {
  frontal: "#3d9b8f",
  parietal: "#5a8fbf",
  temporal: "#c4a35a",
  occipital: "#7a9e6a",
  temporoparietal: "#8eb5c4",
  limbic: "#c47a6a",
  medial: "#a87890",
  medial_temporal: "#b8896a",
  deep: "#6a7a78",
  fill: "#5a6e68",
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
  parent.add(root);

  const parcels = {}; // meshName → { mesh, mirror?, mat, areaKey, base }
  const centroids = {};

  gltf.scene.traverse((obj) => {
    if (!obj.isMesh) return;
    const name = obj.name || obj.parent?.name;
    if (!name) return;

    const lobe = LOBE_OF[name] || "fill";
    const base = new THREE.Color(lobeColors[lobe] || lobeColors.fill);
    const mat = new THREE.MeshStandardMaterial({
      color: base.clone(),
      emissive: new THREE.Color(0x000000),
      emissiveIntensity: 0,
      roughness: 0.62,
      metalness: 0.08,
      transparent: true,
      opacity: name.startsWith("deep.") ? 0.32 : 0.78,
      depthWrite: !name.startsWith("deep."),
      side: THREE.DoubleSide,
    });
    obj.material = mat;
    obj.castShadow = false;
    obj.receiveShadow = false;

    const geo = obj.geometry;
    geo.computeBoundingBox();
    const c = new THREE.Vector3();
    geo.boundingBox.getCenter(c);
    centroids[name] = [c.x, c.y, c.z];

    const areaKey = activityKeyForMesh(name);
    parcels[name] = { mesh: obj, mat, base, areaKey, lobe };

    // Bilateral mirror for left-only merges (not brainstem/callosum)
    const skipMirror = name === "deep.brainstem" || name === "deep.callosum";
    if (!skipMirror) {
      const mirror = obj.clone();
      mirror.material = mat.clone();
      mirror.scale.x *= -1;
      mirror.name = `${name}__R`;
      // Keep same parent as obj
      (obj.parent || gltf.scene).add(mirror);
      parcels[name].mirror = mirror;
      parcels[name].mirrorMat = mirror.material;
    }
  });

  root.add(gltf.scene);

  function setParcelHeat(areaId, activity, mode = "idle") {
    const keys = Object.keys(parcels).filter((n) => {
      const k = parcels[n].areaKey;
      return k === areaId || n === areaId;
    });
    keys.forEach((n) => {
      const p = parcels[n];
      const mats = [p.mat, p.mirrorMat].filter(Boolean);
      mats.forEach((mat) => {
        if (mode === "error") {
          mat.emissive.set("#ff5533");
          mat.emissiveIntensity = 0.85;
          mat.opacity = Math.min(0.95, (mat.opacity || 0.7) + 0.15);
        } else if (mode === "feedback") {
          mat.emissive.set("#ffe066");
          mat.emissiveIntensity = 0.55 + activity * 0.4;
        } else if (mode === "lit" || activity > 0.05) {
          mat.emissive.set("#5fd4ff");
          mat.emissiveIntensity = 0.25 + activity * 0.9;
          mat.color.copy(p.base).lerp(new THREE.Color("#e8fff8"), activity * 0.35);
        } else {
          mat.emissive.set("#000000");
          mat.emissiveIntensity = 0;
          mat.color.copy(p.base);
        }
      });
    });
  }

  function decayHeats(areaActivity) {
    Object.keys(areaActivity || {}).forEach((id) => {
      setParcelHeat(id, areaActivity[id] || 0, "idle");
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

  /** Cam area centroids (MTL merges cortical+hippocampus) */
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
    pickArea,
    lobeColors,
  };
}
