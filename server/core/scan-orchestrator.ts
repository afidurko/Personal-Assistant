import { EventEmitter } from 'node:events';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type {
  Finding,
  MemoryTrace,
  NeuralMeshState,
  ScanCycleResult,
  WorkspaceSnapshot,
} from '../../shared/types.js';
import {
  SWIFT_GUIDE_BY_ID,
  SWIFT_GUIDE_CONCEPTS,
  type SwiftConceptId,
} from '../../shared/swiftGuide.js';
import { NeuralMesh } from './neural-mesh.js';
import { PersistentMemory } from './persistent-memory.js';
import {
  buildSuggestiveImplementations,
  type SuggestiveImplementation,
} from './suggestions.js';
import { AgentMeshRuntime } from './agent-mesh.js';
import { runAllScans } from '../workspaces/index.js';
import type { AgentCycleResult, LoopJob } from '../../shared/types.js';

export type ScanOrchestratorEvent =
  | 'tick'
  | 'complete'
  | 'state'
  | 'memory_update'
  | 'agent_cycle'
  | 'loop_update';

export interface ScanOrchestratorOptions {
  /** Project root passed to workspace scanners. */
  rootDir?: string;
  /** Persistence directory for mesh.json / memory.json. */
  dataDir?: string;
  /** Continuous scan interval (default 15s). */
  intervalMs?: number;
  mesh?: NeuralMesh;
  memory?: PersistentMemory;
  runScans?: (rootDir: string) => Promise<WorkspaceSnapshot[]>;
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_ROOT = path.resolve(__dirname, '../..');

export class ScanOrchestrator extends EventEmitter {
  private readonly rootDir: string;
  private readonly dataDir: string;
  private readonly intervalMs: number;
  private readonly mesh: NeuralMesh;
  private readonly memory: PersistentMemory;
  private readonly runScans: (rootDir: string) => Promise<WorkspaceSnapshot[]>;
  private timer: ReturnType<typeof setInterval> | null = null;
  private running = false;
  private cycleCount = 0;
  private lastCycleAt: string | null = null;
  private workspaces: WorkspaceSnapshot[] = [];
  private scanning = false;
  private ready = false;
  private activeConceptId: string | null = null;
  private guideStep = 0;
  private suggestions: SuggestiveImplementation[] = [];
  private agents: AgentMeshRuntime | null = null;
  private lastAgentCycle: AgentCycleResult | null = null;

  constructor(options: ScanOrchestratorOptions = {}) {
    super();
    this.rootDir = options.rootDir ?? DEFAULT_ROOT;
    this.dataDir = options.dataDir ?? path.join(this.rootDir, 'data');
    this.intervalMs = options.intervalMs ?? 15_000;
    this.mesh = options.mesh ?? new NeuralMesh({ dataDir: this.dataDir });
    this.memory = options.memory ?? new PersistentMemory({ dataDir: this.dataDir });
    this.runScans = options.runScans ?? ((root) => runAllScans(root));
  }

  /** Load mesh + memory from disk (seed topology if empty). */
  async init(): Promise<void> {
    await this.mesh.load();
    await this.memory.load();
    this.agents = new AgentMeshRuntime(this.mesh, this.memory);
    this.ready = true;
    this.emitState();
  }

  async start(): Promise<void> {
    await this.ensureReady();
    if (this.timer) return;
    this.running = true;
    this.emitState();
    void this.runOnce();
    this.timer = setInterval(() => {
      void this.runOnce();
    }, this.intervalMs);
    this.timer.unref?.();
  }

  stop(): void {
    this.running = false;
    this.scanning = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.emitState();
  }

