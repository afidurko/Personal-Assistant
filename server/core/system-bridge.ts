/**
 * System bridge — organism bus: identity → HMO recall → connectome kernel →
 * dual-stream activity → causal motors → plasticity → workspace broadcast.
 */
import { existsSync, readdirSync } from 'node:fs';
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import type { RuntimeStore } from './runtime-store.js';
import { ConnectomeKernel, type ConnectomeRoute } from './connectome-kernel.js';
import { MotorExecutor, type ExecutionReport } from './motor-executor.js';

export type PieceStatus = 'healthy' | 'warning' | 'critical' | 'unknown';

export interface SystemPieceReport {
  id: string;
  title: string;
  layer: string;
  status: PieceStatus;
  detail?: string;
  latency_ms?: number;
  slo?: { max_latency_ms?: number; probe?: string };
}

export interface SystemStatus {
  ok: boolean;
  overall: PieceStatus;
  at: string;
  assistant: string;
  pieces: SystemPieceReport[];
  bus: Record<string, string>;
  session_id?: string;
  scanning?: boolean;
  listening?: boolean;
  last_route?: ConnectomeRoute | null;
  last_execution?: ExecutionReport | null;
  circadian?: { quiet: boolean; intensity: number };
  blockers?: string[];
}

export interface ActivityRow {
  ts: string;
  neuron: string;
  kind: string;
  area: string;
  intensity: number;
  tracts: string[];
  reason: string;
  source: string;
}

export interface TurnBridgeResult {
  route: ConnectomeRoute;
  activities: ActivityRow[];
  execution: ExecutionReport;
  memory: { tier: string; hits: Array<{ path: string; title: string }> };
}

interface PiecesConfig {
  version?: number;
  assistant?: string;
  bus?: Record<string, string>;
  pieces?: Array<{
    id: string;
    title: string;
    layer: string;
    paths?: string[];
    depends_on?: string[];
    check?: string;
    slo?: { max_latency_ms?: number; probe?: string };
  }>;
  boot_order?: string[];
  blockers?: string[];
}

type ActivityListener = (payload: {
  live: Record<string, unknown>;
  activities: ActivityRow[];
  route?: ConnectomeRoute | null;
}) => void;

export class SystemBridge {
  private lastRoute: ConnectomeRoute | null = null;
  private lastExecution: ExecutionReport | null = null;
  private piecesCache: PiecesConfig | null = null;
  private readonly kernel: ConnectomeKernel;
  private readonly motors: MotorExecutor;
  private listeners = new Set<ActivityListener>();

  constructor(
    private readonly rootDir: string,
    private readonly runtime: RuntimeStore,
  ) {
    this.kernel = new ConnectomeKernel(rootDir);
    this.motors = new MotorExecutor(rootDir, runtime);
  }

