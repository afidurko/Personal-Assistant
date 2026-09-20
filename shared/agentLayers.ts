/** Deep agent layers for neural meshing networks */

import type { BrainRegion, WorkspaceKind } from './types.js';

export type AgentLayerId =
  | 'commute'
  | 'memory'
  | 'persistence'
  | 'issue-loop'
  | 'attention'
  | 'swarm';

export type AgentRoleId =
  | 'commute-router'
  | 'efficiency-broker'
  | 'memory-consolidator'
  | 'recall-amplifier'
  | 'job-persistence'
  | 'completion-guardian'
  | 'issue-fix-loop'
  | 'regression-sentinel'
  | 'attention-triage'
  | 'workspace-connector'
  | 'attention-dispatcher'
  | 'privilege-broker'
  | 'lineage-guardian'
  | 'boss-router'
  | 'tool-broker';

export interface AgentLayerMeta {
  id: AgentLayerId;
  name: string;
  depth: number; // 0 = near sensory/workspaces, higher = deeper mesh
  region: BrainRegion;
  color: string;
  purpose: string;
}

export interface MeshAgentDef {
  id: AgentRoleId;
  layer: AgentLayerId;
  name: string;
  mandate: string;
  /** How this agent improves commute / memory / persistence / swarm */
  enhances: Array<'commute' | 'memory' | 'persistence' | 'repair' | 'swarm'>;
  region: BrainRegion;
  color: string;
  relatedWorkspaceKinds: WorkspaceKind[];
  /** Max autonomous fix attempts per loop cycle (issue-loop agents) */
  maxLoopAttempts?: number;
}

/** Stacked deep layers — swarm is the privilege / lineage / boss-worker stratum. */
export const AGENT_LAYERS: AgentLayerMeta[] = [
  {
    id: 'commute',
    name: 'Task Commute Layer',
    depth: 1,
    region: 'basal_ganglia',
    color: '#6ec6ff',
    purpose:
      'Route tasks through the shortest high-confidence mesh paths so work moves with less friction.',
  },
  {
    id: 'memory',
    name: 'Memory Enhancement Layer',
    depth: 2,
    region: 'hippocampus',
    color: '#b39ddb',
    purpose:
      'Consolidate scan and job traces into durable semantic memory for faster recall on the next commute.',
  },
  {
    id: 'persistence',
    name: 'Job Persistence Layer',
    depth: 3,
    region: 'striatum',
    color: '#80cbc4',
    purpose:
      'Keep jobs and tasks alive across cycles until completion criteria are met — no silent dropouts.',
  },
  {
    id: 'issue-loop',
    name: 'Automated Issue-Fix Loop',
    depth: 4,
    region: 'repair_loop',
    color: '#ff8a65',
    purpose:
      'Dedicated looping agents that detect regressions and findings, attempt fixes, re-verify, and persist outcomes.',
  },
  {
    id: 'attention',
    name: 'Needs Attention Layer',
    depth: 5,
    region: 'prefrontal',
    color: '#f0a04b',
    purpose:
      'Triage and clear Needs Attention items across every coding workspace; escalate only Aaron-gated decisions.',
  },
  {
    id: 'swarm',
    name: 'Swarm Privilege & Bus Layer',
    depth: 6,
    region: 'swarm_bus',
    color: '#1abc9c',
    purpose:
      'HAAS→Cam: privilege inheritance, lineage terminate, and boss/worker synapse ops shared by every agent and workspace.',
  },
];

