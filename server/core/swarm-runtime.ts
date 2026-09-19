/**
 * Swarm runtime — privilege inheritance, lineage, and boss/worker bus
 * integrated into the neural mesh + persistent memory across workspaces.
 */

import { randomUUID } from 'node:crypto';
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import path from 'node:path';
import type { MemoryTrace, WorkspaceSnapshot } from '../../shared/types.js';
import {
  PrivilegeError,
  SWARM_MESH_NAMESPACES,
  createChiefNode,
  emptyLineageState,
  loadPrivilegeCatalog,
  mayTerminate,
  spawnChild,
  type SwarmBusEvent,
  type SwarmLineageState,
  type SwarmPrimitiveOp,
} from '../../shared/swarmPrivileges.js';
import { agentNodeId } from '../../shared/agentLayers.js';
import type { NeuralMesh } from './neural-mesh.js';
import type { PersistentMemory } from './persistent-memory.js';

export interface SwarmCycleResult {
  spawns: number;
  assigns: number;
  broadcasts: number;
  resolves: number;
  terminations: number;
  denials: number;
  activeAgents: number;
  memoryWrites: number;
  events: SwarmBusEvent[];
  namespacesTouched: string[];
}

export class SwarmRuntime {
  private state: SwarmLineageState;
  private readonly filePath: string;
  private loaded = false;

  constructor(
    private readonly mesh: NeuralMesh,
    private readonly memory: PersistentMemory,
    private readonly dataDir: string,
    private readonly rootDir: string,
  ) {
    this.filePath = path.join(dataDir, 'swarm-lineage.json');
    this.state = emptyLineageState();
  }

  async load(): Promise<void> {
    await mkdir(this.dataDir, { recursive: true });
    try {
      const raw = await readFile(this.filePath, 'utf8');
      const parsed = JSON.parse(raw) as SwarmLineageState;
      this.state = parsed?.version === 1 ? parsed : emptyLineageState();
    } catch (err) {
      const code = (err as NodeJS.ErrnoException).code;
      if (code !== 'ENOENT') throw err;
      this.state = emptyLineageState();
    }
    if (!this.state.agents.some((a) => a.id === 'agent.chief' && a.status === 'active')) {
      this.state.agents.unshift(createChiefNode());
    }
    this.loaded = true;
    await this.save();
  }

  async save(): Promise<void> {
    if (!this.loaded) await this.load();
    this.state.updatedAt = new Date().toISOString();
    // Cap event log
    if (this.state.events.length > 200) {
      this.state.events = this.state.events.slice(-200);
    }
    await mkdir(this.dataDir, { recursive: true });
    await atomicWriteJson(this.filePath, this.state);
  }

  getState(): SwarmLineageState {
    return {
      ...this.state,
      agents: this.state.agents.map((a) => ({ ...a, privileges: [...a.privileges], lineage: [...a.lineage], workspaceIds: [...a.workspaceIds] })),
      events: this.state.events.map((e) => ({ ...e, workspaceIds: [...e.workspaceIds] })),
    };
  }

