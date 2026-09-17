import { useEffect, useRef } from 'react';

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
 * In-process Cam cortex (vendored three) — lazy-loaded, no iframe.
 */
export function CortexStage({ listening = false }: CortexStageProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const mountRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<CortexHandle | null>(null);

  useEffect(() => {
    const host = mountRef.current;
    const stage = stageRef.current;
    if (!host || !stage) return;

    let cancelled = false;
    let io: IntersectionObserver | null = null;
    let ro: ResizeObserver | null = null;

    const onVis = () => {
      const api = apiRef.current;
      if (!api) return;
      if (document.hidden) api.pause();
      else api.resume();
    };

    void import('@/lib/cortex/engine.js')
      .then(({ mountCortex }) => {
        if (cancelled || !mountRef.current || !stageRef.current) return;
        const api = mountCortex(mountRef.current, {
          embed: true,
          liveActivityUrl: '/api/runtime/live-activity',
          pollMs: 5000,
        }) as CortexHandle;
        if (cancelled) {
          api.destroy();
          return;
        }
        apiRef.current = api;

        io = new IntersectionObserver(
          (entries) => {
            const visible = entries.some((e) => e.isIntersecting && e.intersectionRatio > 0.08);
            if (visible) api.resume();
            else api.pause();
          },
          { threshold: [0, 0.08, 0.25] },
        );
        io.observe(stageRef.current);

        // Layout/settling often changes size without a window resize.
        ro = new ResizeObserver(() => {
          window.dispatchEvent(new Event('resize'));
        });
        ro.observe(mountRef.current);

        document.addEventListener('visibilitychange', onVis);
      })
      .catch((err) => {
        console.error('[cortex] failed to mount', err);
        if (mountRef.current) {
          mountRef.current.innerHTML =
            '<p class="cortex-fallback">Cortex failed to load — refresh to retry.</p>';
        }
      });

    return () => {
      cancelled = true;
      io?.disconnect();
      ro?.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      apiRef.current?.destroy();
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
