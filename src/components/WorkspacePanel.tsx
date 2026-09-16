import { STATUS_COLORS } from '@shared/types';
import { useMeshStore } from '@/store/meshStore';

interface WorkspacePanelProps {
  onOpenWorkspace: (workspaceId: string) => void;
}

export function WorkspacePanel({ onOpenWorkspace }: WorkspacePanelProps) {
  const workspaces = useMeshStore((s) => s.workspaces);
  const selectedWorkspaceId = useMeshStore((s) => s.selectedWorkspaceId);
  const selectWorkspace = useMeshStore((s) => s.selectWorkspace);

  const selected = workspaces.find((w) => w.id === selectedWorkspaceId) ?? null;

  const handleSelect = (workspaceId: string) => {
    selectWorkspace(workspaceId);
    onOpenWorkspace(workspaceId);
  };

  return (
    <section className="panel" aria-labelledby="workspaces-heading">
      <div className="panel-header">
        <h2 id="workspaces-heading">Workspaces</h2>
        <span className="panel-meta">{workspaces.length} regions</span>
      </div>

      <ul className="workspace-list">
        {workspaces.map((ws) => {
          const color = STATUS_COLORS[ws.status] ?? ws.color;
          return (
            <li key={ws.id}>
              <button
                type="button"
                className={`workspace-item${selectedWorkspaceId === ws.id ? ' selected' : ''}`}
                onClick={() => handleSelect(ws.id)}
              >
                <span className="status-pip" style={{ background: color }} />
                <span className="workspace-name">{ws.name}</span>
                <span className="workspace-score">{Math.round(ws.score)}</span>
              </button>
            </li>
          );
        })}
      </ul>

      {workspaces.length === 0 && (
        <p className="empty-note">Waiting for mesh state from the server.</p>
      )}

      {selected && (
        <div className="workspace-detail">
          <h2>{selected.name}</h2>
          <p>{selected.description}</p>

          <div className="metrics-row">
            <div className="metric">
              <span className="metric-label">Status</span>
              <span className="metric-value" style={{ color: STATUS_COLORS[selected.status] }}>
                {selected.status}
              </span>
            </div>
            <div className="metric">
              <span className="metric-label">Score</span>
              <span className="metric-value">{Math.round(selected.score)}</span>
            </div>
            {Object.entries(selected.metrics)
              .slice(0, 4)
              .map(([key, value]) => (
                <div key={key} className="metric">
                  <span className="metric-label">{key}</span>
                  <span className="metric-value">{String(value)}</span>
                </div>
              ))}
          </div>

          <h2 className="h2" style={{ marginBottom: '0.65rem' }}>
            Findings
          </h2>
          {selected.findings.length === 0 ? (
            <p className="empty-note">No findings in this workspace yet.</p>
          ) : (
            <ul className="findings-list">
              {selected.findings.map((f) => (
                <li key={f.id} className="finding">
                  <div className="finding-title">
                    {f.title}
                    <span className={`severity ${f.severity}`}>{f.severity}</span>
                  </div>
                  <div className="finding-detail">{f.detail}</div>
                  {f.suggestion && (
                    <div className="suggestion">{f.suggestion}</div>
                  )}
                </li>
              ))}
            </ul>
          )}

          {selected.findings.some((f) => f.suggestion) && (
            <>
              <h2 className="h2" style={{ margin: '1.25rem 0 0.65rem' }}>
                Suggestions
              </h2>
              <ul className="suggestions-list">
                {selected.findings
                  .filter((f) => f.suggestion)
                  .map((f) => (
                    <li key={`sug-${f.id}`} className="suggestion">
                      {f.suggestion}
                    </li>
                  ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
