/** Deep agent layers for neural meshing networks */

import type { BrainRegion, WorkspaceKind } from './types.js';

export type AgentLayerId =
  | 'commute'
  | 'memory'
  | 'persistence'
  | 'issue-loop';

export type AgentRoleId =
  | 'commute-router'
  | 'efficiency-broker'
  | 'memory-consolidator'
  | 'recall-amplifier'
  | 'job-persistence'
  | 'completion-guardian'
  | 'issue-fix-loop'
  | 'regression-sentinel';

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
  /** How this agent improves commute / memory / persistence */
  enhances: Array<'commute' | 'memory' | 'persistence' | 'repair'>;
  region: BrainRegion;
  color: string;
  relatedWorkspaceKinds: WorkspaceKind[];
  /** Max autonomous fix attempts per loop cycle (issue-loop agents) */
  maxLoopAttempts?: number;
}

/** Stacked deep layers — issue-loop is the dedicated repair stratum. */
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
    relatedWorkspaceKinds: ['health', 'improvements'],
  },
  {
    id: 'efficiency-broker',
    layer: 'commute',
    name: 'Efficiency Broker',
    mandate: 'Collapse redundant scan/suggestion paths; batch related findings.',
    enhances: ['commute', 'persistence'],
    region: 'basal_ganglia',
    color: '#29b6f6',
    relatedWorkspaceKinds: ['architecture', 'updates'],
  },
  {
    id: 'memory-consolidator',
    layer: 'memory',
    name: 'Memory Consolidator',
    mandate: 'Promote high-salience scan traces into semantic mesh memory.',
    enhances: ['memory'],
    region: 'hippocampus',
    color: '#9575cd',
    relatedWorkspaceKinds: ['health', 'architecture'],
  },
  {
    id: 'recall-amplifier',
    layer: 'memory',
    name: 'Recall Amplifier',
    mandate: 'Boost activation on memories that match the active job or issue.',
    enhances: ['memory', 'commute'],
    region: 'hippocampus',
    color: '#7e57c2',
    relatedWorkspaceKinds: ['improvements', 'vulnerability'],
  },
  {
    id: 'job-persistence',
    layer: 'persistence',
    name: 'Job Persistence Agent',
    mandate: 'Track open jobs until done; re-queue stalled work into the next cycle.',
    enhances: ['persistence'],
    region: 'striatum',
    color: '#26a69a',
    relatedWorkspaceKinds: ['improvements', 'updates'],
  },
  {
    id: 'completion-guardian',
    layer: 'persistence',
    name: 'Completion Guardian',
    mandate: 'Refuse to close a job while critical findings remain unaddressed.',
    enhances: ['persistence', 'repair'],
    region: 'striatum',
    color: '#00897b',
    relatedWorkspaceKinds: ['vulnerability', 'health'],
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
    relatedWorkspaceKinds: ['vulnerability', 'architecture', 'health'],
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
    relatedWorkspaceKinds: ['health', 'updates', 'vulnerability'],
    maxLoopAttempts: 3,
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