export const MESH_AGENTS: MeshAgentDef[] = [
  {
    id: 'commute-router',
    layer: 'commute',
    name: 'Commute Router',
    mandate: 'Rank workspace→agent→memory hops by latency and success weight.',
    enhances: ['commute'],
    region: 'basal_ganglia',
    color: '#4fc3f7',
    relatedWorkspaceKinds: ['health', 'improvements', 'swarm'],
  },
  {
    id: 'efficiency-broker',
    layer: 'commute',
    name: 'Efficiency Broker',
    mandate: 'Collapse redundant scan/suggestion paths; batch related findings.',
    enhances: ['commute', 'persistence'],
    region: 'basal_ganglia',
    color: '#29b6f6',
    relatedWorkspaceKinds: ['architecture', 'updates', 'swarm'],
  },
  {
    id: 'memory-consolidator',
    layer: 'memory',
    name: 'Memory Consolidator',
    mandate: 'Promote high-salience scan traces into semantic mesh memory.',
    enhances: ['memory'],
    region: 'hippocampus',
    color: '#9575cd',
    relatedWorkspaceKinds: ['health', 'architecture', 'swarm', 'agi_research'],
  },
  {
    id: 'recall-amplifier',
    layer: 'memory',
    name: 'Recall Amplifier',
    mandate: 'Boost activation on memories that match the active job or issue.',
    enhances: ['memory', 'commute'],
    region: 'hippocampus',
    color: '#7e57c2',
    relatedWorkspaceKinds: ['improvements', 'vulnerability', 'swarm'],
  },
  {
    id: 'job-persistence',
    layer: 'persistence',
    name: 'Job Persistence Agent',
    mandate: 'Track open jobs until done; re-queue stalled work into the next cycle.',
    enhances: ['persistence'],
    region: 'striatum',
    color: '#26a69a',
    relatedWorkspaceKinds: ['improvements', 'updates', 'swarm'],
  },
  {
    id: 'completion-guardian',
    layer: 'persistence',
    name: 'Completion Guardian',
    mandate: 'Refuse to close a job while critical findings remain unaddressed.',
    enhances: ['persistence', 'repair'],
    region: 'striatum',
    color: '#00897b',
    relatedWorkspaceKinds: ['vulnerability', 'health', 'swarm'],
  },
  {
    id: 'issue-fix-loop',
    layer: 'issue-loop',
    name: 'Issue Fix Loop',
    mandate:
      'Autonomously loop: detect issue → propose fix sketch → verify → persist; escalate if attempts exhaust.',
    enhances: ['repair', 'persistence'],
    region: 'repair_loop',
    color: '#ff7043',
    relatedWorkspaceKinds: ['vulnerability', 'architecture', 'health', 'swarm'],
    maxLoopAttempts: 5,
  },
  {
    id: 'regression-sentinel',
    layer: 'issue-loop',
    name: 'Regression Sentinel',
    mandate: 'Watch score deltas across cycles; trigger the fix loop when health drops.',
    enhances: ['repair', 'commute'],
    region: 'repair_loop',
    color: '#f4511e',
    relatedWorkspaceKinds: ['health', 'updates', 'vulnerability', 'swarm', 'needs_attention'],
    maxLoopAttempts: 3,
  },
  {
    id: 'attention-triage',
    layer: 'attention',
    name: 'Attention Triage',
    mandate:
      'Rank Needs Attention queue items: auto-clearable vs Aaron-gated (kill, enhance, outbound).',
    enhances: ['repair', 'commute'],
    region: 'prefrontal',
    color: '#f6b26b',
    relatedWorkspaceKinds: [
      'needs_attention',
      'improvements',
      'health',
      'vulnerability',
      'swarm',
    ],
    maxLoopAttempts: 4,
  },
  {
    id: 'workspace-connector',
    layer: 'attention',
    name: 'Workspace Connector',
    mandate:
      'Verify every registry coding workspace is connected; report empty submodules without inventing remotes.',
    enhances: ['commute', 'persistence'],
    region: 'prefrontal',
    color: '#e69138',
    relatedWorkspaceKinds: ['needs_attention', 'health', 'updates', 'swarm'],
  },
  {
    id: 'attention-dispatcher',
    layer: 'attention',
    name: 'Attention Dispatcher',
    mandate:
      'Route auto-clearable attention items via choose-workspace / issue-loop / swarm assign across all workspaces.',
    enhances: ['repair', 'commute', 'swarm'],
    region: 'prefrontal',
    color: '#d0791c',
    relatedWorkspaceKinds: [
      'needs_attention',
      'improvements',
      'architecture',
      'vulnerability',
      'agi_research',
      'swarm',
    ],
    maxLoopAttempts: 5,
  },
  {
    id: 'privilege-broker',
    layer: 'swarm',
    name: 'Privilege Broker',
    mandate:
      'Enforce privilege inheritance on every spawn: child ⊆ parent; never grant aaron_only privileges.',
    enhances: ['swarm', 'persistence'],
    region: 'swarm_bus',
    color: '#16a085',
    relatedWorkspaceKinds: ['swarm', 'health', 'architecture', 'improvements', 'agi_research'],
  },
  {
    id: 'lineage-guardian',
    layer: 'swarm',
    name: 'Lineage Guardian',
    mandate: 'Track agent lineage; allow ancestors (or Aaron) to terminate descendants safely.',
    enhances: ['swarm', 'repair'],
    region: 'swarm_bus',
    color: '#0e9f6e',
    relatedWorkspaceKinds: ['swarm', 'vulnerability', 'health', 'updates'],
  },
  {
    id: 'boss-router',
    layer: 'swarm',
    name: 'Boss/Worker Router',
    mandate: 'assign_task / broadcast / resolve_task / send_message across all workspace agents.',
    enhances: ['swarm', 'commute'],
    region: 'swarm_bus',
    color: '#048c7f',
    relatedWorkspaceKinds: [
      'swarm',
      'health',
      'architecture',
      'vulnerability',
      'updates',
      'improvements',
      'agi_research',
    ],
  },
  {
    id: 'tool-broker',
    layer: 'swarm',
    name: 'Tool Broker',
    mandate: 'tool-creator → tool-user registry; privilege-gated tool runs shared via mesh/tools.',
    enhances: ['swarm', 'memory'],
    region: 'swarm_bus',
    color: '#117a65',
    relatedWorkspaceKinds: ['swarm', 'architecture', 'updates', 'improvements'],
  },
];

export function agentNodeId(id: AgentRoleId): string {
  return `agent-${id}`;
}

export function layerHubId(id: AgentLayerId): string {
  return `layer-${id}`;
}

export function isAgentNodeId(nodeId: string): boolean {
  return nodeId.startsWith('agent-') || nodeId.startsWith('layer-');
}
