import type { Finding, WorkspaceSnapshot } from '@shared/types';
import { STATUS_COLORS } from '@shared/types';
import { useMeshStore } from '@/store/meshStore';

interface NeedsAttentionPanelProps {
  onOpenWorkspace: (workspaceId: string) => void;
  onFocusNode?: (nodeId: string) => void;
  onRunAgentCycle?: () => void;
}

/** Cam Needs Attention tab — cross-workspace queue + coding workspace connectivity. */
export function NeedsAttentionPanel({
  onOpenWorkspace,
  onFocusNode,
  onRunAgentCycle,
}: NeedsAttentionPanelProps) {
  const workspaces = useMeshStore((s) => s.workspaces);
  const attention =
    workspaces.find((w) => w.kind === 'needs_attention') ??
    workspaces.find((w) => w.id === 'workspace-needs-attention') ??
    null;
  const loopJobs = useMeshStore((s) => s.loopJobs ?? []);
  const openJobs = loopJobs.filter((j) => j.status !== 'fixed');

  const queue = attention
    ? [...attention.findings]
        .filter((f) => f.severity !== 'info')
        .sort((a, b) => severityRank(b.severity) - severityRank(a.severity))
    : [];

  const connected = Number(attention?.metrics.connectedWorkspaces ?? 0);
  const total = Number(attention?.metrics.codingWorkspaceCount ?? 0);
  const color = attention
    ? STATUS_COLORS[attention.status] ?? attention.color
    : STATUS_COLORS.idle;

  return (
    <section className="panel needs-attention-panel" aria-labelledby="needs-attention-heading">
      <div className="panel-header">
        <h2 id="needs-attention-heading">Needs Attention</h2>
        <span className="panel-meta">
          {queue.length} open · {connected}/{total || '—'} workspaces
        </span>
      </div>
      <p className="guide-lede">
        Automates the attention tab across every coding workspace — triage, connect, dispatch.
        Aaron gates stay on kill / enhance / outbound.
      </p>

      <div className="metrics-row">
        <div className="metric">
          <span className="metric-label">Queue</span>
          <span className="metric-value" style={{ color }}>
            {queue.length}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Score</span>
          <span className="metric-value">
            {attention ? Math.round(attention.score) : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Connected</span>
          <span className="metric-value">
            {total ? `${connected}/${total}` : '—'}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Open loops</span>
          <span className="metric-value">{openJobs.length}</span>
        </div>
      </div>

      <div className="guide-controls">
        {attention && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => onOpenWorkspace(attention.id)}
          >
            Open workspace
          </button>
        )}
        {onFocusNode && (
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => onFocusNode('agent-attention-triage')}
          >
            Focus triage agent
          </button>
        )}
        {onRunAgentCycle && (
          <button type="button" className="btn" onClick={onRunAgentCycle}>
            Run agent cycle
          </button>
        )}
      </div>

      {!attention ? (
        <p className="empty-note">Waiting for a scan cycle to populate the Needs Attention queue.</p>
      ) : queue.length === 0 ? (
        <p className="empty-note">Queue clear — all connected workspaces look calm.</p>
      ) : (
        <ul className="needs-attention-list">
          {queue.slice(0, 16).map((f) => (
            <AttentionRow key={f.id} finding={f} workspaces={workspaces} onOpenWorkspace={onOpenWorkspace} />
          ))}
        </ul>
      )}
    </section>
  );
}

function AttentionRow({
  finding: f,
  workspaces,
  onOpenWorkspace,
}: {
  finding: Finding;
  workspaces: WorkspaceSnapshot[];
  onOpenWorkspace: (workspaceId: string) => void;
}) {
  const related = (f.relatedNodeIds ?? [])
    .filter((id) => id.startsWith('workspace-'))
    .map((id) => workspaces.find((w) => w.id === id))
    .filter(Boolean) as WorkspaceSnapshot[];

  return (
    <li className={`needs-attention-item severity-${f.severity}`}>
      <div className="suggestion-card-head">
        <span className={`suggestion-kind needs-attention`}>{f.category}</span>
        <span className={`severity ${f.severity}`}>{f.severity}</span>
      </div>
      <div className="finding-title">{f.title}</div>
      <div className="finding-detail">{f.detail}</div>
      {f.suggestion && <div className="suggestion">{f.suggestion}</div>}
      {related.length > 0 && (
        <div className="related-chips">
          {related.map((w) => (
            <button
              key={w.id}
              type="button"
              className="related-chip"
              onClick={() => onOpenWorkspace(w.id)}
            >
              {w.name}
            </button>
          ))}
        </div>
      )}
    </li>
  );
}

function severityRank(s: Finding['severity']): number {
  switch (s) {
    case 'critical':
      return 5;
    case 'high':
      return 4;
    case 'medium':
      return 3;
    case 'low':
      return 2;
    default:
      return 1;
  }
}
