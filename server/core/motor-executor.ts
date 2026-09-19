/**
 * Causal motor executor — accepted plans leave world deltas (mesh/vault/activity).
 * Dangerous motors (outbound, jobs, enhance, cline) stay dry-run unless explicitly armed.
 */
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import type { RuntimeStore } from './runtime-store.js';
import type { ConnectomeRoute } from './connectome-kernel.js';

export interface MotorResult {
  motor: string;
  status: 'executed' | 'dry_run' | 'skipped' | 'denied' | 'error';
  detail: string;
  delta?: Record<string, unknown>;
}

export interface ExecutionReport {
  at: string;
  results: MotorResult[];
  plasticity: { ltp: string[]; ltd: string[] };
  workspace_packet?: Record<string, unknown> | null;
}

const LIVE_SAFE = new Set([
  'motor.mesh',
  'motor.vault',
  'motor.slm',
  'motor.dl',
  'motor.public_apis',
  'motor.tool',
]);

const ALWAYS_DRY = new Set([
  'motor.text',
  'motor.call',
  'motor.facetime',
  'motor.jobs',
  'motor.enhance',
  'motor.cline',
  'motor.speak',
  'motor.jarvis',
  'motor.calendar',
  'motor.docs',
  'motor.web_fetch',
]);

export class MotorExecutor {
  constructor(
    private readonly rootDir: string,
    private readonly runtime: RuntimeStore,
  ) {}

  async execute(route: ConnectomeRoute, opts: { goal?: string } = {}): Promise<ExecutionReport> {
    const results: MotorResult[] = [];
    const ltp: string[] = [];
    const ltd: string[] = [];

    if (!route.accepted) {
      for (const t of route.tracts) ltd.push(t);
      await this.writePlasticity(ltp, ltd, 'route_rejected');
      return {
        at: new Date().toISOString(),
        results: [
          {
            motor: '*',
            status: 'denied',
            detail: route.reason || 'route not accepted',
          },
        ],
        plasticity: { ltp, ltd },
        workspace_packet: null,
      };
    }

    for (const motor of route.motor_plan) {
      if (ALWAYS_DRY.has(motor) || !LIVE_SAFE.has(motor)) {
        results.push({
          motor,
          status: 'dry_run',
          detail: 'gated / not auto-executed in home bridge',
        });
        continue;
      }
      try {
        const r = await this.runSafe(motor, route, opts.goal || route.goal);
        results.push(r);
        if (r.status === 'executed') {
          for (const t of route.tracts.slice(0, 4)) ltp.push(t);
        } else if (r.status === 'error') {
          for (const t of route.tracts.slice(0, 2)) ltd.push(t);
        }
      } catch (e) {
        results.push({
          motor,
          status: 'error',
          detail: String(e),
        });
        for (const t of route.tracts.slice(0, 2)) ltd.push(t);
      }
    }

    // Trajectory violations → LTD on ACC bus
    if (route.trajectory_violations.length) {
      ltd.push('tract.cingulum');
    }

    await this.writePlasticity(ltp, ltd, 'motor_execute');
    const packet = await this.publishWorkspace(route, results);

    return {
      at: new Date().toISOString(),
      results,
      plasticity: { ltp: [...new Set(ltp)], ltd: [...new Set(ltd)] },
      workspace_packet: packet,
    };
  }

  private async runSafe(
    motor: string,
    route: ConnectomeRoute,
    goal: string,
  ): Promise<MotorResult> {
    switch (motor) {
      case 'motor.mesh':
        return this.meshClaim(route, goal);
      case 'motor.vault':
        return this.vaultDistill(route, goal);
      case 'motor.public_apis':
        return this.publicApis(goal);
      case 'motor.slm':
        return this.slmStub(route, goal);
      case 'motor.dl':
        return this.dlStub(route, goal);
      case 'motor.tool':
        return {
          motor,
          status: 'dry_run',
          detail: 'tool registry invoke requires explicit tool id',
        };
      default:
        return { motor, status: 'skipped', detail: 'no handler' };
    }
  }