  /**
   * One swarm cycle across all workspaces:
   * privilege-check spawn → assign/broadcast → resolve → memory namespaces → mesh pulse.
   */
  async runCycle(input: {
    workspaces: WorkspaceSnapshot[];
  }): Promise<SwarmCycleResult> {
    if (!this.loaded) await this.load();
    const catalog = loadPrivilegeCatalog(this.rootDir);
    const workspaceIds = input.workspaces.map((w) => w.id);
    const now = new Date().toISOString();
    const events: SwarmBusEvent[] = [];
    let spawns = 0;
    let assigns = 0;
    let broadcasts = 0;
    let resolves = 0;
    let terminations = 0;
    let denials = 0;
    let memoryWrites = 0;

    const chief =
      this.state.agents.find((a) => a.id === 'agent.chief' && a.status === 'active') ??
      createChiefNode(catalog, now);
    if (!this.state.agents.some((a) => a.id === chief.id)) {
      this.state.agents.push(chief);
    }

    // Ensure chief sees all live workspaces
    chief.workspaceIds = unique([...chief.workspaceIds, ...workspaceIds, 'workspace-all']);

    // Spawn capability-broker + tooling agents if missing (privilege-safe)
    const rolesToEnsure = [
      { role: 'capability-broker', meshAgent: 'privilege-broker' as const },
      { role: 'tool-creator', meshAgent: 'tool-broker' as const },
      { role: 'qa', meshAgent: 'lineage-guardian' as const },
    ];

    for (const { role, meshAgent } of rolesToEnsure) {
      const existing = this.state.agents.find(
        (a) => a.role === role && a.parentId === chief.id && a.status === 'active',
      );
      if (existing) {
        existing.workspaceIds = unique([...existing.workspaceIds, ...workspaceIds]);
        continue;
      }
      try {
        const child = spawnChild({
          parent: chief,
          role,
          catalog,
          workspaceIds,
          now,
        });
        this.state.agents.push(child);
        spawns += 1;
        const ev = this.busEvent('synapse.spawn', chief.id, child.id, `spawn ${role}`, workspaceIds, true, now);
        events.push(ev);
        this.mesh.ensureEdge(
          agentNodeId('boss-router'),
          agentNodeId(meshAgent),
          'spawns',
          0.6,
          `spawn ${role}`,
        );
        this.mesh.pulseAgent(meshAgent, 0.5);
      } catch (err) {
        denials += 1;
        events.push(
          this.busEvent(
            'denied',
            chief.id,
            role,
            err instanceof Error ? err.message : String(err),
            workspaceIds,
            false,
            now,
          ),
        );
      }
    }

    const broker = this.state.agents.find(
      (a) => a.role === 'capability-broker' && a.status === 'active',
    );
    if (broker) {
      // Cross-workspace assign: one worker per weak workspace
      const weak = [...input.workspaces].sort((a, b) => a.score - b.score).slice(0, 3);
      for (const ws of weak) {
        try {
          const worker = spawnChild({
            parent: broker,
            role: 'task-executor',
            catalog,
            workspaceIds: [ws.id, ...workspaceIds],
            now,
          });
          // Dedupe by role+parent+workspace tag in id suffix for cycle ephemerals
          worker.id = `${broker.id}/task-executor@${worker.level}:${ws.kind}`;
          const prior = this.state.agents.find((a) => a.id === worker.id && a.status === 'active');
          if (!prior) {
            this.state.agents.push(worker);
            spawns += 1;
            events.push(
              this.busEvent('synapse.spawn', broker.id, worker.id, `spawn worker for ${ws.kind}`, [ws.id], true, now),
            );
          }
          const assignee = prior ?? worker;
          assigns += 1;
          events.push(
            this.busEvent(
              'synapse.assign_task',
              broker.id,
              assignee.id,
              `stabilize ${ws.name} (score=${ws.score})`,
              [ws.id],
              true,
              now,
            ),
          );
          this.mesh.ensureEdge(
            agentNodeId('boss-router'),
            `ws-${ws.kind}`,
            'assigns',
            0.55 + (100 - ws.score) / 200,
            `assign→${ws.kind}`,
          );
          this.mesh.pulseAgent('boss-router', 0.35);
          resolves += 1;
          events.push(
            this.busEvent(
              'synapse.resolve_task',
              assignee.id,
              broker.id,
              `acked ${ws.kind}`,
              [ws.id],
              true,
              now,
            ),
          );
        } catch (err) {
          denials += 1;
          events.push(
            this.busEvent(
              'denied',
              broker.id,
              ws.kind,
              err instanceof Error ? err.message : String(err),
              [ws.id],
              false,
              now,
            ),
          );
        }
      }

      broadcasts += 1;
      events.push(
        this.busEvent(
          'synapse.broadcast',
          broker.id,
          undefined,
          `cycle across ${workspaceIds.length} workspaces`,
          workspaceIds,
          true,
          now,
          'mesh.all',
        ),
      );
      this.mesh.pulseAgent('boss-router', 0.45);
      this.mesh.pulseLayer('swarm', 0.7);
    }

    // Deny aaron_only escalation attempt (contract pulse)
    try {
      if (broker) {
        spawnChild({
          parent: broker,
          role: 'rogue',
          requested: ['kill_master', 'task_giver'],
          catalog,
          workspaceIds,
          now,
        });
      }
    } catch (err) {
      if (err instanceof PrivilegeError) {
        denials += 1;
        events.push(
          this.busEvent(
            'denied',
            broker?.id ?? chief.id,
            'rogue',
            err.message,
            workspaceIds,
            false,
            now,
          ),
        );
        this.mesh.pulseAgent('privilege-broker', 0.8);
      }
    }

    // Lineage hygiene: terminate ephemeral workers older than keep-alive if too many
    const activeWorkers = this.state.agents.filter(
      (a) => a.role === 'task-executor' && a.status === 'active',
    );
    if (activeWorkers.length > 12 && broker) {
      const oldest = activeWorkers.sort(
        (a, b) => Date.parse(a.createdAt) - Date.parse(b.createdAt),
      )[0];
      if (oldest && mayTerminate(broker, oldest)) {
        oldest.status = 'terminated';
        oldest.terminatedAt = now;
        oldest.terminateReason = 'lineage hygiene — cap ephemeral workers';
        terminations += 1;
        events.push(
          this.busEvent(
            'synapse.terminate_lineage',
            broker.id,
            oldest.id,
            oldest.terminateReason,
            oldest.workspaceIds,
            true,
            now,
          ),
        );
        this.mesh.pulseAgent('lineage-guardian', 0.75);
        this.mesh.ensureEdge(
          agentNodeId('lineage-guardian'),
          agentNodeId('privilege-broker'),
          'terminates',
          0.5,
          'lineage hygiene',
        );
      }
    }

    // Persist events + memory namespaces shared by all agents/workspaces
    this.state.events.push(...events);
    const namespacesTouched = [...SWARM_MESH_NAMESPACES];

    for (const ev of events) {
      const trace = await this.memory.write({
        kind: 'swarm',
        content: `[${ev.op}] ${ev.from}${ev.to ? ' → ' + ev.to : ''}: ${ev.detail}`,
        workspaceIds: ev.workspaceIds.length ? ev.workspaceIds : workspaceIds,
        nodeIds: [
          agentNodeId('privilege-broker'),
          agentNodeId('boss-router'),
          agentNodeId('lineage-guardian'),
          'layer-swarm',
          'hub-hippocampus',
        ],
        salience: ev.ok ? 0.45 : 0.7,
        createdAt: ev.at,
        lastAccessedAt: ev.at,
        decay: 0,
        tags: [
          'swarm',
          ev.op,
          ev.ok ? 'ok' : 'denied',
          'mesh/agent-lineage',
          'mesh/swarm/bus',
          ...ev.workspaceIds.map((id) => id.replace(/^workspace-/, '')),
        ],
      });
      memoryWrites += 1;
      void trace;
    }

    // Semantic distillate into mesh/swarm/privileges + mesh/agent-lineage
    await this.memory.write({
      kind: 'semantic',
      content: `Swarm cycle: active=${this.activeCount()} spawns=${spawns} assigns=${assigns} denials=${denials} terminations=${terminations} workspaces=${workspaceIds.join(',')}`,
      workspaceIds: [...workspaceIds, 'workspace-all'],
      nodeIds: ['layer-swarm', 'hub-hippocampus', 'hub-cortex'],
      salience: 0.55,
      createdAt: now,
      lastAccessedAt: now,
      decay: 0,
      tags: [
        'swarm',
        'mesh/agent-lineage',
        'mesh/swarm/privileges',
        'cross-workspace',
        'all-agents',
      ],
    });
    memoryWrites += 1;

    // Namespace mirror file for cross-workspace restore
    await this.writeNamespaceMirror(workspaceIds, now);

    // Hebbian: reinforce swarm layer ↔ every workspace
    for (const ws of input.workspaces) {
      this.mesh.ensureEdge('layer-swarm', `ws-${ws.kind}`, 'correlates', 0.4, 'swarm↔workspace');
      this.mesh.reinforceEdge('layer-swarm', `ws-${ws.kind}`, 0.02);
    }
    this.mesh.ensureEdge('layer-swarm', 'hub-hippocampus', 'feeds', 0.5, 'swarm→memory');
    this.mesh.ensureEdge('layer-swarm', 'hub-cortex', 'feeds', 0.45, 'swarm→cortex');
    this.mesh.pulseLayer('swarm', 0.55);

    await this.save();
    await this.mesh.save();

    return {
      spawns,
      assigns,
      broadcasts,
      resolves,
      terminations,
      denials,
      activeAgents: this.activeCount(),
      memoryWrites,
      events,
      namespacesTouched,
    };
  }