  async runOnce(): Promise<ScanCycleResult> {
    await this.ensureReady();
    this.scanning = true;
    // Paint the brain map scanning colors while workspaces run.
    this.mesh.markScanning();
    this.emit('tick', { cycle: this.cycleCount + 1, at: new Date().toISOString() });
    this.emitState();

    let snapshots: WorkspaceSnapshot[] = [];
    try {
      snapshots = await this.runScans(this.rootDir);
    } catch (err) {
      this.scanning = false;
      this.emitState();
      throw err;
    }

    this.workspaces = snapshots;
    const activationDeltas = this.mesh.applyScanResults(snapshots);
    this.suggestions = buildSuggestiveImplementations(snapshots);

    const agentRuntime = this.agents ?? new AgentMeshRuntime(this.mesh, this.memory);
    this.agents = agentRuntime;
    this.lastAgentCycle = await agentRuntime.runCycle({
      workspaces: snapshots,
      suggestions: this.suggestions,
    });
    // Rebuild suggestions with live loop/cycle context for agent-aware implementations.
    this.suggestions = buildSuggestiveImplementations(snapshots, {
      loopJobs: agentRuntime.getJobs(),
      lastAgentCycle: this.lastAgentCycle,
    });
    this.emit('agent_cycle', this.lastAgentCycle);
    this.emit('loop_update', agentRuntime.getJobs());

    const { nodes } = this.mesh.getState();
    const colorMap: Record<string, string> = {};
    for (const node of nodes) {
      colorMap[node.id] = node.color;
    }

    const memoryWrites: MemoryTrace[] = [];
    const allFindings: Finding[] = [];

    for (const snap of snapshots) {
      allFindings.push(...snap.findings);
      const meshNode = this.mesh.findWorkspaceNode(snap.id, snap.kind);
      const nodeId = meshNode?.id ?? `ws-${snap.kind}`;
      for (const finding of snap.findings) {
        const salience = severityToSalience(finding.severity);
        const trace = await this.memory.write({
          kind: 'scan',
          content: `${finding.title}: ${finding.detail}`,
          workspaceIds: [snap.id],
          nodeIds: finding.relatedNodeIds ?? [nodeId],
          salience,
          createdAt: finding.createdAt || new Date().toISOString(),
          lastAccessedAt: new Date().toISOString(),
          decay: 0,
          tags: [snap.kind, finding.category, finding.severity, 'scan'],
        });
        memoryWrites.push(trace);
      }

      const breadcrumb = await this.memory.write({
        kind: 'scan',
        content: `Scan ${snap.name}: score=${snap.score} status=${snap.status} findings=${snap.findings.length}`,
        workspaceIds: [snap.id],
        nodeIds: [nodeId],
        salience: Math.max(0.08, 0.2 + (100 - snap.score) / 200),
        createdAt: new Date().toISOString(),
        lastAccessedAt: new Date().toISOString(),
        decay: 0,
        tags: [snap.kind, 'cycle', snap.status],
      });
      memoryWrites.push(breadcrumb);
    }

    await this.memory.decayAll(0.01);
    await this.mesh.save();

    this.cycleCount += 1;
    this.lastCycleAt = new Date().toISOString();
    this.scanning = false;

    const result: ScanCycleResult = {
      workspaces: snapshots,
      findings: allFindings,
      memoryWrites,
      activationDeltas,
      colorMap,
    };

    this.emit('complete', result);
    if (memoryWrites.length > 0) {
      this.emit('memory_update', memoryWrites);
    }
    this.emitState();
    return result;
  }

  getFullState(): NeuralMeshState {
    const { nodes, edges } = this.mesh.getState();
    return {
      nodes,
      edges,
      workspaces: this.workspaces,
      memory: this.memory.getTraces().slice(0, 120),
      // Continuous loop armed, or a cycle currently in flight.
      scanning: this.running || this.scanning,
      lastCycleAt: this.lastCycleAt,
      cycleCount: this.cycleCount,
      activeConceptId: this.activeConceptId,
      guideStep: this.guideStep,
      suggestions: this.suggestions,
      loopJobs: this.agents?.getJobs() ?? [],
      lastAgentCycle: this.lastAgentCycle,
    };
  }

  getSuggestions(): SuggestiveImplementation[] {
    return this.suggestions.map((s) => ({
      ...s,
      relatedWorkspaceIds: [...s.relatedWorkspaceIds],
      relatedConceptIds: [...s.relatedConceptIds],
      sourceFindingIds: [...s.sourceFindingIds],
    }));
  }

  getLoopJobs(): LoopJob[] {
    return this.agents?.getJobs() ?? [];
  }

  async runAgentCycle(): Promise<AgentCycleResult | null> {
    await this.ensureReady();
    if (!this.agents) this.agents = new AgentMeshRuntime(this.mesh, this.memory);
    this.lastAgentCycle = await this.agents.runCycle({
      workspaces: this.workspaces,
      suggestions: this.suggestions,
    });
    this.suggestions = buildSuggestiveImplementations(this.workspaces, {
      loopJobs: this.agents.getJobs(),
      lastAgentCycle: this.lastAgentCycle,
    });
    this.emit('agent_cycle', this.lastAgentCycle);
    this.emit('loop_update', this.agents.getJobs());
    this.emitState();
    return this.lastAgentCycle;
  }

