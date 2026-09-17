import { randomUUID } from 'node:crypto';
import type {
  AgentCycleResult,
  Finding,
  LoopJob,
  MemoryTrace,
  SuggestiveImplementation,
  WorkspaceSnapshot,
} from '../../shared/types.js';
import {
  AGENT_LAYERS,
  MESH_AGENTS,
  agentNodeId,
  type AgentRoleId,
} from '../../shared/agentLayers.js';
import type { NeuralMesh } from './neural-mesh.js';
import type { PersistentMemory } from './persistent-memory.js';

const SEVERITY_ORDER = { critical: 5, high: 4, medium: 3, low: 2, info: 1 } as const;

export class AgentMeshRuntime {
  private jobs: LoopJob[] = [];
  private lastCycle: AgentCycleResult | null = null;
  private loopArmed = true;
  private previousScores = new Map<string, number>();

  constructor(
    private readonly mesh: NeuralMesh,
    private readonly memory: PersistentMemory,
  ) {}

  getJobs(): LoopJob[] {
    return this.jobs.map((j) => ({ ...j }));
  }

  getLastCycle(): AgentCycleResult | null {
    return this.lastCycle ? { ...this.lastCycle, loopActions: [...this.lastCycle.loopActions] } : null;
  }

  setLoopArmed(armed: boolean): void {
    this.loopArmed = armed;
  }

  isLoopArmed(): boolean {
    return this.loopArmed;
  }

  /**
   * One deep-layer agent cycle: commute → memory → persistence → issue-loop.
   */
  async runCycle(input: {
    workspaces: WorkspaceSnapshot[];
    suggestions: SuggestiveImplementation[];
  }): Promise<AgentCycleResult> {
    const { workspaces, suggestions } = input;
    const commutePaths = this.enhanceCommute(workspaces);
    const memoryWrites = await this.enhanceMemory(workspaces);
    const persistedJobs = this.enhancePersistence(workspaces, suggestions);
    const loopActions = this.loopArmed
      ? await this.runIssueFixLoop(workspaces, suggestions)
      : [];

    const efficiencyGain = Math.min(
      1,
      commutePaths.length * 0.08 + memoryWrites * 0.05 + persistedJobs * 0.04 + loopActions.length * 0.1,
    );

    // Pulse agent nodes
    for (const agent of MESH_AGENTS) {
      this.mesh.pulseAgent(agent.id, 0.2 + efficiencyGain * 0.4);
    }
    for (const layer of AGENT_LAYERS) {
      this.mesh.pulseLayer(layer.id, 0.15 + layer.depth * 0.08);
    }

    for (const ws of workspaces) {
      this.previousScores.set(ws.id, ws.score);
    }

    this.lastCycle = {
      commutePaths,
      memoryWrites,
      persistedJobs,
      loopActions,
      efficiencyGain,
    };
    await this.mesh.save();
    return this.lastCycle;
  }

  /** Shortest high-weight hops from weak workspaces to repair/persistence agents. */
  private enhanceCommute(workspaces: WorkspaceSnapshot[]): AgentCycleResult['commutePaths'] {
    const weak = [...workspaces].sort((a, b) => a.score - b.score).slice(0, 3);
    const paths: AgentCycleResult['commutePaths'] = [];

    for (const ws of weak) {
      const targetAgents = MESH_AGENTS.filter((a) =>
        a.relatedWorkspaceKinds.includes(ws.kind),
      );
      for (const agent of targetAgents) {
        const from = `ws-${ws.kind}`;
        const to = agentNodeId(agent.id);
        const weight = Math.max(0.2, (100 - ws.score) / 100);
        this.mesh.reinforceEdge(from, to, 0.03 + weight * 0.05);
        this.mesh.ensureEdge(from, to, 'commutes', weight, `${ws.kind} → ${agent.name}`);
        paths.push({
          from,
          to,
          weight,
          label: `commute:${ws.kind}→${agent.id}`,
        });
      }
    }
    return paths;
  }

  private async enhanceMemory(workspaces: WorkspaceSnapshot[]): Promise<number> {
    let writes = 0;
    const consolidator = MESH_AGENTS.find((a) => a.id === 'memory-consolidator')!;
    const amplifier = MESH_AGENTS.find((a) => a.id === 'recall-amplifier')!;

    for (const ws of workspaces) {
      if (ws.findings.length === 0) continue;
      const top = [...ws.findings].sort(
        (a, b) => SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity],
      )[0];
      await this.memory.write({
        kind: 'agent',
        content: `[${consolidator.name}] consolidated ${ws.name}: ${top.title}`,
        workspaceIds: [ws.id],
        nodeIds: [agentNodeId(consolidator.id), `ws-${ws.kind}`],
        salience: 0.45 + SEVERITY_ORDER[top.severity] * 0.08,
        createdAt: new Date().toISOString(),
        lastAccessedAt: new Date().toISOString(),
        decay: 0,
        tags: ['agent', 'memory', consolidator.id, ws.kind],
      });
      writes += 1;
    }

