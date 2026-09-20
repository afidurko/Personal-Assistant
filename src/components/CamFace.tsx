/**
 * CamFace — Cam’s actual portrait as an Audio2Face ARKit mesh.
 * Desk: NVIDIA A2F / A2F-3D NIM (integrations/llmavatartalk gRPC).
 * Browser: same ARKit weights on the photo-fitted MediaPipe mesh.
 */
import { memo, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import * as THREE from 'three';
import { applyA2FDisplacements, headPoseFromWeights } from '@/lib/a2f/displace';
import { LIPS_INNER_LOOP, type CamA2FMesh } from '@/lib/a2f/landmarks';
import { buildA2FSchedule, composeA2F } from '@/lib/a2f/weights';
import { expressionFromStatus } from '@/lib/visemes';
import type { CamVoiceStatus } from '@/hooks/useCamVoice';

const PHOTO = '/identity/persona/cam-face.jpg';
const MESH_URL = '/avatars/cam-a2f-mesh.json';

interface CamFaceProps {
  status: CamVoiceStatus;
  listening: boolean;
  level: number;
  typing?: boolean;
  speakingText?: string;
  speechProgress?: number;
}

export const CamFace = memo(function CamFace({
  status,
  listening,
  level,
  typing = false,
  speakingText = '',
  speechProgress = -1,
}: CamFaceProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const weightsApi = useRef<{
    set: (w: ReturnType<typeof composeA2F>) => void;
  } | null>(null);
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const expr = expressionFromStatus(status, typing);
  const schedule = useMemo(() => buildA2FSchedule(speakingText), [speakingText]);

  useEffect(() => {
    const node = mountRef.current;
    if (!node) return;
    let cancelled = false;
    let renderer: THREE.WebGLRenderer | null = null;
    let raf = 0;

    (async () => {
      try {
        const meshRes = await fetch(MESH_URL);
        if (!meshRes.ok) throw new Error('Cam A2F mesh missing — run scripts/build-cam-a2f-mesh.mjs');
        const mesh = (await meshRes.json()) as CamA2FMesh;
        if (cancelled) return;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(28, 1, 0.05, 10);
        camera.position.set(0, 0.02, 1.15);

        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
        renderer.setSize(node.clientWidth, node.clientHeight);
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.setClearColor(0x000000, 0);
        node.replaceChildren(renderer.domElement);

        const tex = await new THREE.TextureLoader().loadAsync(PHOTO);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.minFilter = THREE.LinearFilter;
        tex.generateMipmaps = false;

        const rest = new Float32Array(mesh.positions);
        const live = new Float32Array(mesh.positions);
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(live, 3));
        geo.setAttribute('uv', new THREE.Float32BufferAttribute(mesh.uvs, 2));
        geo.setIndex(mesh.indices);
        geo.computeVertexNormals();

        const faceMat = new THREE.MeshBasicMaterial({
          map: tex,
          transparent: false,
          side: THREE.DoubleSide,
        });
        const face = new THREE.Mesh(geo, faceMat);

        const loop = mesh.mouthLoop?.length ? mesh.mouthLoop : LIPS_INNER_LOOP;
        const cavityPos: number[] = [];
        const cavityIdx: number[] = [];
        for (const i of loop) {
          cavityPos.push(rest[i * 3] ?? 0, rest[i * 3 + 1] ?? 0, (rest[i * 3 + 2] ?? 0) - 0.04);
        }
        for (let i = 1; i < loop.length - 1; i++) cavityIdx.push(0, i, i + 1);
        const cavityGeo = new THREE.BufferGeometry();
        cavityGeo.setAttribute('position', new THREE.Float32BufferAttribute(cavityPos, 3));
        cavityGeo.setIndex(cavityIdx);
        const cavity = new THREE.Mesh(
          cavityGeo,
          new THREE.MeshBasicMaterial({ color: 0x2a1410, side: THREE.DoubleSide }),
        );

        const teeth = new THREE.Mesh(
          new THREE.PlaneGeometry(0.09, 0.028),
          new THREE.MeshBasicMaterial({ color: 0xe8dcd0, side: THREE.DoubleSide }),
        );
        teeth.position.set(0, 0.01, -0.03);

        const head = new THREE.Group();
        head.add(cavity);
        head.add(teeth);
        head.add(face);
        scene.add(head);

        scene.add(new THREE.AmbientLight(0xffffff, 1));

        const current = { weights: composeA2F({ expr: 'idle', speaking: false, progress: -1, schedule: [], timeSec: 0 }) };
        weightsApi.current = {
          set: (w) => {
            current.weights = w;
          },
        };

        const tick = () => {
          if (cancelled || !renderer) return;
          const w = current.weights;
          applyA2FDisplacements(rest, w, live);
          (geo.getAttribute('position') as THREE.BufferAttribute).needsUpdate = true;
          const pose = headPoseFromWeights(w);
          head.rotation.set(pose.pitch, pose.yaw, pose.roll);
          const jaw = w.JawOpen ?? 0;
          teeth.position.y = 0.012 - jaw * 0.03;
          teeth.scale.set(1 + jaw * 0.15, 1 + jaw * 0.8, 1);
          teeth.visible = jaw > 0.12;
          renderer.render(scene, camera);
          raf = requestAnimationFrame(tick);
        };
        tick();

        const onResize = () => {
          if (!renderer || !node) return;
          const s = Math.max(1, node.clientWidth);
          renderer.setSize(s, s);
        };
        window.addEventListener('resize', onResize);

        if (!cancelled) setReady(true);
        return () => window.removeEventListener('resize', onResize);
      } catch (e) {
        console.error('Cam A2F avatar failed', e);
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : 'Avatar failed');
          setReady(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      weightsApi.current = null;
      try {
        renderer?.dispose();
      } catch {
        /* ignore */
      }
      if (node) node.replaceChildren();
    };
  }, []);

  useEffect(() => {
    let raf = 0;
    const t0 = performance.now();
    const loop = () => {
      const timeSec = (performance.now() - t0) / 1000;
      weightsApi.current?.set(
        composeA2F({
          expr,
          speaking: Boolean(speakingText) && speechProgress >= 0,
          progress: speechProgress,
          schedule,
          timeSec,
        }),
      );
      raf = requestAnimationFrame(loop);
    };
    loop();
    return () => cancelAnimationFrame(raf);
  }, [expr, speakingText, speechProgress, schedule]);

  return (
    <div
      className={`cam-face-live expr-${expr}${listening ? ' live' : ''}${
        speakingText ? ' mouth-open' : ''
      }${ready ? ' ready' : ''}`}
      style={{ ['--level' as string]: String(level) } as CSSProperties}
      role="img"
      aria-label={`Cam, ${expr}`}
    >
      <div className="cam-face-live-inner cam-face-a2f">
        <div ref={mountRef} className="cam-face-th-mount" />
        {!ready && !loadError ? <p className="cam-face-loading">Fitting Cam…</p> : null}
        {loadError ? (
          <div className="cam-face-fallback">
            <img src={PHOTO} alt="Cam" />
          </div>
        ) : null}
      </div>
    </div>
  );
});
