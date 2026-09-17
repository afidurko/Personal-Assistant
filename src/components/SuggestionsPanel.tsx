import type { SuggestiveImplementation } from '@shared/types';
import { useMeshStore } from '@/store/meshStore';

interface SuggestionsPanelProps {
  onOpenWorkspace: (workspaceId: string) => void;
  onOpenConcept: (conceptId: string) => void;
}

export function SuggestionsPanel({ onOpenWorkspace, onOpenConcept }: SuggestionsPanelProps) {
  const suggestions = useMeshStore((s) => s.suggestions ?? []);

  return (
    <section className="panel suggestions-panel" aria-labelledby="suggestions-heading">
      <div className="panel-header">
        <h2 id="suggestions-heading">Suggestive implementations</h2>
        <span className="panel-meta">{suggestions.length} ranked</span>
      </div>
      <p className="guide-lede">
        Auto-derived from live scans — concrete next steps, sketches, and linked guide concepts.
      </p>
      {suggestions.length === 0 ? (
        <p className="empty-note">Waiting for a scan cycle to propose implementations.</p>
      ) : (
        <ul className="suggestions-impl-list">
          {suggestions.slice(0, 12).map((s) => (
            <SuggestionCard
              key={s.id}
              suggestion={s}
              onOpenWorkspace={onOpenWorkspace}
              onOpenConcept={onOpenConcept}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function SuggestionCard({
  suggestion: s,
  onOpenWorkspace,
  onOpenConcept,
}: {
  suggestion: SuggestiveImplementation;
  onOpenWorkspace: (workspaceId: string) => void;
  onOpenConcept: (conceptId: string) => void;
}) {
  return (
    <li className="suggestion-card">
      <div className="suggestion-card-head">
        <span className={`suggestion-kind ${s.kind}`}>{s.kind}</span>
        <span className="suggestion-priority">{Math.round(s.priority)}</span>
      </div>
      <h3 className="suggestion-title">{s.title}</h3>
      <p className="suggestion-rationale">{s.rationale}</p>
      <p className="suggestion-impl">{s.implementation}</p>
      {s.sketch && (
        <pre className="concept-sample">
          <code>{s.sketch}</code>
        </pre>
      )}
      <div className="related-chips">
        {s.relatedWorkspaceIds.map((id) => (
          <button
            key={id}
            type="button"
            className="related-chip"
            onClick={() => onOpenWorkspace(id)}
          >
            {id.replace(/^workspace-/, '')}
          </button>
        ))}
        {s.relatedConceptIds.map((id) => (
          <button
            key={id}
            type="button"
            className="related-chip"
            onClick={() => onOpenConcept(id)}
          >
            {id}
          </button>
        ))}
      </div>
    </li>
  );
}
