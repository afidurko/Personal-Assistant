import { describe, expect, it } from 'vitest';
import { mkdtemp, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { NeuralMesh } from './neural-mesh.js';
import { PersistentMemory } from './persistent-memory.js';
import { AgentMeshRuntime } from './agent-mesh.js';
import { AGENT_LAYERS, MESH_AGENTS, agentNodeId, layerHubId } from '../../shared/agentLayers.js';
import { STATUS_COLORS, type WorkspaceSnapshot } from '../../shared/types.js';

function snap(partial: Partial<WorkspaceSnapshot> & Pick<WorkspaceSnapshot, 'id' | 'kind'>): WorkspaceSnapshot {
  return {
    name: partial.name ?? partial.kind,
    description: '',
    status: partial.status ?? 'warning',
    score: partial.score ?? 60,
    lastScanAt: new Date().toISOString(),
    findings: partial.findings ?? [
      {
        id: 'f-crit',
        workspaceId: partial.id,
        title: 'Critical stub',
        detail: 'needs loop',
        severity: 'critical',
        category: 'test',
        suggestion: 'Apply fix sketch',
        createdAt: new Date().toISOString(),
      },
    ],
    metrics: {},
    color: STATUS_COLORS.warning,
    pulse: 0.4,
    ...partial,
  };
}

describe('deep agent mesh layers', () => {
  it('seeds layer hubs and agents into the brain map', async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), 'pa-agents-'));
    try {
      const mesh = new NeuralMesh({ dataDir: dir });
      await mesh.load();
      const { nodes, edges } = mesh.getState();
      for (const layer of AGENT_LAYERS) {
        expect(nodes.some((n) => n.id === layerHubId(layer.id) && n.kind === 'layer')).toBe(true);
      }
      for (const agent of MESH_AGENTS) {
        expect(nodes.some((n) => n.id === agentNodeId(agent.id) && n.kind === 'agent')).toBe(true);
      }
      expect(edges.some((e) => e.kind === 'feeds' && e.from === 'layer-commute')).toBe(true);
      expect(edges.some((e) => e.kind === 'loops')).toBe(true);
      expect(nodes.some((n) => n.id === layerHubId('swarm'))).toBe(true);
      expect(nodes.some((n) => n.id === agentNodeId('boss-router'))).toBe(true);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it('issue-fix loop enqueues and attempts repair jobs from critical findings', async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), 'pa-loop-'));
    try {
      const mesh = new NeuralMesh({ dataDir: dir });
      const memory = new PersistentMemory({ dataDir: dir });
      await mesh.load();
      await memory.load();
      const runtime = new AgentMeshRuntime(mesh, memory);

      const workspaces = [
        snap({ id: 'workspace-vulnerability', kind: 'vulnerability', score: 40, status: 'critical' }),
        snap({ id: 'workspace-health', kind: 'health', score: 70, status: 'warning', findings: [] }),
      ];

      const cycle1 = await runtime.runCycle({ workspaces, suggestions: [] });
      expect(cycle1.commutePaths.length).toBeGreaterThan(0);
      expect(cycle1.memoryWrites).toBeGreaterThan(0);
      expect(cycle1.persistedJobs).toBeGreaterThan(0);
      expect(runtime.getJobs().length).toBeGreaterThan(0);

      const cycle2 = await runtime.runCycle({ workspaces, suggestions: [] });
      expect(cycle2.loopActions.length).toBeGreaterThan(0);
      expect(cycle2.loopActions.some((j) => j.attempts >= 1)).toBe(true);
      expect(cycle2.efficiencyGain).toBeGreaterThan(0);

      const traces = memory.getTraces();
      expect(traces.some((t) => t.kind === 'loop' || t.kind === 'agent')).toBe(true);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});