  private async meshClaim(route: ConnectomeRoute, goal: string): Promise<MotorResult> {
    const claim = {
      kind: 'mesh_claim',
      at: new Date().toISOString(),
      sense: route.sense,
      hotspot: route.hotspot_id,
      behavior: route.behavior,
      goal: goal.slice(0, 240),
      motors: route.motor_plan,
      dual_stream: route.dual_stream.winner,
      kernel: route.kernel,
      tier: 'secondary',
      namespace: 'mesh/runs',
    };
    await this.runtime.appendLine('activity-events.jsonl', JSON.stringify({
      ts: claim.at,
      neuron: 'neuron.mesh_sync_loop',
      kind: 'loop',
      area: 'area.mtl',
      intensity: 0.7,
      tracts: ['tract.fornix', 'tract.cingulum'],
      reason: 'motor.mesh claim',
      source: 'motor_executor',
    }));
    const dir = path.join(this.rootDir, 'vault/10-Mesh-Distillates/mesh-claims');
    await mkdir(dir, { recursive: true });
    const day = claim.at.slice(0, 10);
    await appendFile(path.join(dir, `${day}.jsonl`), `${JSON.stringify(claim)}\n`, 'utf8');
    return {
      motor: 'motor.mesh',
      status: 'executed',
      detail: 'mesh claim written',
      delta: { claim },
    };
  }

  private async vaultDistill(route: ConnectomeRoute, goal: string): Promise<MotorResult> {
    const dir = path.join(this.rootDir, 'vault/10-Mesh-Distillates/converse');
    await mkdir(dir, { recursive: true });
    const row = {
      at: new Date().toISOString(),
      kind: 'vault_distill',
      sense: route.sense,
      hotspot: route.hotspot_id,
      goal: goal.slice(0, 240),
      behavior: route.behavior,
    };
    await appendFile(path.join(dir, 'motor-vault.jsonl'), `${JSON.stringify(row)}\n`, 'utf8');
    return {
      motor: 'motor.vault',
      status: 'executed',
      detail: 'vault distill appended',
      delta: { row },
    };
  }

  private async publicApis(goal: string): Promise<MotorResult> {
    const q = goal.trim() || 'weather';
    const out = await runPython(this.rootDir, [
      'scripts/public-apis-search.py',
      '--query',
      q,
      '--offline',
      '--num',
      '3',
    ]);
    if (!out.ok) {
      return {
        motor: 'motor.public_apis',
        status: 'error',
        detail: out.error || 'public-apis search failed',
      };
    }
    return {
      motor: 'motor.public_apis',
      status: 'executed',
      detail: 'offline catalog search',
      delta: { preview: out.stdout.slice(0, 400) },
    };
  }

  private async slmStub(route: ConnectomeRoute, goal: string): Promise<MotorResult> {
    // Fast-path stub until local weights land — intent classify heuristic
    const g = goal.toLowerCase();
    let intent = 'general';
    if (/code|cline|refactor|typescript|python/.test(g)) intent = 'coding';
    else if (/research|paper|scholar|agi/.test(g)) intent = 'research';
    else if (/job|career|linkedin|indeed/.test(g)) intent = 'careers';
    else if (/speak|say|hello|hi /.test(g)) intent = 'presence';
    const delta = {
      model: 'cam-router-slm-heuristic',
      intent,
      hotspot_suggest: route.hotspot_id,
      status: 'planned_weights_missing',
    };
    await this.runtime.appendLine(
      'activity-events.jsonl',
      JSON.stringify({
        ts: new Date().toISOString(),
        neuron: 'neuron.slm',
        kind: 'agent',
        area: 'area.dlpfc',
        intensity: 0.55,
        tracts: ['tract.slf', 'tract.forceps_minor'],
        reason: `slm_intent:${intent}`,
        source: 'motor_executor',
      }),
    );
    return {
      motor: 'motor.slm',
      status: 'executed',
      detail: 'heuristic sLM stub (weights not installed)',
      delta,
    };
  }

