/** Shared domain types for Personal Assistant neural mesh */

export type WorkspaceKind =
  | 'health'
  | 'architecture'
  | 'vulnerability'
  | 'updates'
  | 'improvements'
  | 'agi_research'
  | 'swarm';

export type ScanStatus = 'idle' | 'scanning' | 'healthy' | 'warning' | 'critical' | 'stale';

export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical';

export type MeshEdgeKind =
  | 'depends_on'
  | 'feeds'
  | 'correlates'
  | 'suggests'
  | 'monitors'
  | 'hebbian'
  | 'commutes'
  | 'repairs'
  | 'persists'
  | 'loops'
  | 'assigns'
  | 'broadcasts'
  | 'spawns'
  | 'terminates'
  | 'inherits';

export interface Finding {
  id: string;
  workspaceId: string;
  title: string;
  detail: string;
  severity: Severity;
  category: string;
  suggestion?: string;
  relatedNodeIds?: string[];
  createdAt: string;
}

export interface WorkspaceSnapshot {
  id: string;
  kind: WorkspaceKind;
  name: string;
  description: string;
  status: ScanStatus;
  score: number; // 0–100
  lastScanAt: string | null;
  findings: Finding[];
  metrics: Record<string, number | string | boolean>;
  color: string;
  pulse: number; // 0–1 animation intensity
}

export interface BrainNode {
  id: string;
  label: string;
  workspaceId: string | null;
  /** Optional Swift Guide concept id when this node is a tour concept */
  conceptId?: string | null;
  /** Optional agent / layer id */
  agentId?: string | null;
  layerId?: string | null;
  region: BrainRegion;
  x: number; // 0–1 normalized
  y: number;
  activation: number; // 0–1
  status: ScanStatus;
  color: string;
  radius: number;
  tags: string[];
  interactive: boolean;
  /** Distinguishes workspace/hub vs Swift Guide concept / agent nodes */
  kind?: 'workspace' | 'hub' | 'concept' | 'agent' | 'layer';
}

export type BrainRegion =
  | 'cortex'
  | 'hippocampus'
  | 'amygdala'
  | 'thalamus'
  | 'prefrontal'
  | 'cerebellum'
  | 'insula'
  | 'basal_ganglia'
  | 'striatum'
  | 'repair_loop'
  | 'swarm_bus';

export interface MeshEdge {
  id: string;
  from: string;
  to: string;
  kind: MeshEdgeKind;
  weight: number; // 0–1
  bidirectional?: boolean;
  label?: string;
}

export interface MemoryTrace {
  id: string;
  kind: 'episodic' | 'semantic' | 'procedural' | 'scan' | 'agent' | 'loop' | 'swarm';
  content: string;
  workspaceIds: string[];
  nodeIds: string[];
  salience: number;
  createdAt: string;
  lastAccessedAt: string;
  decay: number;
  tags: string[];
}

export type LoopJobStatus = 'queued' | 'running' | 'verifying' | 'fixed' | 'escalated' | 'blocked';

export interface LoopJob {
  id: string;
  title: string;
  detail: string;
  severity: Severity;
  status: LoopJobStatus;
  attempts: number;
  maxAttempts: number;
  sourceFindingId?: string;
  sourceWorkspaceId?: string;
  assignedAgentId: string;
  fixSketch?: string;
  lastError?: string;
  createdAt: string;
  updatedAt: string;
}

export interface AgentCycleResult {
  commutePaths: Array<{ from: string; to: string; weight: number; label: string }>;
  memoryWrites: number;
  persistedJobs: number;
  loopActions: LoopJob[];
  efficiencyGain: number;
  /** HAAS→Cam swarm cycle summary (privileges / lineage / boss-worker) */
  swarm?: {
    spawns: number;
    assigns: number;
    broadcasts: number;
    denials: number;
    terminations: number;
    activeAgents: number;
    namespacesTouched: string[];
  } | null;
}

