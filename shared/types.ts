/** Shared domain types for Personal Assistant neural mesh */

export type WorkspaceKind =
  | 'health'
  | 'architecture'
  | 'vulnerability'
  | 'updates'
  | 'improvements';

export type ScanStatus = 'idle' | 'scanning' | 'healthy' | 'warning' | 'critical' | 'stale';

export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical';

export type MeshEdgeKind =
  | 'depends_on'
  | 'feeds'
  | 'correlates'
  | 'suggests'
  | 'monitors'
  | 'hebbian';

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
  region: BrainRegion;
  x: number; // 0–1 normalized
  y: number;
  activation: number; // 0–1
  status: ScanStatus;
  color: string;
  radius: number;
  tags: string[];
  interactive: boolean;
}

export type BrainRegion =
  | 'cortex'
  | 'hippocampus'
  | 'amygdala'
  | 'thalamus'
  | 'prefrontal'
  | 'cerebellum'
  | 'insula';

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
  kind: 'episodic' | 'semantic' | 'procedural' | 'scan';
  content: string;
  workspaceIds: string[];
  nodeIds: string[];
  salience: number;
  createdAt: string;
  lastAccessedAt: string;
  decay: number;
  tags: string[];
}

export interface NeuralMeshState {
  nodes: BrainNode[];
  edges: MeshEdge[];
  workspaces: WorkspaceSnapshot[];
  memory: MemoryTrace[];
  scanning: boolean;
  lastCycleAt: string | null;
  cycleCount: number;
}

export interface ScanCycleResult {
  workspaces: WorkspaceSnapshot[];
  findings: Finding[];
  memoryWrites: MemoryTrace[];
  activationDeltas: Record<string, number>;
  colorMap: Record<string, string>;
}

export interface WsServerMessage {
  type: 'state' | 'scan_tick' | 'scan_complete' | 'memory_update' | 'node_focus';
  payload: unknown;
  at: string;
}

export interface WsClientMessage {
  type: 'start_scan' | 'stop_scan' | 'focus_node' | 'open_workspace' | 'reinforce' | 'query_memory';
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
};