  setIssueLoopArmed(armed: boolean): void {
    if (!this.agents) this.agents = new AgentMeshRuntime(this.mesh, this.memory);
    this.agents.setLoopArmed(armed);
    this.emitState();
  }

  isIssueLoopArmed(): boolean {
    return this.agents?.isLoopArmed() ?? true;
  }

  getWorkspaces(): WorkspaceSnapshot[] {
    return this.workspaces.map((w) => ({
      ...w,
      findings: [...w.findings],
      metrics: { ...w.metrics },
    }));
  }

  queryMemory(q?: string | string[]): MemoryTrace[] {
    if (q === undefined || q === '') return this.memory.getTraces();
    return this.memory.query(q);
  }

  focusNode(id: string): { nodeId: string; workspaceIds: string[] } {
    const workspaceIds = this.mesh.focusNode(id);
    void this.mesh.save();
    this.emitState();
    return { nodeId: id, workspaceIds };
  }

  focusWorkspace(workspaceId: string): { nodeId: string; workspaceIds: string[] } {
    const node = this.mesh.findWorkspaceNode(workspaceId);
    if (!node) return { nodeId: workspaceId, workspaceIds: [workspaceId] };
    return this.focusNode(node.id);
  }

  async openConcept(conceptId: string): Promise<{
    nodeId: string;
    conceptId: string;
    workspaceIds: string[];
    guideStep: number;
  }> {
    await this.ensureReady();
    const concept = SWIFT_GUIDE_CONCEPTS.find((c) => c.id === conceptId);
    if (!concept) {
      return { nodeId: conceptId, conceptId, workspaceIds: [], guideStep: this.guideStep };
    }
    const focused = this.mesh.focusConcept(concept.id);
    this.activeConceptId = concept.id;
    this.guideStep = concept.tourOrder;
    await this.memory.write({
      kind: 'procedural',
      content: `Swift Guide: explored ${concept.title} — ${concept.explore}`,
      workspaceIds: focused.workspaceIds,
      nodeIds: [focused.nodeId],
      salience: 0.55,
      createdAt: new Date().toISOString(),
      lastAccessedAt: new Date().toISOString(),
      decay: 0,
      tags: ['swift-guide', concept.id, 'tour', ...concept.tags],
    });
    await this.mesh.save();
    this.emit('memory_update', this.memory.getTraces().slice(0, 20));
    this.emitState();
    return { ...focused, guideStep: this.guideStep };
  }

  async guideStart(): Promise<ReturnType<ScanOrchestrator['openConcept']>> {
    return this.openConcept(SWIFT_GUIDE_CONCEPTS[0].id);
  }

  async guideNext(): Promise<ReturnType<ScanOrchestrator['openConcept']> | null> {
    const current = this.activeConceptId
      ? SWIFT_GUIDE_BY_ID[this.activeConceptId as SwiftConceptId]
      : null;
    const nextId = current?.nextId ?? SWIFT_GUIDE_CONCEPTS[0]?.id;
    if (!nextId) return null;
    return this.openConcept(nextId);
  }

  async guidePrev(): Promise<ReturnType<ScanOrchestrator['openConcept']> | null> {
    if (!this.activeConceptId) return this.guideStart();
    const idx = SWIFT_GUIDE_CONCEPTS.findIndex((c) => c.id === this.activeConceptId);
    const prev = SWIFT_GUIDE_CONCEPTS[Math.max(0, idx - 1)];
    return this.openConcept(prev.id);
  }

  reinforce(from: string, to: string, delta = 0.05): void {
    this.mesh.reinforceEdge(from, to, delta);
    void this.mesh.save();
    this.emitState();
  }

  getMesh(): NeuralMesh {
    return this.mesh;
  }

  getMemory(): PersistentMemory {
    return this.memory;
  }

  isRunning(): boolean {
    return this.running;
  }

  isScanning(): boolean {
    return this.scanning;
  }

  on(event: ScanOrchestratorEvent, handler: (...args: unknown[]) => void): this;
  on(event: string | symbol, handler: (...args: unknown[]) => void): this {
    return super.on(event, handler);
  }

  private async ensureReady(): Promise<void> {
    if (!this.ready) await this.init();
  }

  private emitState(): void {
    this.emit('state', this.getFullState());
  }
}

function severityToSalience(severity: Finding['severity']): number {
  switch (severity) {
    case 'critical':
      return 0.95;
    case 'high':
      return 0.8;
    case 'medium':
      return 0.55;
    case 'low':
      return 0.35;
    default:
      return 0.2;
  }
}