  onActivity(fn: ActivityListener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  async loadPieces(): Promise<PiecesConfig> {
    if (this.piecesCache) return this.piecesCache;
    try {
      const raw = await readFile(path.join(this.rootDir, 'config/system/pieces.json'), 'utf8');
      this.piecesCache = JSON.parse(raw) as PiecesConfig;
    } catch {
      this.piecesCache = { pieces: [], bus: {}, assistant: 'Cam' };
    }
    return this.piecesCache;
  }

  getLastRoute(): ConnectomeRoute | null {
    return this.lastRoute;
  }

  /** In-process connectome route (no Python spawn). */
  async routeSense(
    sense: string,
    goal = '',
    extra: {
      source?: string;
      aaronVoiceScore?: number | null;
      notAaron?: boolean;
      kill?: boolean;
      actHint?: 'speak' | 'docs' | 'research' | 'default';
    } = {},
  ): Promise<ConnectomeRoute> {
    const result = await this.kernel.route({
      sense,
      goal,
      source: extra.source,
      aaronVoiceScore: extra.aaronVoiceScore,
      notAaron: extra.notAaron,
      kill: extra.kill,
      actHint: extra.actHint ?? 'speak',
    });
    this.lastRoute = result;
    return result;
  }

  async onTurn(
    text: string,
    source: string,
    opts: { aaronVoiceScore?: number | null } = {},
  ): Promise<TurnBridgeResult> {
    const sense = source === 'mic' || source === 'speech' ? 'sense.ios.mic' : 'sense.chat.aaron';
    const goal = (text || '').trim().slice(0, 240) || 'converse';

    const memory = await this.hmoRecall(goal);
    const route = await this.routeSense(sense, goal, {
      source,
      aaronVoiceScore: opts.aaronVoiceScore,
      actHint: 'speak',
    });

    let activities: ActivityRow[] = [];
    if (route.accepted) {
      activities = await this.emitConverseTurn(source, route);
    } else {
      activities = [
        row(
          'neuron.qa',
          'agent',
          'area.cingulate',
          0.9,
          ['tract.cingulum'],
          route.reason || 'turn_rejected',
        ),
      ];
      await this.appendActivities(activities);
      await this.refreshLiveActivity(activities);
    }

    const execution = await this.motors.execute(route, { goal });
    this.lastExecution = execution;

    this.notify(activities, route);
    return { route, activities, execution, memory };
  }

  async onMicSpike(purpose = 'conversation'): Promise<TurnBridgeResult> {
    const route = await this.routeSense('sense.ios.mic', purpose, {
      source: 'mic',
      aaronVoiceScore: 1,
      actHint: 'speak',
    });
    const activities = route.accepted
      ? await this.emitMicSpike()
      : [
          row('neuron.qa', 'agent', 'area.cingulate', 0.8, ['tract.cingulum'], 'mic_rejected'),
        ];
    if (!route.accepted) {
      await this.appendActivities(activities);
      await this.refreshLiveActivity(activities);
    }
    const execution = await this.motors.execute(route, { goal: purpose });
    this.lastExecution = execution;
    this.notify(activities, route);
    return {
      route,
      activities,
      execution,
      memory: { tier: 'primary', hits: [] },
    };
  }

  async onCameraSpike(purpose = 'presence'): Promise<TurnBridgeResult> {
    const route = await this.routeSense('sense.ios.camera', purpose, {
      source: 'camera',
      actHint: 'default',
    });
    const activities = route.accepted
      ? await this.emitCameraSpike()
      : [
          row('neuron.qa', 'agent', 'area.cingulate', 0.8, ['tract.cingulum'], 'camera_rejected'),
        ];
    if (!route.accepted) {
      await this.appendActivities(activities);
      await this.refreshLiveActivity(activities);
    }
    const execution = await this.motors.execute(route, { goal: purpose });
    this.lastExecution = execution;
    this.notify(activities, route);
    return {
      route,
      activities,
      execution,
      memory: { tier: 'primary', hits: [] },
    };
  }

  async emitConverseTurn(source: string, route?: ConnectomeRoute): Promise<ActivityRow[]> {
    const tracts =
      route?.dual_stream.tracts?.length
        ? route.dual_stream.tracts.slice(0, 5)
        : ['tract.arcuate', 'tract.af_anterior', 'tract.af_posterior', 'tract.fat'];
    const intensity = route?.circadian?.intensity ?? 1;
    const rows: ActivityRow[] = [
      row('neuron.language_in', 'agent', 'area.wernicke', 0.9 * intensity, tracts, `converse_turn:${source}`),
      row(
        'neuron.speak_loop',
        'loop',
        'area.broca',
        0.95 * intensity,
        tracts,
        `dual_stream:${route?.dual_stream.winner || 'dorsal'}:speak`,
      ),
      row('neuron.comms', 'agent', 'area.broca', 0.7 * intensity, ['tract.arcuate', 'tract.fat'], 'outbound_reply'),
    ];
    if (source === 'mic' || source === 'speech') {
      rows.splice(
        1,
        0,
        row('neuron.asr', 'agent', 'area.auditory', 0.85 * intensity, ['tract.mdlf', 'tract.arcuate'], 'converse_mic'),
      );
    }
    // MAP stages that are active light their areas
    for (const stage of route?.map_plan || []) {
      if (stage.status === 'active' || stage.status === 'planned') {
        rows.push(
          row(stage.neuron, 'agent', stage.area, 0.65 * intensity, [stage.bus], `map:${stage.id}`),
        );
      }
    }
    await this.appendActivities(rows);
    await this.refreshLiveActivity(rows);
    return rows;
  }

  async emitMicSpike(): Promise<ActivityRow[]> {
    const rows = [
      row('neuron.asr', 'agent', 'area.auditory', 0.8, ['tract.mdlf', 'tract.arcuate'], 'mic_spike'),
    ];
    await this.appendActivities(rows);
    await this.refreshLiveActivity(rows);
    return rows;
  }

  async emitCameraSpike(): Promise<ActivityRow[]> {
    const rows = [
      row(
        'neuron.vision',
        'agent',
        'area.visual',
        0.85,
        ['tract.ilf', 'tract.vof', 'tract.ifof'],
        'camera_spike',
      ),
    ];
    await this.appendActivities(rows);
    await this.refreshLiveActivity(rows);
    return rows;
  }

  /** Hierarchical memory recall (primary lean context). */
  async hmoRecall(goal: string): Promise<{ tier: string; hits: Array<{ path: string; title: string }> }> {
    const hits: Array<{ path: string; title: string }> = [];
    const tokens = goal
      .toLowerCase()
      .split(/\W+/)
      .filter((t) => t.length > 3)
      .slice(0, 8);
    const roots = [
      path.join(this.rootDir, 'vault/02-Cam'),
      path.join(this.rootDir, 'vault/10-Mesh-Distillates'),
      path.join(this.rootDir, 'identity/persistence'),
    ];
    for (const root of roots) {
      if (!existsSync(root)) continue;
      try {
        const files = await walkMd(root, 40);
        for (const f of files) {
          const base = path.basename(f).toLowerCase();
          if (tokens.some((t) => base.includes(t) || f.toLowerCase().includes(t))) {
            hits.push({
              path: path.relative(this.rootDir, f),
              title: path.basename(f, path.extname(f)),
            });
          }
          if (hits.length >= 5) break;
        }
      } catch {
        /* skip */
      }
      if (hits.length >= 5) break;
    }
    // Always include persona prefs as primary
    if (!hits.find((h) => h.path.includes('PERSONA') || h.path.includes('BOUNDARIES'))) {
      const persona = path.join(this.rootDir, 'docs/PERSONA.md');
      if (existsSync(persona)) {
        hits.unshift({ path: 'docs/PERSONA.md', title: 'PERSONA' });
      }
    }
    return { tier: 'primary', hits: hits.slice(0, 5) };
  }

  async status(opts: {
    sessionId?: string;
    scanning?: boolean;
    listening?: boolean;
  } = {}): Promise<SystemStatus> {
    const cfg = await this.loadPieces();
    const reports: SystemPieceReport[] = [];

    for (const piece of cfg.pieces ?? []) {
      const t0 = Date.now();
      const missing = (piece.paths ?? []).filter((p) => !existsSync(path.join(this.rootDir, p)));
      let status: PieceStatus = 'healthy';
      let detail: string | undefined;
      if (missing.length === (piece.paths ?? []).length && (piece.paths ?? []).length > 0) {
        status = 'critical';
        detail = `missing: ${missing.slice(0, 3).join(', ')}`;
      } else if (missing.length > 0) {
        status = 'warning';
        detail = `partial: ${missing.slice(0, 3).join(', ')}`;
      }
      for (const p of piece.paths ?? []) {
        if (p.startsWith('integrations/') && !p.includes('.')) {
          const full = path.join(this.rootDir, p);
          if (existsSync(full) && isEmptyDirSync(full)) {
            status = status === 'critical' ? status : 'warning';
            detail = detail ?? `submodule empty: ${p}`;
          }
        }
      }
      // SLO probe: path existence latency only (cheap)
      const latency = Date.now() - t0;
      if (piece.slo?.max_latency_ms && latency > piece.slo.max_latency_ms) {
        status = status === 'critical' ? status : 'warning';
        detail = `${detail ? detail + '; ' : ''}slo latency ${latency}ms`;
      }
      reports.push({
        id: piece.id,
        title: piece.title,
        layer: piece.layer,
        status,
        detail,
        latency_ms: latency,
        slo: piece.slo,
      });
    }

    // Tailscale callosum probe
    const tsPath = path.join(this.rootDir, 'config/network/tailscale.json');
    if (existsSync(tsPath)) {
      try {
        const ts = JSON.parse(await readFile(tsPath, 'utf8')) as {
          enabled?: boolean;
          converse?: { cam_host_tailscale_ip?: string };
        };
        const hasIp = Boolean(ts.converse?.cam_host_tailscale_ip);
        reports.push({
          id: 'piece.tailscale_callosum',
          title: 'Tailscale corpus callosum',
          layer: 'network',
          status: ts.enabled ? (hasIp ? 'healthy' : 'warning') : 'warning',
          detail: hasIp ? 'host ip configured' : 'MagicDNS / IP not set on this host',
        });
      } catch {
        /* skip */
      }
    }

    const ranks: Record<PieceStatus, number> = {
      healthy: 0,
      unknown: 1,
      warning: 2,
      critical: 3,
    };
    let overall: PieceStatus = 'healthy';
    for (const r of reports) {
      if (ranks[r.status] > ranks[overall]) overall = r.status;
    }

    const circadian = this.lastRoute?.circadian ?? { quiet: false, intensity: 1 };

    return {
      ok: overall !== 'critical',
      overall,
      at: new Date().toISOString(),
      assistant: cfg.assistant ?? 'Cam',
      pieces: reports,
      bus: cfg.bus ?? {},
      session_id: opts.sessionId,
      scanning: opts.scanning,
      listening: opts.listening,
      last_route: this.lastRoute,
      last_execution: this.lastExecution,
      circadian,
      blockers: cfg.blockers ?? defaultBlockers(),
    };
  }

  private notify(activities: ActivityRow[], route: ConnectomeRoute | null): void {
    void this.runtime.readJson<Record<string, unknown>>('live-activity.json', {}).then((live) => {
      for (const fn of this.listeners) {
        try {
          fn({ live, activities, route });
        } catch {
          /* ignore listener errors */
        }
      }
    });
  }

  private async appendActivities(rows: ActivityRow[]): Promise<void> {
    for (const r of rows) {
      await this.runtime.appendLine('activity-events.jsonl', JSON.stringify(r));
    }
    try {
      const vaultEvents = path.join(
        this.rootDir,
        'vault/10-Mesh-Distillates/activity-events.jsonl',
      );
      await mkdir(path.dirname(vaultEvents), { recursive: true });
      for (const r of rows) {
        await appendFile(vaultEvents, `${JSON.stringify(r)}\n`, 'utf8');
      }
    } catch {
      /* best-effort */
    }
  }

  private async refreshLiveActivity(fresh: ActivityRow[]): Promise<void> {
    try {
      const prev = await this.runtime.readJson<{
        firing?: Array<Record<string, unknown>>;
      }>('live-activity.json', { firing: [] });
      const byId = new Map<string, ActivityRow>();
      for (const f of prev.firing ?? []) {
        const neuron = String(f.neuron ?? '');
        if (!neuron) continue;
        byId.set(neuron, {
          ts: String(f.ts ?? new Date().toISOString()),
          neuron,
          kind: String(f.kind ?? 'agent'),
          area: String(f.area ?? 'area.dlpfc'),
          intensity: Number(f.intensity ?? 0.5),
          tracts: Array.isArray(f.tracts) ? (f.tracts as string[]) : [],
          reason: String(f.reason ?? neuron).slice(0, 64),
          source: String(f.source ?? 'system_bridge'),
        });
      }
      for (const r of fresh) {
        const prevRow = byId.get(r.neuron);
        if (!prevRow || r.intensity >= prevRow.intensity) byId.set(r.neuron, r);
      }
      const unique = [...byId.values()];
      const live = {
        at: new Date().toISOString(),
        epoch: Date.now(),
        firing: unique.map((e) => ({
          neuron: e.neuron,
          kind: e.kind,
          area: e.area,
          intensity: e.intensity,
          tracts: e.tracts,
          reason: e.reason.slice(0, 64),
          ts: e.ts,
        })),
        active_areas: [...new Set(unique.map((e) => e.area))],
        active_tracts: [...new Set(unique.flatMap((e) => e.tracts))],
        firing_count: unique.length,
        neuron_count: unique.length,
        standing: true,
        note: 'system bridge organism bus',
      };
      await this.runtime.writeJson('live-activity.json', live);
      try {
        await writeFile(
          path.join(this.rootDir, 'vault/10-Mesh-Distillates/live-activity.json'),
          `${JSON.stringify(live, null, 2)}\n`,
          'utf8',
        );
      } catch {
        /* best-effort */
      }
    } catch {
      /* best-effort */
    }
  }
}

function row(
  neuron: string,
  kind: string,
  area: string,
  intensity: number,
  tracts: string[],
  reason: string,
): ActivityRow {
  return {
    ts: new Date().toISOString(),
    neuron,
    kind,
    area,
    intensity,
    tracts,
    reason,
    source: 'system_bridge',
  };
}

function isEmptyDirSync(p: string): boolean {
  try {
    return readdirSync(p).length === 0;
  } catch {
    return true;
  }
}

function defaultBlockers(): string[] {
  return [
    'Live FunASR / VoiceStudio weights (Aaron-voice + speak) — open PRs #14/#17',
    'Live MemoryBear API — open PR #12',
    'Live Pupil eye tracking — open PR #18',
    'Live nulltickets/nullclaw runtime (synaptic body)',
    'Local sLM/DL model weights (heuristic stubs active)',
    'Embodiment theater (cards/Joshinator/Inkbox) — open PRs #19/#20/#21',
  ];
}

async function walkMd(dir: string, limit: number): Promise<string[]> {
  const out: string[] = [];
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const e of entries) {
    if (out.length >= limit) break;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (e.name.startsWith('.')) continue;
      out.push(...(await walkMd(full, limit - out.length)));
    } else if (e.name.endsWith('.md') || e.name.endsWith('.json')) {
      out.push(full);
    }
  }
  return out;
}

// Re-export types used by server
export type { ConnectomeRoute, ExecutionReport };
