/**
 * System bridge — wires Cam converse / sensory spikes into connectome routes
 * and live DTI activity so home UI, cortex, and Python pathways share one bus.
 */
import { spawn } from 'node:child_process';
import { existsSync, readdirSync } from 'node:fs';
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import type { RuntimeStore } from './runtime-store.js';

export type PieceStatus = 'healthy' | 'warning' | 'critical' | 'unknown';

export interface SystemPieceReport {
  id: string;
  title: string;
  layer: string;
  status: PieceStatus;
  detail?: string;
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
  last_route?: ConnectomeRouteResult | null;
}

export interface ConnectomeRouteResult {
  accepted?: boolean;
  sense?: string;
  motor_plan?: unknown[];
  error?: string;
  [key: string]: unknown;
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
  }>;
  boot_order?: string[];
}

const SPEAK_TRACTS = [
  'tract.arcuate',
  'tract.af_anterior',
  'tract.af_posterior',
  'tract.fat',
] as const;

export class SystemBridge {
  private lastRoute: ConnectomeRouteResult | null = null;
  private piecesCache: PiecesConfig | null = null;

  constructor(
    private readonly rootDir: string,
    private readonly runtime: RuntimeStore,
  ) {}

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

  getLastRoute(): ConnectomeRouteResult | null {
    return this.lastRoute;
  }

  /** Route a sensory spike through Python connectome-route (same as cam-converse-server). */
  async routeSense(sense: string, goal = ''): Promise<ConnectomeRouteResult> {
    const result = await runPythonJson(this.rootDir, [
      'scripts/connectome-route.py',
      '--sense',
      sense,
      ...(goal ? ['--goal', goal] : []),
    ]);
    this.lastRoute = result;
    return result;
  }

