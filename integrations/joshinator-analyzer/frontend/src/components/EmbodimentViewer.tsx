// Procedural 3D embodiment stage — original primitives only (no GLTF / IP assets).
import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { Embodiment } from '../types';

interface Props {
  embodiment: Embodiment | null;
  activeAction?: string | null;
}

function makeBody(recipe: Embodiment['mesh']): THREE.Object3D {
  const group = new THREE.Group();
  const primary = new THREE.Color(recipe.primary_hex);
  const secondary = new THREE.Color(recipe.secondary_hex);
  const emissive = new THREE.Color(recipe.emissive_hex);

  const bodyMat = new THREE.MeshStandardMaterial({
    color: primary,
    emissive,
    emissiveIntensity: 0.22,
    metalness: 0.25,
    roughness: 0.45,
  });
  const headMat = new THREE.MeshStandardMaterial({
    color: secondary,
    emissive,
    emissiveIntensity: 0.12,
    metalness: 0.1,
    roughness: 0.55,
  });
  const accentMat = new THREE.MeshStandardMaterial({
    color: emissive,
    emissive,
    emissiveIntensity: 0.55,
    metalness: 0.4,
    roughness: 0.35,
  });

  const h = recipe.height;
  const b = recipe.bulk;

  let bodyGeom: THREE.BufferGeometry;
  switch (recipe.body) {
    case 'cone':
      bodyGeom = new THREE.ConeGeometry(0.28 * b, 0.9 * h, 16);
      break;
    case 'octahedron':
      bodyGeom = new THREE.OctahedronGeometry(0.42 * b, 0);
      break;
    case 'torus':
      bodyGeom = new THREE.TorusGeometry(0.35 * b, 0.14 * b, 12, 24);
      break;
    case 'capsule':
    default:
      bodyGeom = new THREE.CapsuleGeometry(0.22 * b, 0.55 * h, 6, 12);
      break;
  }
  const body = new THREE.Mesh(bodyGeom, bodyMat);
  body.position.y = 0.55 * h;
  group.add(body);

  let headGeom: THREE.BufferGeometry;
  switch (recipe.head) {
    case 'box':
      headGeom = new THREE.BoxGeometry(0.28 * b, 0.28 * b, 0.28 * b);
      break;
    case 'dodecahedron':
      headGeom = new THREE.DodecahedronGeometry(0.18 * b, 0);
      break;
    case 'sphere':
    default:
      headGeom = new THREE.SphereGeometry(0.18 * b, 20, 16);
      break;
  }
  const head = new THREE.Mesh(headGeom, headMat);
  head.position.y = 0.55 * h + 0.45 * h;
  group.add(head);

  if (recipe.accent === 'ring') {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.38 * b, 0.035, 10, 32),
      accentMat
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.55 * h;
    group.add(ring);
  } else if (recipe.accent === 'fins') {
    for (const x of [-0.32 * b, 0.32 * b]) {
      const fin = new THREE.Mesh(
        new THREE.ConeGeometry(0.08 * b, 0.35 * h, 6),
        accentMat
      );
      fin.position.set(x, 0.7 * h, 0);
      fin.rotation.z = x < 0 ? 0.6 : -0.6;
      group.add(fin);
    }
  } else if (recipe.accent === 'spikes') {
    for (let i = 0; i < 5; i++) {
      const spike = new THREE.Mesh(
        new THREE.ConeGeometry(0.05 * b, 0.22 * h, 5),
        accentMat
      );
      const a = (i / 5) * Math.PI * 2;
      spike.position.set(Math.cos(a) * 0.28 * b, 0.95 * h, Math.sin(a) * 0.28 * b);
      group.add(spike);
    }
  }

  return group;
}

