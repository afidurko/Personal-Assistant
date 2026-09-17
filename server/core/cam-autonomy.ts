/**
 * Cam background autonomy — self-improvement tasks she creates while listening.
 * Writes vault distillates so the 3D cortex live feed can light fibers.
 */
import { mkdir, readFile, writeFile, appendFile } from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import type { LoopJob, MemoryTrace, WorkspaceSnapshot } from '../../shared/types.js';

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

  constructor(private readonly rootDir: string) {}

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

    // Always keep a few open self-tasks so Cam is working in the background
    const open = this.tasks.filter((t) => t.status !== 'done');
    const slots = Math.max(0, 12 - open.length);
    const catalog = [...SELF_IMPROVE_CATALOG].sort(() => Math.random() - 0.5);

    for (const item of catalog) {
      if (spawned >= Math.min(3, slots)) break;
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

    // Advance queued → running → done
    for (const task of this.tasks.filter((t) => t.status !== 'done').slice(0, 8)) {
      if (task.status === 'queued') {
        task.status = 'running';
        task.updatedAt = new Date().toISOString();
        advanced += 1;
      } else if (task.status === 'running' && Math.random() > 0.35) {
        task.status = 'done';
        task.updatedAt = new Date().toISOString();
        advanced += 1;
      }
      activityEvents += await this.emitActivity(task, input.listening ?? false);
    }

    // Cap history but leave generous room for spawn
    this.tasks = this.tasks.slice(0, 64);
    await this.persistImproveTasks(input.loopJobs ?? []);
    await this.refreshLiveActivity();

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
      const dir = path.join(this.rootDir, 'vault/10-Mesh-Distillates');
      await mkdir(dir, { recursive: true });
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
      await appendFile(path.join(dir, 'activity-events.jsonl'), `${JSON.stringify(row)}\n`, 'utf8');
      return 1;
    } catch {
      return 0;
    }
  }

  private async persistImproveTasks(loopJobs: LoopJob[]): Promise<void> {
    try {
      const dir = path.join(this.rootDir, 'vault/10-Mesh-Distillates');
      await mkdir(dir, { recursive: true });
      const payload = {
        updatedAt: new Date().toISOString(),
        camSelfTasks: this.getTasks(),
        loopJobs: loopJobs.slice(0, 40),
        capacity: { selfTaskSlots: 64, loopJobHint: 80, note: 'Room for Cam and her spawn' },
      };
      await writeFile(path.join(dir, 'improve-tasks.json'), JSON.stringify(payload, null, 2), 'utf8');
    } catch {
      /* best-effort */
    }
  }

  private async refreshLiveActivity(): Promise<void> {
    try {
      const dir = path.join(this.rootDir, 'vault/10-Mesh-Distillates');
      const eventsPath = path.join(dir, 'activity-events.jsonl');
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
      await writeFile(path.join(dir, 'live-activity.json'), JSON.stringify(live, null, 2), 'utf8');
    } catch {
      /* best-effort */
    }
  }
}
