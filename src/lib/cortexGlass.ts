/* Shared glass-cortex loader for React hero + connectome viz */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import type { BrainRegion } from '@shared/types';

export const REGION_TO_AREA: Partial<Record<BrainRegion, string>> = {
  prefrontal: 'area.dlpfc',
  cortex: 'area.parietal',
  thalamus: 'area.cingulate',
  hippocampus: 'area.mtl',
  amygdala: 'area.mtl',
  insula: 'area.ofc',
  cerebellum: 'area.visual',
  basal_ganglia: 'area.dlpfc',
  striatum: 'area.temporal',
  repair_loop: 'area.cingulate',
  swarm_bus: 'area.apfc',
};

const LOBE_OF: Record<string, string> = {
  'area.dlpfc': 'frontal',
  'area.apfc': 'frontal',
  'area.ofc': 'frontal',
  'area.broca': 'frontal',
  'area.premotor': 'frontal',
  'area.motor': 'frontal',
  'area.parietal': 'parietal',
  'area.wernicke': 'temporoparietal',
  'area.temporal': 'temporal',
  'area.auditory': 'temporal',
  'area.visual': 'occipital',
  'area.cingulate': 'medial',
  'area.mtl': 'medial_temporal',
  'area.mtl.hippocampus': 'medial_temporal',
  'fill.insula': 'fill',
  'deep.amygdala': 'deep',
  'deep.thalamus': 'deep',
  'deep.striatum': 'deep',
  'deep.cerebellum': 'deep',
  'deep.brainstem': 'deep',
  'deep.callosum': 'deep',
};

const DEFAULT_LOBE_COLORS: Record<string, string> = {
  frontal: '#9ecfc4',
  parietal: '#9ab8d4',
  temporal: '#d4c49a',
  occipital: '#a8c49a',
  temporoparietal: '#b0c8d4',
  limbic: '#d4b0a0',
  medial: '#c8a0b0',
  medial_temporal: '#c8b090',
  deep: '#a0b0ac',
  fill: '#9aada8',
};

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

export type ParcelEntry = {
  mesh: THREE.Mesh;
  mirror?: THREE.Mesh;
  mat: THREE.MeshPhysicalMaterial;
  mirrorMat?: THREE.MeshPhysicalMaterial;
  base: THREE.Color;
  areaKey: string | null;
  deep: boolean;
  restOpacity: number;
};

export type CortexApi = {
  root: THREE.Group;
  parcels: Record<string, ParcelEntry>;
  centroids: Record<string, [number, number, number]>;
  setParcelHeat: (areaId: string, activity: number, mode?: string) => void;
  setTranslucency: (amount: number) => void;
  decayHeats: (areaActivity: Record<string, number>) => void;
  pickArea: (raycaster: THREE.Raycaster) => string | null;
};

function activityKeyForMesh(name: string): string | null {
  if (name === 'area.mtl.hippocampus') return 'area.mtl';
  if (name.startsWith('area.')) return name;
  return null;
}

function makeGlassMaterial(base: THREE.Color, deep: boolean) {
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

export function installGlassEnvironment(renderer: THREE.WebGLRenderer, scene: THREE.Scene) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = env;
  pmrem.dispose();
  return env;
}

export function applyFsCameraUp(camera: THREE.PerspectiveCamera) {
  camera.up.set(0, 0, 1);
}

