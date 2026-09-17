/**
 * Cam background autonomy — self-improvement tasks she creates while listening.
 * Writes vault distillates so the 3D cortex live feed can light fibers.
 */
import { readFile, writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import type { LoopJob, MemoryTrace, WorkspaceSnapshot } from '../../shared/types.js';
import type { RuntimeStore } from './runtime-store.js';

export interface CamSelfTask {
  id: string;
  title: string;
  detail: string;
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical';
  status: 'queued' | 'running' | 'done';
  neuron: string;
  area: string;
  createdAt: string;
  updatedAt: string;
  source: 'cam_autonomy';
}

export interface AutonomyTickResult {
  tasks: CamSelfTask[];
  spawned: number;
  advanced: number;
  activityEvents: number;
}

const SELF_IMPROVE_CATALOG: Array<{
  title: string;
  detail: string;
  neuron: string;
  area: string;
  severity: CamSelfTask['severity'];
}> = [
  {
    title: 'Refresh live activity feed for cortex fibers',
    detail: 'Merge recent converse + agent pulses into live-activity.json for DTI brightness.',
    neuron: 'neuron.mesh_sync_loop',
    area: 'area.mtl',
    severity: 'medium',
  },
  {
    title: 'Consolidate episodic converse into semantic memory',
    detail: 'Distill recent Aaron↔Cam turns into vault mesh notes for faster recall.',
    neuron: 'neuron.memory',
    area: 'area.mtl',
    severity: 'low',
  },
  {
    title: 'Sweep spawn bay capacity for subagents',
    detail: 'Ensure loop job lanes stay open so Cam and her agents have room to work.',
    neuron: 'neuron.delegate_burst',
    area: 'area.dlpfc',
    severity: 'medium',
  },
  {
    title: 'Tune speak/hear arcuate pathway',
    detail: 'Pulse language tracts after mic turns so Broca↔Wernicke stay warm.',
    neuron: 'neuron.speak_loop',
    area: 'area.broca',
    severity: 'low',
  },
  {
    title: 'Propose Cam system enhancement from scan findings',
    detail: 'Turn weak workspace scores into self-improve tasks (Aaron gates apply).',
    neuron: 'neuron.improve_engine',
    area: 'area.apfc',
    severity: 'high',
  },
  {
    title: 'Health conductor standing scan',
    detail: 'Background vitals pass so the cortex health neurons stay honest.',
    neuron: 'neuron.health_conductor',
    area: 'area.cingulate',
    severity: 'medium',
  },
];

export class CamAutonomy {
  private tasks: CamSelfTask[] = [];
  private tickCount = 0;
  private lastImproveFingerprint = '';
  private lastLiveFingerprint = '';

  constructor(private readonly runtime: RuntimeStore) {}

  getTasks(): CamSelfTask[] {
    return this.tasks.map((t) => ({ ...t }));
  }

  /** One background tick — spawn + advance self-tasks, emit activity. */
  async tick(input: {
    workspaces?: WorkspaceSnapshot[];
    loopJobs?: LoopJob[];
    listening?: boolean;
  }): Promise<AutonomyTickResult> {
    this.tickCount += 1;
    let spawned = 0;
    let advanced = 0;
    let activityEvents = 0;
    const advancedTasks: CamSelfTask[] = [];

    // Always keep a few open self-tasks so Cam is working in the background
    const open = this.tasks.filter((t) => t.status !== 'done');
    const slots = Math.max(0, 12 - open.length);
    const catalog = [...SELF_IMPROVE_CATALOG].sort(() => Math.random() - 0.5);

    for (const item of catalog) {
      if (spawned >= Math.min(2, slots)) break;
      if (open.some((t) => t.title === item.title)) continue;
      // Bias toward improve_engine when workspaces look weak
      const weak =
        (input.workspaces ?? []).some((w) => w.score < 70) &&
        item.neuron === 'neuron.improve_engine';
      if (!weak && Math.random() > 0.55 && this.tickCount % 2 === 0) continue;
      const now = new Date().toISOString();
      this.tasks.unshift({
        id: `cam-self-${randomUUID().slice(0, 8)}`,
        title: item.title,
        detail: item.detail,
        severity: item.severity,
        status: 'queued',
        neuron: item.neuron,
        area: item.area,
        createdAt: now,
        updatedAt: now,
        source: 'cam_autonomy',
      });
      spawned += 1;
    }

    // Advance queued → running → done (emit activity only on transitions)
    for (const task of this.tasks.filter((t) => t.status !== 'done').slice(0, 6)) {
      let changed = false;
      if (task.status === 'queued') {
        task.status = 'running';
        task.updatedAt = new Date().toISOString();
        advanced += 1;
        changed = true;
      } else if (task.status === 'running' && Math.random() > 0.45) {
        task.status = 'done';
        task.updatedAt = new Date().toISOString();
        advanced += 1;
        changed = true;
      }
      if (changed) {
        advancedTasks.push(task);
        activityEvents += await this.emitActivity(task, input.listening ?? false);
      }
    }

    // Cap history but leave generous room for spawn
    this.tasks = this.tasks.slice(0, 64);

    const dirty = spawned > 0 || advanced > 0 || this.tickCount === 1;
    if (dirty) {
      await this.persistImproveTasks(input.loopJobs ?? []);
      await this.refreshLiveActivity();
      await this.trimActivityLog();
    }

    return {
      tasks: this.getTasks(),
      spawned,
      advanced,
      activityEvents,
    };
  }

  toMemoryTraces(): Array<Omit<MemoryTrace, 'id'> & { id?: string }> {
    return this.tasks
      .filter((t) => t.status === 'running' || t.status === 'queued')
      .slice(0, 8)
      .map((t) => ({
        kind: 'agent' as const,
        content: `[Cam autonomy] ${t.title} — ${t.detail}`,
        workspaceIds: ['workspace-improvements'],
        nodeIds: ['layer-persistence', 'agent-job-persistence'],
        salience: t.severity === 'high' || t.severity === 'critical' ? 0.7 : 0.45,
        createdAt: t.createdAt,
        lastAccessedAt: t.updatedAt,
        decay: 0,
        tags: ['cam', 'autonomy', 'self-improve', t.neuron],
      }));
  }

  private async emitActivity(task: CamSelfTask, listening: boolean): Promise<number> {
    try {
      const tracts =
        task.area === 'area.broca' || task.neuron.includes('speak')
          ? ['tract.arcuate', 'tract.af_anterior', 'tract.fat']
          : task.area === 'area.mtl'
            ? ['tract.fornix', 'tract.cingulum', 'tract.cingulum2']
            : ['tract.slf', 'tract.cingulum', 'tract.forceps_minor'];
      const row = {
        ts: new Date().toISOString(),
        neuron: task.neuron,
        kind: task.status === 'done' ? 'loop' : 'agent',
        area: task.area,
        intensity: listening ? 0.95 : 0.7,
        tracts,
        reason: `cam_autonomy:${task.status}:${task.title}`,
        source: 'cam_autonomy',
      };
      await this.runtime.appendLine('activity-events.jsonl', JSON.stringify(row));
      return 1;
    } catch {
      return 0;
    }
  }

  private async persistImproveTasks(loopJobs: LoopJob[]): Promise<void> {
    try {
      const payload = {
        updatedAt: new Date().toISOString(),
        camSelfTasks: this.getTasks(),
        loopJobs: loopJobs.slice(0, 40),
        capacity: { selfTaskSlots: 64, loopJobHint: 80, note: 'Room for Cam and her spawn' },
      };
      const fingerprint = JSON.stringify({
        tasks: payload.camSelfTasks.map((t) => [t.id, t.status]),
        jobs: payload.loopJobs.map((j) => [j.id, j.status, j.attempts]),
      });
      if (fingerprint === this.lastImproveFingerprint) return;
      this.lastImproveFingerprint = fingerprint;
      await this.runtime.writeJson('improve-tasks.json', payload);
    } catch {
      /* best-effort */
    }
  }

  private async refreshLiveActivity(): Promise<void> {
    try {
      const eventsPath = this.runtime.pathFor('activity-events.jsonl');
      let lines: string[] = [];
      try {
        const raw = await readFile(eventsPath, 'utf8');
        lines = raw.trim().split('\n').filter(Boolean).slice(-40);
      } catch {
        lines = [];
      }
      const firing = lines
        .map((l) => {
          try {
            return JSON.parse(l) as {
              neuron?: string;
              kind?: string;
              area?: string;
              intensity?: number;
              tracts?: string[];
              reason?: string;
              ts?: string;
            };
          } catch {
            return null;
          }
        })
        .filter(Boolean)
        .map((e) => ({
          neuron: e!.neuron ?? 'neuron.unknown',
          kind: e!.kind ?? 'agent',
          area: e!.area ?? 'area.dlpfc',
          intensity: e!.intensity ?? 0.5,
          tracts: e!.tracts ?? [],
          reason: (e!.reason ?? e!.neuron ?? 'pulse').slice(0, 64),
          ts: e!.ts ?? new Date().toISOString(),
        }));

      // Deduplicate by neuron keeping brightest
      const byId = new Map<string, (typeof firing)[0]>();
      for (const a of firing) {
        const prev = byId.get(a.neuron);
        if (!prev || a.intensity >= prev.intensity) byId.set(a.neuron, a);
      }
      const unique = [...byId.values()];
      const active_areas = [...new Set(unique.map((f) => f.area))];
      const active_tracts = [...new Set(unique.flatMap((f) => f.tracts))];

      const live = {
        at: new Date().toISOString(),
        epoch: Date.now(),
        firing: unique,
        active_areas,
        active_tracts,
        recent_tasks: this.tasks.slice(0, 12).map((t) => ({
          id: t.id,
          title: t.title,
          status: t.status,
          neuron: t.neuron,
        })),
        improve_tasks: this.tasks.filter((t) => t.status !== 'done').length,
        neuron_count: unique.length,
        firing_count: unique.length,
        standing: true,
        note: 'Cam home autonomy + converse feed',
      };
      const fingerprint = JSON.stringify({
        firing: unique.map((f) => [f.neuron, f.intensity]),
        tasks: live.recent_tasks,
      });
      if (fingerprint === this.lastLiveFingerprint) return;
      this.lastLiveFingerprint = fingerprint;
      await this.runtime.writeJson('live-activity.json', live);
    } catch {
      /* best-effort */
    }
  }

  /** Keep activity-events.jsonl from growing without bound. */
  private async trimActivityLog(): Promise<void> {
    try {
      const eventsPath = this.runtime.pathFor('activity-events.jsonl');
      const raw = await readFile(eventsPath, 'utf8');
      const lines = raw.trim().split('\n').filter(Boolean);
      if (lines.length <= 120) return;
      await writeFile(eventsPath, `${lines.slice(-80).join('\n')}\n`, 'utf8');
    } catch {
      /* missing or busy */
    }
  }
}
