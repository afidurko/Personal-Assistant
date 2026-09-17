import { AGENT_LAYERS, MESH_AGENTS } from '@shared/agentLayers';
import type { LoopJob } from '@shared/types';
import { useMeshStore } from '@/store/meshStore';

interface AgentLayersPanelProps {
  onFocusNode: (nodeId: string) => void;
  onRunAgentCycle: () => void;
  onStartIssueLoop: () => void;
  onStopIssueLoop: () => void;
}

export function AgentLayersPanel({
  onFocusNode,
  onRunAgentCycle,
  onStartIssueLoop,
  onStopIssueLoop,
}: AgentLayersPanelProps) {
  const loopJobs = useMeshStore((s) => s.loopJobs ?? []);
  const lastAgentCycle = useMeshStore((s) => s.lastAgentCycle);
  const selectedNodeId = useMeshStore((s) => s.selectedNodeId);

  const openJobs = loopJobs.filter((j) => j.status !== 'fixed');
  const issueLoopAgents = MESH_AGENTS.filter((a) => a.layer === 'issue-loop');

  return (
    <section className="panel agent-layers-panel" aria-labelledby="agent-layers-heading">
      <div className="panel-header">
        <h2 id="agent-layers-heading">Deep agent mesh</h2>
        <span className="panel-meta">{AGENT_LAYERS.length} layers</span>
      </div>
      <p className="guide-lede">
        Stacked neural agents for task commute, memory, persistence, and a dedicated
        automated issue-fix loop.
      </p>

      <div className="guide-controls">
        <button type="button" className="btn" onClick={onRunAgentCycle}>
          Run agent cycle
        </button>
        <button type="button" className="btn btn-ghost" onClick={onStartIssueLoop}>
          Arm issue loop
        </button>
        <button type="button" className="btn btn-ghost" onClick={onStopIssueLoop}>
          Disarm loop
        </button>
      </div>

      {lastAgentCycle && (
        <div className="metrics-row agent-metrics">
          <div className="metric">
            <span className="metric-label">Efficiency</span>
            <span className="metric-value">
              {Math.round(lastAgentCycle.efficiencyGain * 100)}%
            </span>
          </div>
          <div className="metric">
            <span className="metric-label">Commute paths</span>
            <span className="metric-value">{lastAgentCycle.commutePaths.length}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Memory writes</span>
            <span className="metric-value">{lastAgentCycle.memoryWrites}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Loop actions</span>
            <span className="metric-value">{lastAgentCycle.loopActions.length}</span>
          </div>
        </div>
      )}

      <ol className="layer-stack">
        {AGENT_LAYERS.map((layer) => (
          <li key={layer.id} className={`layer-card depth-${layer.depth}`}>
            <button
              type="button"
              className={`layer-hit${selectedNodeId === `layer-${layer.id}` ? ' selected' : ''}`}
              onClick={() => onFocusNode(`layer-${layer.id}`)}
            >
              <span className="layer-swatch" style={{ background: layer.color }} />
              <span className="layer-depth">D{layer.depth}</span>
              <span className="layer-name">{layer.name}</span>
            </button>
            <p className="layer-purpose">{layer.purpose}</p>
            <ul className="agent-mini-list">
              {MESH_AGENTS.filter((a) => a.layer === layer.id).map((agent) => (
                <li key={agent.id}>
                  <button
                    type="button"
                    className={`agent-mini${selectedNodeId === `agent-${agent.id}` ? ' selected' : ''}`}
                    onClick={() => onFocusNode(`agent-${agent.id}`)}
                  >
                    <span className="concept-swatch" style={{ background: agent.color }} />
                    {agent.name}
                  </button>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>

      <div className="issue-loop-section">
        <h2 className="h2">Issue-fix loop jobs</h2>
        <p className="guide-lede">
          {issueLoopAgents.map((a) => a.name).join(' · ')} — detect, attempt, verify, escalate.
        </p>
        {openJobs.length === 0 ? (
          <p className="empty-note">No open loop jobs. Armed loops enqueue work from scan findings.</p>
        ) : (
          <ul className="loop-job-list">
            {openJobs.slice(0, 10).map((job) => (
              <LoopJobRow key={job.id} job={job} />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function LoopJobRow({ job }: { job: LoopJob }) {
  return (
    <li className={`loop-job status-${job.status}`}>
      <div className="suggestion-card-head">
        <span className={`suggestion-kind ${job.severity}`}>{job.status}</span>
        <span className="suggestion-priority">
          {job.attempts}/{job.maxAttempts}
        </span>
      </div>
      <div className="finding-title">{job.title}</div>
      <div className="finding-detail">{job.detail}</div>
      {job.fixSketch && (
        <pre className="concept-sample">
          <code>{job.fixSketch}</code>
        </pre>
      )}
      {job.lastError && <p className="loop-error">{job.lastError}</p>}
    </li>
  );
}
