interface CortexStageProps {
  /** Highlight that Cam is listening — cortex iframe can stay interactive */
  listening?: boolean;
}

/**
 * Full-bleed live 3D Cam cortex (DTI tractography).
 * Served from /viz/connectome — orbit / zoom / fiber LOD stay interactive.
 */
export function CortexStage({ listening = false }: CortexStageProps) {
  return (
    <div
      className={`cortex-stage${listening ? ' listening' : ''}`}
      aria-label="Cam 3D cortex brain visualization"
    >
      <iframe
        className="cortex-frame"
        title="Cam 3D cortex — live DTI tractography"
        src="/viz/connectome/index.html"
        allow="autoplay"
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