  private activeCount(): number {
    return this.state.agents.filter((a) => a.status === 'active').length;
  }

  private busEvent(
    op: SwarmPrimitiveOp,
    from: string,
    to: string | undefined,
    detail: string,
    workspaceIds: string[],
    ok: boolean,
    at: string,
    channel?: string,
  ): SwarmBusEvent {
    return {
      id: randomUUID(),
      op,
      from,
      to,
      channel,
      detail,
      at,
      workspaceIds: [...workspaceIds],
      ok,
    };
  }

  private async writeNamespaceMirror(workspaceIds: string[], now: string): Promise<void> {
    const mirrorPath = path.join(this.dataDir, 'mesh-namespaces.json');
    let mirror: Record<string, unknown> = {};
    try {
      mirror = JSON.parse(await readFile(mirrorPath, 'utf8')) as Record<string, unknown>;
    } catch {
      mirror = {};
    }
    mirror['mesh/agent-lineage'] = {
      updatedAt: now,
      activeAgents: this.activeCount(),
      agents: this.state.agents
        .filter((a) => a.status === 'active')
        .map((a) => ({
          id: a.id,
          role: a.role,
          level: a.level,
          parentId: a.parentId,
          privileges: a.privileges,
          workspaceIds: a.workspaceIds,
        })),
      soleOperator: 'Aaron',
      privilegeInheritance: true,
      lineageTerminate: true,
    };
    mirror['mesh/swarm/bus'] = {
      updatedAt: now,
      recentEvents: this.state.events.slice(-20),
    };
    mirror['mesh/swarm/privileges'] = {
      updatedAt: now,
      catalog: 'config/swarm/privileges.json',
      aaronOnlyNeverGranted: true,
      crossWorkspace: true,
      allAgents: true,
    };
    mirror['mesh/tools'] = {
      updatedAt: now,
      registry: 'config/tools/registry.json',
      team: 'team.tooling',
    };
    mirror['mesh/workspaces'] = {
      updatedAt: now,
      ids: workspaceIds,
    };
    for (const ns of SWARM_MESH_NAMESPACES) {
      if (!(ns in mirror)) {
        mirror[ns] = { updatedAt: now, seeded: true };
      }
    }
    await atomicWriteJson(mirrorPath, mirror);
  }
}

async function atomicWriteJson(filePath: string, data: unknown): Promise<void> {
  const tmp = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(tmp, JSON.stringify(data, null, 2), 'utf8');
  await rename(tmp, filePath);
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

/** Type-only re-export helper for memory kind checks. */
export type { MemoryTrace };
