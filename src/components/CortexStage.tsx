import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { useMeshStore } from '@/store/meshStore';
import {
  applyFsCameraUp,
  buildHeroTracts,
  installGlassEnvironment,
  loadCamCortex,
  REGION_TO_AREA,
  type CortexApi,
} from '@/lib/cortexGlass';
import type { BrainRegion } from '@shared/types';

interface CortexStageProps {
  listening?: boolean;
  onFocusArea?: (areaId: string) => void;
}

type LiveFeed = {
  firing?: { area?: string; intensity?: number }[];
  firing_count?: number;
};

export function CortexStage({ listening = false, onFocusArea }: CortexStageProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<CortexApi | null>(null);
  const activityRef = useRef<Record<string, number>>({});
  const listeningRef = useRef(listening);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agents, setAgents] = useState(0);
  const [glass, setGlass] = useState(true);

  const scanning = useMeshStore((s) => s.scanning);
  const nodes = useMeshStore((s) => s.nodes);
  const selectedNodeId = useMeshStore((s) => s.selectedNodeId);

  useEffect(() => {
    listeningRef.current = listening;
  }, [listening]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    let disposed = false;
    let raf = 0;
    let last = performance.now();
    const areaActivity = activityRef.current;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x05080a, 0.022);

    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    applyFsCameraUp(camera);
    camera.position.set(2.6, 5.2, 2.0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.12;
    host.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0, 0.1, 0.15);
    controls.minDistance = 2.2;
    controls.maxDistance = 12;
    applyFsCameraUp(camera);

    scene.add(new THREE.AmbientLight(0xb8d4cc, 0.7));
    const key = new THREE.DirectionalLight(0xfff5e8, 0.85);
    key.position.set(3, 4, 6);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0x88b0cc, 0.35);
    fill.position.set(-4, -2, 2);
    scene.add(fill);
    scene.add(new THREE.HemisphereLight(0xcfe8e0, 0x1a1008, 0.35));
    installGlassEnvironment(renderer, scene);

    const brain = new THREE.Group();
    scene.add(brain);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    const resize = () => {
      const w = host.clientWidth;
      const h = Math.max(host.clientHeight, 320);
      renderer.setSize(w, h, false);
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(host);

    const onPointer = (ev: PointerEvent) => {
      if (!apiRef.current) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const areaId = apiRef.current.pickArea(raycaster);
      if (!areaId) return;
      areaActivity[areaId] = Math.max(areaActivity[areaId] || 0, 0.9);
      apiRef.current.setParcelHeat(areaId, 0.9, 'lit');
      onFocusArea?.(areaId);
    };
    renderer.domElement.addEventListener('pointerdown', onPointer);

    (async () => {
      try {
        let lobeColors: Record<string, string> | undefined;
        try {
          const cdoc = await fetch('/cortex/anatomy-centroids.json').then((r) => r.json());
          lobeColors = cdoc.lobe_colors;
        } catch {
          /* defaults */
        }
        const api = await loadCamCortex(brain, {
          url: '/cortex/cam-cortex.glb',
          lobeColors,
        });
        if (disposed) return;
        api.setTranslucency(0.82);
        buildHeroTracts(brain, api.centroids);
        apiRef.current = api;
        setReady(true);
      } catch (e) {
        if (!disposed) setError(e instanceof Error ? e.message : 'Cortex load failed');
      }
    })();

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      controls.update();
      // Always-on idle spin; listen mode slightly livelier
      brain.rotation.z += listeningRef.current ? 0.00135 : 0.00085;
      Object.keys(areaActivity).forEach((id) => {
        areaActivity[id] = Math.max(0, (areaActivity[id] || 0) - dt * 0.18);
        apiRef.current?.setParcelHeat(id, areaActivity[id], 'idle');
      });
      if (listeningRef.current) {
        ['area.auditory', 'area.broca', 'area.wernicke'].forEach((id) => {
          areaActivity[id] = Math.max(areaActivity[id] || 0, 0.45);
          apiRef.current?.setParcelHeat(id, areaActivity[id], 'lit');
        });
      }
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener('pointerdown', onPointer);
      controls.dispose();
      renderer.dispose();
      host.removeChild(renderer.domElement);
      apiRef.current = null;
    };
  }, [onFocusArea]);

  // Mesh store → parcel heat
  useEffect(() => {
    const api = apiRef.current;
    if (!api) return;
    const act = activityRef.current;
    if (scanning) {
      ['area.dlpfc', 'area.cingulate', 'area.parietal'].forEach((id) => {
        act[id] = Math.max(act[id] || 0, 0.7);
        api.setParcelHeat(id, 0.7, 'lit');
      });
    }
    if (selectedNodeId) {
      const node = nodes.find((n) => n.id === selectedNodeId);
      const area = node?.region
        ? REGION_TO_AREA[node.region as BrainRegion]
        : undefined;
      if (area) {
        act[area] = Math.max(act[area] || 0, 0.85);
        api.setParcelHeat(area, 0.85, 'lit');
      }
    }
  }, [scanning, selectedNodeId, nodes, ready]);

  // Live activity distillate (optional)
  useEffect(() => {
    if (!ready) return;
    let alive = true;
    const poll = async () => {
      try {
        const feed = (await fetch(`/cortex/live-activity.json?t=${Date.now()}`).then(
          (r) => (r.ok ? r.json() : null),
        )) as LiveFeed | null;
        if (!alive || !feed || !apiRef.current) return;
        setAgents(feed.firing_count || feed.firing?.length || 0);
        (feed.firing || []).forEach((f) => {
          if (!f.area) return;
          const intensity = f.intensity || 0.4;
          activityRef.current[f.area] = Math.max(
            activityRef.current[f.area] || 0,
            intensity,
          );
          apiRef.current?.setParcelHeat(
            f.area,
            intensity,
            intensity > 0.55 ? 'lit' : 'feedback',
          );
        });
      } catch {
        /* offline */
      }
    };
    poll();
    const id = window.setInterval(poll, 2500);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [ready]);

  useEffect(() => {
    apiRef.current?.setTranslucency(glass ? 0.82 : 0.28);
  }, [glass, ready]);

  return (
    <div
      className={`cortex-stage${listening ? ' listening' : ''}`}
      aria-label="Glass Cam cortex"
    >
      <div ref={hostRef} className="cortex-canvas-host" />
      {!ready && !error && <div className="cortex-status">Loading glass cortex…</div>}
      {error && (
        <div className="cortex-status error">
          Cortex unavailable — {error}
        </div>
      )}
      <div className="cortex-hud">
        <span>Orbit · click a parcel · fibers glow through</span>
        <div className="cortex-hud-actions">
          <button
            type="button"
            className={glass ? 'on' : ''}
            onClick={() => setGlass((g) => !g)}
            title="Toggle shell translucency"
          >
            Glass
          </button>
          <span className="cortex-agents">{agents} agents</span>
        </div>
      </div>
    </div>
  );
}
