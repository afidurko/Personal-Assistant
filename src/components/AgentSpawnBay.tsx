import { AGENT_LAYERS, MESH_AGENTS } from '@shared/agentLayers';
import type { LoopJob } from '@shared/types';
import { useMeshStore } from '@/store/meshStore';

interface AgentSpawnBayProps {
  onFocusNode: (nodeId: string) => void;
  onRunAgentCycle: () => void;
  onStartIssueLoop: () => void;
  onStopIssueLoop: () => void;
}

export function AgentSpawnBay({
  onFocusNode,
  onRunAgentCycle,
  onStartIssueLoop,
  onStopIssueLoop,
}: AgentSpawnBayProps) {
  const loopJobs = useMeshStore((s) => s.loopJobs ?? []);
  const lastAgentCycle = useMeshStore((s) => s.lastAgentCycle);
  const selectedNodeId = useMeshStore((s) => s.selectedNodeId);
  const selfTasks = useMeshStore((s) => s.camSelfTasks ?? []);

  const openJobs = loopJobs.filter((j) => j.status !== 'fixed');
  const openSelf = selfTasks.filter((t) => t.status !== 'done');

  return (
    <section className="spawn-bay" aria-labelledby="spawn-bay-heading">
      <div className="spawn-bay-intro">
        <h2 id="spawn-bay-heading">Cam &amp; her agents</h2>
        <p>
          Room for Cam’s standing layers plus unlimited spawn lanes. She keeps creating improve
          tasks for herself in the background while the cortex stays live.
        </p>
        <div className="spawn-capacity">
          <span>
            Self-task slots · {openSelf.length}/64
          </span>
          <span>
            Loop jobs · {openJobs.length}/80
          </span>
          <span>Layers · {AGENT_LAYERS.length}</span>
          <span>Agents · {MESH_AGENTS.length}</span>
        </div>
        <div className="guide-controls">
          <button type="button" className="btn" onClick={onRunAgentCycle}>
            Run agent cycle
          </button>
          <button type="button" className="btn btn-ghost" onClick={onStartIssueLoop}>
            Arm issue loop
          </button>
          <button type="button" className="btn btn-ghost" onClick={onStopIssueLoop}>
            Disarm
          </button>
        </div>
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

      <div className="spawn-grid">
        <div className="spawn-column">
          <h3 className="h2">Cam self-tasks</h3>
          {openSelf.length === 0 ? (
            <p className="empty-note">Autonomy warming up — tasks will appear as Cam ticks.</p>
          ) : (
            <ul className="spawn-list">
              {openSelf.slice(0, 16).map((t) => (
                <li key={t.id} className={`spawn-item status-${t.status}`}>
                  <span className={`suggestion-kind ${t.severity}`}>{t.status}</span>
                  <div className="finding-title">{t.title}</div>
                  <div className="finding-detail">{t.detail}</div>
                  <div className="spawn-meta">{t.neuron}</div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="spawn-column">
          <h3 className="h2">Agent layers</h3>
          <ol className="layer-stack roomy">
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
        </div>

        <div className="spawn-column">
          <h3 className="h2">Issue-fix loop jobs</h3>
          {openJobs.length === 0 ? (
            <p className="empty-note">No open loop jobs. Armed loops enqueue from scan findings.</p>
          ) : (
            <ul className="loop-job-list">
              {openJobs.slice(0, 16).map((job) => (
                <LoopJobRow key={job.id} job={job} />
              ))}
            </ul>
          )}
        </div>
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
    </li>
  );
}