export interface NeuralMeshState {
  nodes: BrainNode[];
  edges: MeshEdge[];
  workspaces: WorkspaceSnapshot[];
  memory: MemoryTrace[];
  scanning: boolean;
  lastCycleAt: string | null;
  cycleCount: number;
  /** Active Swift Guide concept (tour), if any */
  activeConceptId?: string | null;
  guideStep?: number;
  /** Ranked actionable suggestions derived from latest scans */
  suggestions?: SuggestiveImplementation[];
  /** Open/looping jobs owned by persistence + issue-loop agents */
  loopJobs?: LoopJob[];
  /** Last agent-mesh cycle summary */
  lastAgentCycle?: AgentCycleResult | null;
  /** Cam background self-improve tasks */
  camSelfTasks?: Array<{
    id: string;
    title: string;
    detail: string;
    status: string;
    neuron: string;
    severity: string;
  }>;
}

export type SuggestionKind =
  | 'security'
  | 'architecture'
  | 'ops'
  | 'learning'
  | 'dependency'
  | 'dx'
  | 'agent-commute'
  | 'agent-memory'
  | 'agent-persistence'
  | 'agent-repair'
  | 'swarm-privilege'
  | 'swarm-lineage'
  | 'swarm-tooling'
  | 'cam-enhance'
  | 'research-memory'
  | 'cam-reason'
  | 'identity-voice'
  | 'presence-voice'
  | 'identity'
  | 'api-catalog';

export interface SuggestiveImplementation {
  id: string;
  kind: SuggestionKind;
  title: string;
  rationale: string;
  implementation: string;
  sketch?: string;
  priority: number;
  relatedWorkspaceIds: string[];
  relatedConceptIds: string[];
  sourceFindingIds: string[];
}

export interface ScanCycleResult {
  workspaces: WorkspaceSnapshot[];
  findings: Finding[];
  memoryWrites: MemoryTrace[];
  activationDeltas: Record<string, number>;
  colorMap: Record<string, string>;
}

export interface WsServerMessage {
  type:
    | 'state'
    | 'scan_tick'
    | 'scan_complete'
    | 'memory_update'
    | 'node_focus'
    | 'guide_focus'
    | 'agent_cycle'
    | 'loop_update'
    | 'autonomy_update';
  payload: unknown;
  at: string;
}

export interface WsClientMessage {
  type:
    | 'start_scan'
    | 'stop_scan'
    | 'focus_node'
    | 'open_workspace'
    | 'reinforce'
    | 'query_memory'
    | 'open_concept'
    | 'guide_next'
    | 'guide_prev'
    | 'guide_start'
    | 'run_agent_cycle'
    | 'start_issue_loop'
    | 'stop_issue_loop';
  payload?: unknown;
}

/** Status → brain-map color palette */
export const STATUS_COLORS: Record<ScanStatus, string> = {
  idle: '#6b7c8a',
  scanning: '#3db8ff',
  healthy: '#2ec27e',
  warning: '#e6a817',
  critical: '#e35d5d',
  stale: '#8a7a9a',
};

export const WORKSPACE_META: Record<
  WorkspaceKind,
  { name: string; description: string; region: BrainRegion; defaultColor: string }
> = {
  health: {
    name: 'System Health',
    description: 'Continuous vitals: uptime, resources, process health, service readiness.',
    region: 'thalamus',
    defaultColor: '#2ec27e',
  },
  architecture: {
    name: 'Architecture Map',
    description: 'Structural topology: modules, coupling, layering, dependency health.',
    region: 'prefrontal',
    defaultColor: '#5b8def',
  },
  vulnerability: {
    name: 'Vulnerability Scan',
    description: 'Threat surface: dependency CVEs, config risks, insecure patterns.',
    region: 'amygdala',
    defaultColor: '#e35d5d',
  },
  updates: {
    name: 'Updates & Drift',
    description: 'Package freshness, lockfile drift, outdated runtimes and tooling.',
    region: 'cerebellum',
    defaultColor: '#e6a817',
  },
  improvements: {
    name: 'Improvement Engine',
    description: 'Actionable suggestions synthesized from health, vulns, and architecture.',
    region: 'insula',
    defaultColor: '#4ecdc4',
  },
  agi_research: {
    name: 'AGI Research Scan',
    description: 'Daily AI/AGI paper scan → Cam enhancement proposals (Aaron gates apply).',
    region: 'hippocampus',
    defaultColor: '#9b59b6',
  },
  swarm: {
    name: 'Swarm Mesh',
    description:
      'Privilege inheritance, lineage terminate, and boss/worker bus across all agents and workspaces.',
    region: 'swarm_bus',
    defaultColor: '#1abc9c',
  },
};
