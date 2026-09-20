/**
 * CamFace — Cam’s real portrait driven by NVIDIA Audio2Face ARKit weights.
 * Desk studio: integrations/llmavatartalk PushAudio → Omniverse / A2F-3D NIM.
 * Browser: same blendshape vector on the identity photo (not a stock doll).
 */
import { memo, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import * as THREE from 'three';
import { fitFromMesh } from '@/lib/a2f/fit';
import { CAM_A2F_FRAG, CAM_A2F_VERT } from '@/lib/a2f/shader';
import { buildA2FSchedule, composeA2F } from '@/lib/a2f/weights';
import type { CamA2FMesh } from '@/lib/a2f/landmarks';
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
  /** Optional Higgsfield Speak clip (never auto-fetched live). */
  clipUrl?: string | null;
}

export const CamFace = memo(function CamFace({
  status,
  listening,
  level,
  typing = false,
  speakingText = '',
  speechProgress = -1,
  clipUrl = null,
}: CamFaceProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<{ set: (w: ReturnType<typeof composeA2F>) => void } | null>(null);
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
        const mesh = (await (await fetch(MESH_URL)).json()) as CamA2FMesh;
        const fit = fitFromMesh(mesh);
        if (cancelled) return;

        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(32, 1, 0.05, 10);
        camera.position.set(0, 0.02, 1.28);

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

        const uniforms = {
          map: { value: tex },
          jawOpen: { value: 0 },
          smile: { value: 0.08 },
          blinkL: { value: 0 },
          blinkR: { value: 0 },
          funnel: { value: 0 },
          pucker: { value: 0 },
          headYaw: { value: 0 },
          headPitch: { value: 0 },
          mouthCenter: { value: new THREE.Vector2(fit.mouthCenter.x, fit.mouthCenter.y) },
          mouthSize: { value: new THREE.Vector2(fit.mouthSize.x, fit.mouthSize.y) },
          eyeL: { value: new THREE.Vector2(fit.eyeL.x, fit.eyeL.y) },
          eyeR: { value: new THREE.Vector2(fit.eyeR.x, fit.eyeR.y) },
          eyeSize: { value: new THREE.Vector2(fit.eyeSize.x, fit.eyeSize.y) },
        };

        const mat = new THREE.ShaderMaterial({
          uniforms,
          vertexShader: CAM_A2F_VERT,
          fragmentShader: CAM_A2F_FRAG,
        });
        const plane = new THREE.Mesh(new THREE.PlaneGeometry(1, 1, 32, 32), mat);
        scene.add(plane);

        apiRef.current = {
          set: (w) => {
            uniforms.jawOpen.value = Math.min(0.5, w.JawOpen ?? 0);
            uniforms.smile.value =
              ((w.MouthSmileLeft ?? 0) + (w.MouthSmileRight ?? 0)) * 0.5;
            uniforms.blinkL.value = w.EyeBlinkLeft ?? 0;
            uniforms.blinkR.value = w.EyeBlinkRight ?? 0;
            uniforms.funnel.value = w.MouthFunnel ?? 0;
            uniforms.pucker.value = w.MouthPucker ?? 0;
            uniforms.headYaw.value = w.HeadYaw ?? 0;
            uniforms.headPitch.value = w.HeadPitch ?? 0;
            plane.rotation.y = (w.HeadYaw ?? 0) * 0.18;
            plane.rotation.x = (w.HeadPitch ?? 0) * 0.12;
          },
        };

        const tick = () => {
          if (cancelled || !renderer) return;
          renderer.render(scene, camera);
          raf = requestAnimationFrame(tick);
        };
        tick();
        if (!cancelled) setReady(true);
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
      apiRef.current = null;
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
      apiRef.current?.set(
        composeA2F({
          expr,
          speaking: Boolean(speakingText) && speechProgress >= 0,
          progress: speechProgress,
          schedule,
          timeSec: (performance.now() - t0) / 1000,
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
        {clipUrl && speakingText ? (
          <video
            className="cam-face-higgsfield"
            src={clipUrl}
            autoPlay
            muted
            playsInline
            loop
            aria-hidden
          />
        ) : null}
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
