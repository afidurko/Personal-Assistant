import { describe, expect, it } from 'vitest';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { NeuralMesh } from './neural-mesh.js';
import { PersistentMemory } from './persistent-memory.js';
import { AgentMeshRuntime } from './agent-mesh.js';
import { SwarmRuntime } from './swarm-runtime.js';
import { AGENT_LAYERS, MESH_AGENTS, agentNodeId, layerHubId } from '../../shared/agentLayers.js';
import {
  PrivilegeError,
  createChiefNode,
  loadPrivilegeCatalog,
  mayTerminate,
  spawnChild,
} from '../../shared/swarmPrivileges.js';
import { STATUS_COLORS, type WorkspaceSnapshot } from '../../shared/types.js';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

function snap(
  partial: Partial<WorkspaceSnapshot> & Pick<WorkspaceSnapshot, 'id' | 'kind'>,
): WorkspaceSnapshot {
  return {
    name: partial.name ?? partial.kind,
    description: '',
    status: partial.status ?? 'warning',
    score: partial.score ?? 60,
    lastScanAt: new Date().toISOString(),
    findings: partial.findings ?? [],
    metrics: {},
    color: STATUS_COLORS.warning,
    pulse: 0.4,
    ...partial,
  };
}

describe('swarm privileges', () => {
  it('enforces subset inheritance and blocks aaron_only', () => {
    const catalog = loadPrivilegeCatalog(ROOT);
    const chief = createChiefNode(catalog);
    const broker = spawnChild({ parent: chief, role: 'capability-broker', catalog });
    expect(broker.level).toBe(2);
    expect(broker.privileges.every((p) => chief.privileges.includes(p))).toBe(true);

    expect(() =>
      spawnChild({
        parent: broker,
        role: 'rogue',
        requested: ['kill_master'],
        catalog,
      }),
    ).toThrow(PrivilegeError);

    const worker = spawnChild({ parent: broker, role: 'task-executor', catalog });
    expect(mayTerminate(broker, worker)).toBe(true);
    expect(mayTerminate(worker, broker)).toBe(false);
    expect(mayTerminate({ id: 'Aaron', isAaron: true }, worker)).toBe(true);
  });
});

describe('swarm neural mesh integration', () => {
  it('seeds swarm layer + agents and merges into existing mesh', async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), 'pa-swarm-mesh-'));
    try {
      const mesh = new NeuralMesh({ dataDir: dir });
      await mesh.load();
      expect(mesh.getState().nodes.some((n) => n.id === layerHubId('swarm'))).toBe(true);
      expect(mesh.getState().nodes.some((n) => n.id === agentNodeId('privilege-broker'))).toBe(true);
      expect(mesh.getState().nodes.some((n) => n.id === 'ws-swarm')).toBe(true);
      for (const layer of AGENT_LAYERS) {
        expect(mesh.getState().nodes.some((n) => n.id === layerHubId(layer.id))).toBe(true);
      }
      for (const agent of MESH_AGENTS) {
        expect(mesh.getState().nodes.some((n) => n.id === agentNodeId(agent.id))).toBe(true);
      }
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it('runs swarm cycle into memory namespaces across all workspaces', async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), 'pa-swarm-rt-'));
    try {
      const mesh = new NeuralMesh({ dataDir: dir });
      const memory = new PersistentMemory({ dataDir: dir });
      await mesh.load();
      await memory.load();
      const swarm = new SwarmRuntime(mesh, memory, dir, ROOT);
      await swarm.load();

      const workspaces = [
        snap({ id: 'workspace-health', kind: 'health', score: 55 }),
        snap({ id: 'workspace-swarm', kind: 'swarm', score: 80 }),
        snap({ id: 'workspace-agi-research', kind: 'agi_research', score: 70 }),
      ];

      const result = await swarm.runCycle({ workspaces });
      expect(result.activeAgents).toBeGreaterThan(1);
      expect(result.denials).toBeGreaterThan(0);
      expect(result.assigns).toBeGreaterThan(0);
      expect(result.namespacesTouched).toEqual(
        expect.arrayContaining(['mesh/agent-lineage', 'mesh/tools', 'mesh/swarm/bus']),
      );

      const traces = memory.getTraces();
      expect(traces.some((t) => t.kind === 'swarm')).toBe(true);
      expect(traces.some((t) => t.tags.includes('cross-workspace'))).toBe(true);
      expect(traces.some((t) => t.workspaceIds.includes('workspace-all'))).toBe(true);

      const mirror = JSON.parse(await readFile(path.join(dir, 'mesh-namespaces.json'), 'utf8')) as {
        'mesh/agent-lineage': { privilegeInheritance: boolean; activeAgents: number };
        'mesh/swarm/privileges': { crossWorkspace: boolean; allAgents: boolean };
      };
      expect(mirror['mesh/agent-lineage'].privilegeInheritance).toBe(true);
      expect(mirror['mesh/agent-lineage'].activeAgents).toBeGreaterThan(0);
      expect(mirror['mesh/swarm/privileges'].crossWorkspace).toBe(true);
      expect(mirror['mesh/swarm/privileges'].allAgents).toBe(true);

      const runtime = new AgentMeshRuntime(mesh, memory, { rootDir: ROOT, dataDir: dir });
      const cycle = await runtime.runCycle({ workspaces, suggestions: [] });
      expect(cycle.swarm?.activeAgents).toBeGreaterThan(0);
      expect(cycle.swarm?.namespacesTouched.length).toBeGreaterThan(0);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});