  async emitConverseTurn(source: string): Promise<ActivityRow[]> {
    const rows: ActivityRow[] = [
      row('neuron.language_in', 'agent', 'area.wernicke', 0.9, [...SPEAK_TRACTS], `converse_turn:${source}`),
      row('neuron.speak_loop', 'loop', 'area.broca', 0.95, [...SPEAK_TRACTS], 'dual_stream:dorsal:speak'),
      row('neuron.comms', 'agent', 'area.broca', 0.7, ['tract.arcuate', 'tract.fat'], 'outbound_reply'),
    ];
    if (source === 'mic' || source === 'speech') {
      rows.splice(
        1,
        0,
        row('neuron.asr', 'agent', 'area.auditory', 0.85, ['tract.mdlf', 'tract.arcuate'], 'converse_mic'),
      );
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

  /**
   * Full converse turn: route chat sense + light language tracts.
   * Best-effort — never throws into the HTTP handler.
   */
  async onTurn(text: string, source: string): Promise<{
    route: ConnectomeRouteResult;
    activities: ActivityRow[];
  }> {
    const sense = source === 'mic' || source === 'speech' ? 'sense.ios.mic' : 'sense.chat.aaron';
    const goal = (text || '').trim().slice(0, 120) || 'converse';
    let route: ConnectomeRouteResult = { accepted: false };
    try {
      route = await this.routeSense(sense, goal);
    } catch (e) {
      route = { accepted: false, error: String(e) };
    }
    let activities: ActivityRow[] = [];
    try {
      activities = await this.emitConverseTurn(source);
    } catch {
      activities = [];
    }
    return { route, activities };
  }

  async onMicSpike(purpose = 'conversation'): Promise<{
    route: ConnectomeRouteResult;
    activities: ActivityRow[];
  }> {
    let route: ConnectomeRouteResult = { accepted: false };
    try {
      route = await this.routeSense('sense.ios.mic', purpose);
    } catch (e) {
      route = { accepted: false, error: String(e) };
    }
    const activities = await this.emitMicSpike().catch(() => [] as ActivityRow[]);
    return { route, activities };
  }

  async onCameraSpike(purpose = 'presence'): Promise<{
    route: ConnectomeRouteResult;
    activities: ActivityRow[];
  }> {
    let route: ConnectomeRouteResult = { accepted: false };
    try {
      route = await this.routeSense('sense.ios.camera', purpose);
    } catch (e) {
      route = { accepted: false, error: String(e) };
    }
    const activities = await this.emitCameraSpike().catch(() => [] as ActivityRow[]);
    return { route, activities };
  }

  async status(opts: {
    sessionId?: string;
    scanning?: boolean;
    listening?: boolean;
  } = {}): Promise<SystemStatus> {
    const cfg = await this.loadPieces();
    const reports: SystemPieceReport[] = [];

    for (const piece of cfg.pieces ?? []) {
      const missing = (piece.paths ?? []).filter((p) => !pathExistsSync(path.join(this.rootDir, p)));
      let status: PieceStatus = 'healthy';
      let detail: string | undefined;
      if (missing.length === (piece.paths ?? []).length && (piece.paths ?? []).length > 0) {
        status = 'critical';
        detail = `missing: ${missing.slice(0, 3).join(', ')}`;
      } else if (missing.length > 0) {
        // Soft: empty submodule dirs still "exist" — check emptiness for integrations/
        const softEmpty = missing.length === 0 ? [] : missing;
        if (softEmpty.length) {
          status = 'warning';
          detail = `partial: ${missing.slice(0, 3).join(', ')}`;
        }
      }
      // Empty integration checkouts
      for (const p of piece.paths ?? []) {
        if (p.startsWith('integrations/') && !p.includes('.')) {
          const full = path.join(this.rootDir, p);
          if (pathExistsSync(full) && isEmptyDirSync(full)) {
            status = status === 'critical' ? status : 'warning';
            detail = detail ?? `submodule empty: ${p}`;
          }
        }
      }
      reports.push({
        id: piece.id,
        title: piece.title,
        layer: piece.layer,
        status,
        detail,
      });
    }

    // Glue piece must be present
    const bridgePath = path.join(this.rootDir, 'server/core/system-bridge.ts');
    if (!pathExistsSync(bridgePath)) {
      reports.push({
        id: 'piece.system_bridge',
        title: 'System bridge',
        layer: 'glue',
        status: 'critical',
        detail: 'system-bridge.ts missing',
      });
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
    };
  }

  private async appendActivities(rows: ActivityRow[]): Promise<void> {
    for (const r of rows) {
      await this.runtime.appendLine('activity-events.jsonl', JSON.stringify(r));
    }
    // Mirror into vault distillates so Python health/feed tools stay aligned
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
        note: 'system bridge: converse + connectome',
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

function pathExistsSync(p: string): boolean {
  return existsSync(p);
}

function isEmptyDirSync(p: string): boolean {
  try {
    return readdirSync(p).length === 0;
  } catch {
    return true;
  }
}

function runPythonJson(rootDir: string, scriptAndArgs: string[]): Promise<ConnectomeRouteResult> {
  return new Promise((resolve) => {
    const child = spawn('python3', scriptAndArgs, {
      cwd: rootDir,
      env: process.env,
    });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      resolve({ accepted: false, error: 'connectome-route timeout' });
    }, 12_000);
    child.stdout.on('data', (d) => {
      stdout += String(d);
    });
    child.stderr.on('data', (d) => {
      stderr += String(d);
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      try {
        const start = stdout.indexOf('{');
        const end = stdout.lastIndexOf('}');
        if (start >= 0 && end > start) {
          resolve(JSON.parse(stdout.slice(start, end + 1)) as ConnectomeRouteResult);
          return;
        }
      } catch {
        /* fall through */
      }
      resolve({
        accepted: false,
        error: code === 0 ? 'no_json' : stderr.slice(0, 200) || `exit ${code}`,
      });
    });
    child.on('error', (e) => {
      clearTimeout(timer);
      resolve({ accepted: false, error: String(e) });
    });
  });
}