  private async dlStub(route: ConnectomeRoute, goal: string): Promise<MotorResult> {
    const delta = {
      model: 'cam-vault-embed-stub',
      tokens: goal.split(/\s+/).filter(Boolean).length,
      hotspot: route.hotspot_id,
      status: 'planned_weights_missing',
    };
    await this.runtime.appendLine(
      'activity-events.jsonl',
      JSON.stringify({
        ts: new Date().toISOString(),
        neuron: 'neuron.dl',
        kind: 'agent',
        area: 'area.temporal',
        intensity: 0.5,
        tracts: ['tract.ilf', 'tract.ifof'],
        reason: 'dl_embed_stub',
        source: 'motor_executor',
      }),
    );
    return {
      motor: 'motor.dl',
      status: 'executed',
      detail: 'embedding stub (weights not installed)',
      delta,
    };
  }

  private async writePlasticity(ltp: string[], ltd: string[], reason: string): Promise<void> {
    try {
      const weights = await this.runtime.readJson<Record<string, number>>('tract-weights.json', {});
      for (const t of ltp) {
        weights[t] = Math.min(1, (weights[t] ?? 0.5) + 0.08);
      }
      for (const t of ltd) {
        weights[t] = Math.max(0.05, (weights[t] ?? 0.5) - 0.12);
      }
      weights._updated = Date.now() as unknown as number;
      await this.runtime.writeJson('tract-weights.json', {
        ...weights,
        _meta: { at: new Date().toISOString(), reason },
      });
    } catch {
      /* best-effort */
    }
  }

  private async publishWorkspace(
    route: ConnectomeRoute,
    results: MotorResult[],
  ): Promise<Record<string, unknown> | null> {
    try {
      const packet = {
        at: new Date().toISOString(),
        sense: route.sense,
        hotspot: route.hotspot_id,
        behavior: route.behavior,
        dual_stream: route.dual_stream.winner,
        map_active: route.map_plan.filter((m) => m.status !== 'skipped').map((m) => m.id),
        motors_executed: results.filter((r) => r.status === 'executed').map((r) => r.motor),
        lease_ttl_s: 3600,
        bus: 'tract.forceps_minor',
      };
      const leasesPath = path.join(
        this.rootDir,
        'vault/10-Mesh-Distillates/workspace-leases.json',
      );
      let doc: { leases?: unknown[]; updatedAt?: string } = {};
      try {
        doc = JSON.parse(await readFile(leasesPath, 'utf8')) as typeof doc;
      } catch {
        doc = { leases: [] };
      }
      const leases = Array.isArray(doc.leases) ? doc.leases : [];
      leases.unshift(packet);
      doc.leases = leases.slice(0, 3);
      doc.updatedAt = packet.at;
      await writeFile(leasesPath, `${JSON.stringify(doc, null, 2)}\n`, 'utf8');
      await this.runtime.writeJson('workspace-leases.json', doc);
      return packet;
    } catch {
      return null;
    }
  }
}

function runPython(
  rootDir: string,
  args: string[],
): Promise<{ ok: boolean; stdout: string; error?: string }> {
  return new Promise((resolve) => {
    const child = spawn('python3', args, { cwd: rootDir, env: process.env });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      resolve({ ok: false, stdout, error: 'timeout' });
    }, 20_000);
    child.stdout.on('data', (d) => {
      stdout += String(d);
    });
    child.stderr.on('data', (d) => {
      stderr += String(d);
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({
        ok: code === 0,
        stdout,
        error: code === 0 ? undefined : stderr.slice(0, 200) || `exit ${code}`,
      });
    });
    child.on('error', (e) => {
      clearTimeout(timer);
      resolve({ ok: false, stdout, error: String(e) });
    });
  });
}
