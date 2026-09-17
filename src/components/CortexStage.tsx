import { useEffect, useRef } from 'react';
import { mountCortex } from '@/lib/cortex/engine.js';

interface CortexStageProps {
  listening?: boolean;
}

type CortexHandle = {
  destroy: () => void;
  pause: () => void;
  resume: () => void;
  setLodHigh: (high: boolean) => void;
};

/**
 * In-process Cam cortex (vendored three) — no iframe, shared heap + resize.
 */
export function CortexStage({ listening = false }: CortexStageProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const mountRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<CortexHandle | null>(null);

  useEffect(() => {
    const host = mountRef.current;
    const stage = stageRef.current;
    if (!host || !stage) return;

    const api = mountCortex(host, {
      embed: true,
      liveActivityUrl: '/api/runtime/live-activity',
      pollMs: 5000,
    }) as CortexHandle;
    apiRef.current = api;

    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries.some((e) => e.isIntersecting && e.intersectionRatio > 0.08);
        if (visible) api.resume();
        else api.pause();
      },
      { threshold: [0, 0.08, 0.25] },
    );
    io.observe(stage);

    const onVis = () => {
      if (document.hidden) api.pause();
      else api.resume();
    };
    document.addEventListener('visibilitychange', onVis);

    return () => {
      io.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      api.destroy();
      apiRef.current = null;
    };
  }, []);

  return (
    <div
      ref={stageRef}
      className={`cortex-stage${listening ? ' listening' : ''}`}
      aria-label="Cam 3D cortex brain visualization"
    >
      <div ref={mountRef} className="cortex-mount-host" />
      <div className="cortex-hud" aria-hidden>
        <span className="cortex-hud-pill">
          <i /> Live 3D cortex
        </span>
        <span className="cortex-hud-hint">Orbit · zoom · adaptive LOD · no iframe</span>
      </div>
    </div>
  );
}