function makeArena(motif: string, colorHex: string): THREE.Object3D {
  const group = new THREE.Group();
  const mat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(colorHex),
    emissive: new THREE.Color(colorHex),
    emissiveIntensity: 0.35,
    transparent: true,
    opacity: 0.55,
    side: THREE.DoubleSide,
  });

  const disc = new THREE.Mesh(new THREE.RingGeometry(0.55, 1.15, 48), mat);
  disc.rotation.x = -Math.PI / 2;
  group.add(disc);

  if (motif === 'hex_grid') {
    const hex = new THREE.Mesh(
      new THREE.CircleGeometry(0.5, 6),
      new THREE.MeshBasicMaterial({
        color: colorHex,
        transparent: true,
        opacity: 0.25,
        side: THREE.DoubleSide,
      })
    );
    hex.rotation.x = -Math.PI / 2;
    hex.position.y = 0.01;
    group.add(hex);
  } else if (motif === 'lane_rings') {
    for (const r of [0.7, 0.9, 1.1]) {
      const lane = new THREE.Mesh(
        new THREE.RingGeometry(r - 0.03, r, 48),
        new THREE.MeshBasicMaterial({
          color: colorHex,
          transparent: true,
          opacity: 0.35,
          side: THREE.DoubleSide,
        })
      );
      lane.rotation.x = -Math.PI / 2;
      lane.position.y = 0.015;
      group.add(lane);
    }
  }

  return group;
}

const EmbodimentViewer: React.FC<Props> = ({ embodiment, activeAction }) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const actorRef = useRef<THREE.Object3D | null>(null);
  const animRef = useRef<number>(0);
  const actionRef = useRef<string | null>(null);

  useEffect(() => {
    actionRef.current = activeAction ?? null;
  }, [activeAction]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !embodiment) return;

    const width = mount.clientWidth || 360;
    const height = mount.clientHeight || 280;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x0b1220, 0.085);

    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 40);
    camera.position.set(2.2, 1.8, 2.6);
    camera.lookAt(0, 0.8, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight(0xb8d4ff, 0x1a2030, 0.9);
    scene.add(hemi);
    const key = new THREE.DirectionalLight(0xffffff, 0.85);
    key.position.set(3, 5, 2);
    scene.add(key);

    const arena = makeArena(embodiment.arena_motif, embodiment.mesh.emissive_hex);
    scene.add(arena);

    const actor = makeBody(embodiment.mesh);
    scene.add(actor);
    actorRef.current = actor;

    let t0 = performance.now();
    const tick = (now: number) => {
      const t = (now - t0) / 1000;
      arena.rotation.y = t * 0.25;

      if (actorRef.current) {
        const action = actionRef.current;
        let bob = Math.sin(t * 2.2) * 0.04;
        let spin = t * 0.35;
        if (action && action !== 'idle') {
          bob = Math.sin(t * 8) * 0.12;
          spin = t * 1.8;
          actorRef.current.scale.setScalar(1 + Math.sin(t * 10) * 0.04);
        } else {
          actorRef.current.scale.setScalar(1);
        }
        actorRef.current.position.y = bob;
        actorRef.current.rotation.y = spin;
      }

      renderer.render(scene, camera);
      animRef.current = requestAnimationFrame(tick);
    };
    animRef.current = requestAnimationFrame(tick);

    const onResize = () => {
      if (!mount) return;
      const w = mount.clientWidth || 360;
      const h = mount.clientHeight || 280;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', onResize);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', onResize);
      actorRef.current = null;
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement);
      }
      scene.traverse((obj) => {
        const mesh = obj as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
        const mat = mesh.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((m) => m.dispose());
        else if (mat) mat.dispose();
      });
    };
  }, [embodiment]);

  if (!embodiment) {
    return (
      <div className="embodiment-viewer embodiment-empty">
        <p>No 3D embodiment yet</p>
        <span>Detect a card to spawn an original procedural champion</span>
      </div>
    );
  }

  return (
    <div className="embodiment-viewer">
      <div className="embodiment-hud">
        <div className="embodiment-title">
          <strong>{embodiment.display_name}</strong>
          <span>{embodiment.subtitle}</span>
        </div>
        <div className="embodiment-hp">
          HP {embodiment.hp.current}/{embodiment.hp.max}
        </div>
        <div className="embodiment-archetype">{embodiment.archetype_id.replace(/_/g, ' ')}</div>
      </div>
      <div className="embodiment-canvas" ref={mountRef} />
      <div className="embodiment-actions">
        {embodiment.actions.map((action) => (
          <span key={action} className={`embodiment-action-chip${activeAction === action ? ' active' : ''}`}>
            {action.replace(/_/g, ' ')}
          </span>
        ))}
      </div>
      <p className="embodiment-license">{embodiment.license_note}</p>
    </div>
  );
};

export default EmbodimentViewer;