export async function loadCamCortex(
  parent: THREE.Object3D,
  opts: { url?: string; lobeColors?: Record<string, string> } = {},
): Promise<CortexApi> {
  const url = opts.url || '/cortex/cam-cortex.glb';
  const lobeColors = { ...DEFAULT_LOBE_COLORS, ...(opts.lobeColors || {}) };
  const loader = new GLTFLoader();
  const gltf = await loader.loadAsync(url);

  const root = new THREE.Group();
  root.name = 'cam-cortex-shell';
  root.renderOrder = 2;
  parent.add(root);

  const parcels: Record<string, ParcelEntry> = {};
  const centroids: Record<string, [number, number, number]> = {};

  gltf.scene.traverse((obj) => {
    if (!(obj instanceof THREE.Mesh)) return;
    const name = obj.name || obj.parent?.name;
    if (!name) return;

    const lobe = LOBE_OF[name] || 'fill';
    const deep = name.startsWith('deep.');
    const base = new THREE.Color(lobeColors[lobe] || lobeColors.fill);
    const mat = makeGlassMaterial(base, deep);
    obj.material = mat;
    obj.castShadow = false;
    obj.receiveShadow = false;
    obj.renderOrder = deep ? 1 : 2;

    const geo = obj.geometry;
    geo.computeBoundingBox();
    const c = new THREE.Vector3();
    geo.boundingBox!.getCenter(c);
    centroids[name] = [c.x, c.y, c.z];

    const areaKey = activityKeyForMesh(name);
    const restOpacity = deep ? GLASS.deepOpacity : GLASS.cortexOpacity;
    parcels[name] = { mesh: obj, mat, base, areaKey, deep, restOpacity };

    if (name !== 'deep.brainstem' && name !== 'deep.callosum') {
      const mirror = obj.clone();
      mirror.material = makeGlassMaterial(base, deep);
      mirror.scale.x *= -1;
      mirror.name = `${name}__R`;
      mirror.renderOrder = obj.renderOrder;
      (obj.parent || gltf.scene).add(mirror);
      parcels[name].mirror = mirror;
      parcels[name].mirrorMat = mirror.material as THREE.MeshPhysicalMaterial;
    }
  });

  root.add(gltf.scene);

  function applyMatState(
    mat: THREE.MeshPhysicalMaterial,
    p: ParcelEntry,
    activity: number,
    mode: string,
  ) {
    const rest = p.restOpacity;
    const baseTx = p.deep ? GLASS.deepTransmission : GLASS.cortexTransmission;
    if (mode === 'error') {
      mat.emissive.set('#ff5533');
      mat.emissiveIntensity = 1.15;
      mat.opacity = Math.min(0.78, rest + GLASS.litOpacityBoost + 0.12);
      mat.transmission = Math.max(0.4, baseTx - 0.3);
      mat.color.copy(p.base);
    } else if (mode === 'feedback' || mode === 'lit' || activity > 0.05) {
      const lit = mode === 'feedback' ? '#ffe066' : '#5fd4ff';
      mat.emissive.set(lit);
      mat.emissiveIntensity = 0.4 + activity * 1.2;
      mat.opacity = rest + GLASS.litOpacityBoost * Math.max(activity, 0.35);
      mat.transmission = baseTx * (1 - activity * 0.32);
      mat.color.copy(p.base).lerp(new THREE.Color('#e8fff8'), activity * 0.45);
    } else {
      mat.emissive.set('#1a3028');
      mat.emissiveIntensity = p.deep ? 0.02 : 0.06;
      mat.opacity = rest;
      mat.transmission = baseTx;
      mat.color.copy(p.base);
    }
  }

  function setParcelHeat(areaId: string, activity: number, mode = 'idle') {
    Object.keys(parcels)
      .filter((n) => parcels[n].areaKey === areaId || n === areaId)
      .forEach((n) => {
        const p = parcels[n];
        [p.mat, p.mirrorMat].filter(Boolean).forEach((mat) => {
          applyMatState(mat!, p, activity, mode);
        });
      });
  }

  function decayHeats(areaActivity: Record<string, number>) {
    Object.keys(areaActivity).forEach((id) => {
      setParcelHeat(id, areaActivity[id] || 0, 'idle');
    });
  }

  function setTranslucency(amount = 0.85) {
    const t = Math.max(0, Math.min(1, amount));
    Object.values(parcels).forEach((p) => {
      const rest = p.deep
        ? THREE.MathUtils.lerp(0.32, 0.1, t)
        : THREE.MathUtils.lerp(0.55, 0.2, t);
      p.restOpacity = rest;
      [p.mat, p.mirrorMat].filter(Boolean).forEach((mat) => {
        mat!.opacity = rest;
        mat!.transmission = THREE.MathUtils.lerp(0.35, 0.85, t);
        mat!.emissiveIntensity = THREE.MathUtils.lerp(0.02, 0.07, t);
      });
    });
  }

  function pickArea(raycaster: THREE.Raycaster) {
    const meshes: THREE.Object3D[] = [];
    Object.values(parcels).forEach((p) => {
      meshes.push(p.mesh);
      if (p.mirror) meshes.push(p.mirror);
    });
    const hits = raycaster.intersectObjects(meshes, false);
    if (!hits.length) return null;
    const n = hits[0].object.name.replace(/__R$/, '');
    return parcels[n]?.areaKey || (n.startsWith('area.') ? n : null);
  }

  const outCentroids = { ...centroids };
  if (centroids['area.mtl'] && centroids['area.mtl.hippocampus']) {
    const a = centroids['area.mtl'];
    const b = centroids['area.mtl.hippocampus'];
    outCentroids['area.mtl'] = [
      (a[0] + b[0]) / 2,
      (a[1] + b[1]) / 2,
      (a[2] + b[2]) / 2,
    ];
  }

  return {
    root,
    parcels,
    centroids: outCentroids,
    setParcelHeat,
    setTranslucency,
    decayHeats,
    pickArea,
  };
}

/** Lightweight association fibers between Cam area centroids */
export function buildHeroTracts(
  parent: THREE.Object3D,
  centroids: Record<string, [number, number, number]>,
): THREE.Group {
  const pairs: [string, string][] = [
    ['area.wernicke', 'area.broca'],
    ['area.broca', 'area.dlpfc'],
    ['area.dlpfc', 'area.parietal'],
    ['area.visual', 'area.temporal'],
    ['area.temporal', 'area.ofc'],
    ['area.mtl', 'area.cingulate'],
    ['area.cingulate', 'area.dlpfc'],
    ['area.mtl', 'area.dlpfc'],
    ['area.auditory', 'area.broca'],
    ['area.apfc', 'area.mtl'],
    ['area.premotor', 'area.motor'],
    ['area.visual', 'area.parietal'],
  ];
  const group = new THREE.Group();
  group.name = 'hero-tracts';
  for (const [a, b] of pairs) {
    const A = centroids[a];
    const B = centroids[b];
    if (!A || !B) continue;
    const mid = new THREE.Vector3(
      (A[0] + B[0]) / 2,
      (A[1] + B[1]) / 2 + 0.35,
      (A[2] + B[2]) / 2,
    );
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(...A),
      mid,
      new THREE.Vector3(...B),
    );
    const pts = curve.getPoints(28);
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const dir = new THREE.Vector3(...B).sub(new THREE.Vector3(...A)).normalize();
    const col = new THREE.Color(Math.abs(dir.x), Math.abs(dir.z), Math.abs(dir.y));
    const mat = new THREE.LineBasicMaterial({
      color: col,
      transparent: true,
      opacity: 0.35,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const line = new THREE.Line(geo, mat);
    line.renderOrder = 0;
    group.add(line);
  }
  parent.add(group);
  return group;
}
