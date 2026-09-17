import { useEffect, useRef } from 'react';

interface CortexStageProps {
  /** Highlight that Cam is listening — cortex iframe can stay interactive */
  listening?: boolean;
}

/**
 * Full-bleed live 3D Cam cortex (DTI tractography).
 * Embed mode strips nested chrome; pauses RAF when off-screen / hidden.
 */
export function CortexStage({ listening = false }: CortexStageProps) {
  const frameRef = useRef<HTMLIFrameElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const frame = frameRef.current;
    const stage = stageRef.current;
    if (!frame || !stage) return;

    const post = (msg: object) => {
      try {
        frame.contentWindow?.postMessage(msg, window.location.origin);
      } catch {
        /* cross-origin during load — ignore */
      }
    };

    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries.some((e) => e.isIntersecting && e.intersectionRatio > 0.08);
        post({ type: visible ? 'cam-cortex-resume' : 'cam-cortex-pause' });
      },
      { threshold: [0, 0.08, 0.25] },
    );
    io.observe(stage);

    const onVis = () => {
      if (document.hidden) post({ type: 'cam-cortex-pause' });
      else post({ type: 'cam-cortex-resume' });
    };
    document.addEventListener('visibilitychange', onVis);

    return () => {
      io.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      post({ type: 'cam-cortex-pause' });
    };
  }, []);

  return (
    <div
      ref={stageRef}
      className={`cortex-stage${listening ? ' listening' : ''}`}
      aria-label="Cam 3D cortex brain visualization"
    >
      <iframe
        ref={frameRef}
        className="cortex-frame"
        title="Cam 3D cortex — live DTI tractography"
        src="/viz/connectome/index.html?embed=1"
        allow="autoplay"
        loading="eager"
      />
      <div className="cortex-hud" aria-hidden>
        <span className="cortex-hud-pill">
          <i /> Live 3D cortex
        </span>
        <span className="cortex-hud-hint">Orbit · zoom · fibers brighten with agents</span>
      </div>
    </div>
  );
}
