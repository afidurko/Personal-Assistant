import {
  SWIFT_GUIDE_BY_ID,
  SWIFT_GUIDE_CONCEPTS,
  type SwiftConceptId,
} from '@shared/swiftGuide';
import { useMeshStore } from '@/store/meshStore';

interface SwiftGuidePanelProps {
  onOpenConcept: (conceptId: string) => void;
  onGuideStart: () => void;
  onGuideNext: () => void;
  onGuidePrev: () => void;
  onOpenWorkspace: (workspaceId: string) => void;
}

export function SwiftGuidePanel({
  onOpenConcept,
  onGuideStart,
  onGuideNext,
  onGuidePrev,
  onOpenWorkspace,
}: SwiftGuidePanelProps) {
  const activeConceptId = useMeshStore((s) => s.activeConceptId);
  const guideStep = useMeshStore((s) => s.guideStep ?? 0);
  const workspaces = useMeshStore((s) => s.workspaces);

  const active = activeConceptId
    ? SWIFT_GUIDE_BY_ID[activeConceptId as SwiftConceptId]
    : null;

  const jumpPath = active
    ? SWIFT_GUIDE_CONCEPTS.filter((c) => c.tourOrder <= active.tourOrder)
    : [];

  return (
    <section className="panel guide-panel" aria-labelledby="swift-guide-heading">
      <div className="panel-header">
        <h2 id="swift-guide-heading">Swift Guide</h2>
        <span className="panel-meta">
          {guideStep > 0 ? `Step ${guideStep} / ${SWIFT_GUIDE_CONCEPTS.length}` : 'Tour'}
        </span>
      </div>

      <p className="guide-lede">
        Explore language concepts like a playground tour — each node lights related
        workspaces on the brain map.
      </p>

      <div className="guide-controls">
        <button type="button" className="btn btn-ghost" onClick={onGuideStart}>
          Start tour
        </button>
        <button type="button" className="btn btn-ghost" onClick={onGuidePrev} disabled={!active}>
          Prev
        </button>
        <button type="button" className="btn" onClick={onGuideNext}>
          {active?.nextId ? 'Next concept' : active ? 'Restart' : 'Begin'}
        </button>
      </div>

      {jumpPath.length > 0 && (
        <nav className="jump-bar" aria-label="Guide path">
          {jumpPath.map((c, i) => (
            <button
              key={c.id}
              type="button"
              className={`jump-crumb${c.id === active?.id ? ' current' : ''}`}
              onClick={() => onOpenConcept(c.id)}
            >
              {i > 0 && <span className="jump-sep">/</span>}
              {c.title}
            </button>
          ))}
        </nav>
      )}

      <ul className="concept-list">
        {SWIFT_GUIDE_CONCEPTS.map((c) => (
          <li key={c.id}>
            <button
              type="button"
              className={`concept-item${activeConceptId === c.id ? ' selected' : ''}`}
              onClick={() => onOpenConcept(c.id)}
            >
              <span className="concept-swatch" style={{ background: c.color }} />
              <span className="concept-order">{c.tourOrder}</span>
              <span className="concept-name">{c.title}</span>
            </button>
          </li>
        ))}
      </ul>

      {active && (
        <div className="concept-detail">
          <h2>{active.title}</h2>
          <p>{active.summary}</p>
          <p className="concept-explore">{active.explore}</p>
          <pre className="concept-sample">
            <code>{active.sample}</code>
          </pre>
          <div className="concept-related">
            <span className="metric-label">Related workspaces</span>
            <div className="related-chips">
              {active.relatedWorkspaceKinds.map((kind) => {
                const ws = workspaces.find((w) => w.kind === kind);
                return (
                  <button
                    key={kind}
                    type="button"
                    className="related-chip"
                    onClick={() => onOpenWorkspace(ws?.id ?? `workspace-${kind}`)}
                  >
                    {ws?.name ?? kind}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