    // Amplify memories matching open loop jobs
    for (const job of this.jobs.filter((j) => j.status === 'queued' || j.status === 'running')) {
      await this.memory.write({
        kind: 'agent',
        content: `[${amplifier.name}] recall boost for job “${job.title}”`,
        workspaceIds: job.sourceWorkspaceId ? [job.sourceWorkspaceId] : [],
        nodeIds: [agentNodeId(amplifier.id)],
        salience: 0.6,
        createdAt: new Date().toISOString(),
        lastAccessedAt: new Date().toISOString(),
        decay: 0,
        tags: ['agent', 'recall', amplifier.id, 'job'],
      });
      writes += 1;
    }

    return writes;
  }

  private enhancePersistence(
    workspaces: WorkspaceSnapshot[],
    suggestions: SuggestiveImplementation[],
  ): number {
    const guardian = MESH_AGENTS.find((a) => a.id === 'completion-guardian')!;
    const persistence = MESH_AGENTS.find((a) => a.id === 'job-persistence')!;
    let count = 0;

    // Keep critical/high findings as persistent jobs
    for (const ws of workspaces) {
      for (const finding of ws.findings) {
        if (finding.severity !== 'critical' && finding.severity !== 'high') continue;
        if (this.jobs.some((j) => j.sourceFindingId === finding.id)) continue;
        this.jobs.push(this.makeJob(finding, ws, persistence.id));
        this.mesh.ensureEdge(
          `ws-${ws.kind}`,
          agentNodeId(persistence.id),
          'persists',
          0.65,
          'persist finding',
        );
        count += 1;
      }
    }

    // Suggestions with security/ops kind become sticky jobs
    for (const s of suggestions.slice(0, 5)) {
      if (s.kind !== 'security' && s.kind !== 'ops') continue;
      const key = `sug-${s.id}`;
      if (this.jobs.some((j) => j.id === key || j.title === s.title)) continue;
      this.jobs.push({
        id: key,
        title: s.title,
        detail: s.implementation,
        severity: s.priority >= 80 ? 'high' : 'medium',
        status: 'queued',
        attempts: 0,
        maxAttempts: 4,
        sourceWorkspaceId: s.relatedWorkspaceIds[0],
        assignedAgentId: guardian.id,
        fixSketch: s.sketch,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });
      count += 1;
    }

    // Re-queue stalled running jobs
    for (const job of this.jobs) {
      if (job.status === 'blocked') {
        job.status = 'queued';
        job.updatedAt = new Date().toISOString();
        count += 1;
      }
    }

    // Cap job list
    this.jobs = this.jobs
      .sort((a, b) => SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity])
      .slice(0, 40);

    return count;
  }

  /**
   * Dedicated automated issue-fix loop layer.
   * Detect → attempt fix sketch → verify via score/finding presence → persist or escalate.
   */
  private async runIssueFixLoop(
    workspaces: WorkspaceSnapshot[],
    suggestions: SuggestiveImplementation[],
  ): Promise<LoopJob[]> {
    const fixer = MESH_AGENTS.find((a) => a.id === 'issue-fix-loop')!;
    const sentinel = MESH_AGENTS.find((a) => a.id === 'regression-sentinel')!;
    const acted: LoopJob[] = [];

    // Regression sentinel: score drops trigger new loop jobs
    for (const ws of workspaces) {
      const prev = this.previousScores.get(ws.id);
      if (prev != null && ws.score < prev - 5) {
        const id = `regress-${ws.id}-${Date.now()}`;
        const job: LoopJob = {
          id,
          title: `Regression in ${ws.name}`,
          detail: `Score dropped ${prev} → ${ws.score}`,
          severity: ws.score < 50 ? 'critical' : 'high',
          status: 'queued',
          attempts: 0,
          maxAttempts: sentinel.maxLoopAttempts ?? 3,
          sourceWorkspaceId: ws.id,
          assignedAgentId: sentinel.id,
          fixSketch: `Re-scan ${ws.kind}; apply top suggestion for this workspace.`,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        this.jobs.unshift(job);
        this.mesh.pulseAgent(sentinel.id, 0.85);
        this.mesh.ensureEdge(`ws-${ws.kind}`, agentNodeId(sentinel.id), 'loops', 0.8, 'regression');
      }
    }

    const queue = this.jobs.filter(
      (j) => j.status === 'queued' || j.status === 'running' || j.status === 'verifying',
    );

    for (const job of queue.slice(0, 6)) {
      job.status = 'running';
      job.attempts += 1;
      job.assignedAgentId = job.assignedAgentId || fixer.id;
      job.updatedAt = new Date().toISOString();
      this.mesh.pulseAgent(job.assignedAgentId as AgentRoleId, 0.9);
      this.mesh.pulseLayer('issue-loop', 0.95);

      const sketch =
        job.fixSketch ??
        suggestions.find((s) => s.relatedWorkspaceIds.includes(job.sourceWorkspaceId ?? ''))
          ?.sketch ??
        suggestions.find((s) => s.title === job.title)?.implementation ??
        `Inspect ${job.title} and apply workspace suggestion.`;

      job.fixSketch = sketch;
      job.status = 'verifying';

      const stillPresent = this.findingStillOpen(job, workspaces);
      const wsScore = workspaces.find((w) => w.id === job.sourceWorkspaceId)?.score ?? 100;

      if (!stillPresent && wsScore >= 80) {
        job.status = 'fixed';
        await this.memory.write(this.loopMemory(job, 'fixed'));
      } else if (job.attempts >= job.maxAttempts) {
        job.status = 'escalated';
        job.lastError = 'Max autonomous fix attempts reached — needs human/agent escalate.';
        await this.memory.write(this.loopMemory(job, 'escalated'));
      } else {
        job.status = 'queued';
        job.lastError = stillPresent
          ? 'Issue still present after attempt; re-queued.'
          : 'Verification inconclusive; re-queued.';
        await this.memory.write(this.loopMemory(job, 'retry'));
      }

      job.updatedAt = new Date().toISOString();
      acted.push({ ...job });
      this.mesh.ensureEdge(
        agentNodeId(fixer.id),
        job.sourceWorkspaceId ? `ws-${job.sourceWorkspaceId.replace(/^workspace-/, '')}` : 'hub-cortex',
        'repairs',
        0.7,
        'issue-loop',
      );
    }

    return acted;
  }

  private findingStillOpen(job: LoopJob, workspaces: WorkspaceSnapshot[]): boolean {
    if (!job.sourceFindingId && !job.sourceWorkspaceId) return job.severity === 'critical';
    for (const ws of workspaces) {
      if (job.sourceWorkspaceId && ws.id !== job.sourceWorkspaceId) continue;
      if (job.sourceFindingId && ws.findings.some((f) => f.id === job.sourceFindingId)) return true;
      if (
        !job.sourceFindingId &&
        ws.findings.some(
          (f) => f.title === job.title || f.severity === 'critical' || f.severity === 'high',
        )
      ) {
        return true;
      }
    }
    return false;
  }

  private makeJob(finding: Finding, ws: WorkspaceSnapshot, agentId: string): LoopJob {
    return {
      id: randomUUID(),
      title: finding.title,
      detail: finding.detail,
      severity: finding.severity,
      status: 'queued',
      attempts: 0,
      maxAttempts: MESH_AGENTS.find((a) => a.id === 'issue-fix-loop')?.maxLoopAttempts ?? 5,
      sourceFindingId: finding.id,
      sourceWorkspaceId: ws.id,
      assignedAgentId: agentId,
      fixSketch: finding.suggestion,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
  }

  private loopMemory(job: LoopJob, phase: string): Omit<MemoryTrace, 'id'> & { id?: string } {
    return {
      kind: 'loop',
      content: `[issue-loop:${phase}] ${job.title} (attempt ${job.attempts}/${job.maxAttempts}) — ${job.fixSketch ?? ''}`,
      workspaceIds: job.sourceWorkspaceId ? [job.sourceWorkspaceId] : [],
      nodeIds: [agentNodeId('issue-fix-loop'), layerHubIdSafe()],
      salience: phase === 'fixed' ? 0.75 : phase === 'escalated' ? 0.85 : 0.5,
      createdAt: new Date().toISOString(),
      lastAccessedAt: new Date().toISOString(),
      decay: 0,
      tags: ['agent', 'issue-loop', phase, job.severity],
    };
  }
}

function layerHubIdSafe(): string {
  return 'layer-issue-loop';
}
