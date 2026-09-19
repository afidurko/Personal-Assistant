/**
 * In-process Cam connectome kernel — sense → hotspot → switches → motor plan.
 * Mirrors scripts/connectome-route.py so live turns never shell out.
 */
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { applyTrajectoryPolicies, loadTrajectoryPolicies, type TrajectoryViolation } from './trajectory-policies.js';

export interface RouteOptions {
  sense: string;
  goal?: string;
  hotspotId?: string;
  notAaron?: boolean;
  kill?: boolean;
  noAutonomy?: boolean;
  enhance?: boolean;
  noResearchScan?: boolean;
  noSlm?: boolean;
  noDl?: boolean;
  /** Mic/voice must pass identity; text can bypass */
  aaronVoiceScore?: number | null;
  source?: string;
  actHint?: 'speak' | 'docs' | 'research' | 'default';
}

export interface MapStage {
  id: string;
  area: string;
  neuron: string;
  bus: string;
  status: 'planned' | 'active' | 'skipped';
}

export interface DualStreamResult {
  winner: 'dorsal' | 'ventral';
  act: string;
  tracts: string[];
  policy: Record<string, string>;
}

export interface ConnectomeRoute {
  accepted: boolean;
  reason?: string;
  sense: string;
  goal: string;
  area: string | null;
  center: string | null;
  columns: string[];
  tracts: string[];
  behavior: string;
  hotspot_id: string | null;
  alt_hotspots: string[];
  pathway: string[];
  switch_state: Record<string, string>;
  motor_plan: string[];
  trajectory_violations: TrajectoryViolation[];
  missing_explicit_edges: string[][];
  dual_stream: DualStreamResult;
  map_plan: MapStage[];
  circadian?: { quiet: boolean; intensity: number };
  identity?: { required: boolean; passed: boolean; score: number | null };
  kernel: 'in_process';
  persona: { name: string; voice: string; sole_operator: string };
}

interface Hotspot {
  id: string;
  pathway: string[];
  behavior: string;
  area?: string;
  center?: string;
  columns?: string[];
  tracts?: string[];
  side_effects?: string[];
}

interface ConnectomeData {
  senseIds: Set<string>;
  switches: Array<{ id: string; default?: string }>;
  effectors: Array<{ id: string; requires_switch?: string[] }>;
  hotspots: Hotspot[];
  edgePairs: Set<string>;
  dualPolicy: Record<string, string>;
  dualStreams: {
    dorsal: { tracts: string[] };
    ventral: { tracts: string[] };
  };
  mapModules: Record<string, { area: string; neuron: string; bus: string }>;
  identityThreshold: number;
  quietHours: { start: string; end: string; timezone: string } | null;
  policies: import('./trajectory-policies.js').TrajectoryPolicy[];
}

function edgeKey(a: string, b: string): string {
  return `${a}->${b}`;
}

export class ConnectomeKernel {
  private data: ConnectomeData | null = null;

  constructor(private readonly rootDir: string) {}

  async ensureLoaded(): Promise<ConnectomeData> {
    if (this.data) return this.data;
    const cfg = path.join(this.rootDir, 'config/connectome');
    const [sensory, switches, motor, hotspots, synapses, meshParams, voice, policies] =
      await Promise.all([
        readJson(path.join(cfg, 'sensory.json')),
        readJson(path.join(cfg, 'switches.json')),
        readJson(path.join(cfg, 'motor.json')),
        readJson(path.join(cfg, 'hotspots.json')),
        readJson(path.join(cfg, 'synapses.json')),
        readJson(path.join(cfg, 'mesh-params.json')),
        readJson(path.join(this.rootDir, 'config/persona/voice.json')).catch(() => ({})),
        loadTrajectoryPolicies(this.rootDir),
      ]);

    const dual = (meshParams.language_dual_stream || {}) as Record<string, unknown>;
    const policy = (dual.conflict_policy || {}) as Record<string, string>;
    const idSwitch = ((switches.switches || []) as Array<{ id: string; threshold?: number }>).find(
      (s) => s.id === 'switch.identity',
    );

    const avail = (voice as { availability?: { quiet_hours?: { start: string; end: string } | null; timezone?: string } })
      .availability;
    const qh = avail?.quiet_hours;

    this.data = {
      senseIds: new Set(((sensory.neurons || []) as Array<{ id: string }>).map((n) => n.id)),
      switches: (switches.switches || []) as Array<{ id: string; default?: string }>,
      effectors: (motor.effectors || []) as Array<{ id: string; requires_switch?: string[] }>,
      hotspots: (hotspots.hotspots || []) as Hotspot[],
      edgePairs: new Set(
        ((synapses.edges || []) as Array<{ from: string; to: string }>).map((e) =>
          edgeKey(e.from, e.to),
        ),
      ),
      dualPolicy: policy,
      dualStreams: {
        dorsal: { tracts: ((dual.dorsal as { tracts?: string[] })?.tracts || []) as string[] },
        ventral: { tracts: ((dual.ventral as { tracts?: string[] })?.tracts || []) as string[] },
      },
      mapModules: (meshParams.planning_modules_map || {}) as Record<
        string,
        { area: string; neuron: string; bus: string }
      >,
      identityThreshold: typeof idSwitch?.threshold === 'number' ? idSwitch.threshold : 0.85,
      quietHours: qh
        ? { start: qh.start, end: qh.end, timezone: avail?.timezone || 'America/New_York' }
        : null,
      policies,
    };
    return this.data;
  }

  async route(opts: RouteOptions): Promise<ConnectomeRoute> {
    const data = await this.ensureLoaded();
    const goal = opts.goal || '';
    const sense = opts.sense;

    if (!data.senseIds.has(sense)) {
      return rejected(sense, goal, `unknown sense id: ${sense}`);
    }

    if (opts.notAaron) {
      return rejected(sense, goal, 'switch.tasking hold — only Aaron may assign tasks');
    }

    // Identity gate for mic/speech sources
    const source = opts.source || 'text';
    const micLike = source === 'mic' || source === 'speech';
    const score = opts.aaronVoiceScore ?? null;
    const identityRequired = micLike;
    const identityPassed =
      !identityRequired || (typeof score === 'number' && score >= data.identityThreshold);
    if (identityRequired && !identityPassed) {
      const base = rejected(
        sense,
        goal,
        `switch.identity hold — Aaron voice required (threshold ${data.identityThreshold})`,
      );
      base.identity = { required: true, passed: false, score };
      return base;
    }

    const switchState = resolveSwitches(data.switches, {
      kill: !!opts.kill,
      autonomy: !opts.noAutonomy,
      enhance: !!opts.enhance,
      researchScan: !opts.noResearchScan,
      slm: !opts.noSlm,
      dl: !opts.noDl,
    });

    const effectorReqs: Record<string, string[]> = {};
    for (const e of data.effectors) {
      effectorReqs[e.id] = e.requires_switch || [];
    }

    const candidates = hotspotsForSense(data.hotspots, sense);
    const hotspot = pickHotspot(candidates, goal, opts.hotspotId);

    let pathway: string[];
    let planned: string[];
    let behavior: string;
    let center: string | null;
    let columns: string[];
    let tracts: string[];

    if (hotspot) {
      pathway = [...hotspot.pathway];
      planned = motorsFromPathway(pathway, switchState, effectorReqs);
      for (const side of hotspot.side_effects || []) {
        if (!planned.includes(side) && motorAllowed(side, effectorReqs, switchState)) {
          planned.push(side);
        }
      }
      behavior = hotspot.behavior;
      center = hotspot.area || hotspot.center || null;
      columns = hotspot.columns || [];
      tracts = hotspot.tracts || [];
    } else {
      pathway = [sense, 'area.wernicke', 'area.dlpfc', 'area.mtl', 'switch.autonomy', 'motor.mesh'];
      planned = motorAllowed('motor.mesh', effectorReqs, switchState) ? ['motor.mesh'] : [];
      behavior = 'generic_integrate_and_remember';
      center = 'area.dlpfc';
      columns = [];
      tracts = [];
    }

    const known = new Set(data.effectors.map((e) => e.id));
    planned = planned.filter((m) => known.has(m));

    const { plan, violations } = applyTrajectoryPolicies(planned, switchState, data.policies);

    const missing: string[][] = [];
    for (let i = 0; i < pathway.length - 1; i++) {
      const a = pathway[i]!;
      const b = pathway[i + 1]!;
      if (!data.edgePairs.has(edgeKey(a, b))) missing.push([a, b]);
    }

    const actHint = inferAct(opts.actHint, goal, behavior);
    const dual = resolveDualStream(data, actHint);
    // Prefer dual-stream tracts when hotspot tracts empty
    if (!tracts.length) tracts = dual.tracts.slice(0, 5);

    const mapPlan = buildMapPlan(data.mapModules, goal, behavior);
    const circadian = resolveCircadian(data.quietHours);

    let accepted = true;
    let reason: string | undefined;
    let motorPlan = plan;
    if (opts.kill || switchState['switch.kill'] === 'act') {
      accepted = false;
      reason = 'switch.kill act — all motor silenced';
      motorPlan = [];
    }

    return {
      accepted,
      reason,
      sense,
      goal,
      area: center,
      center,
      columns,
      tracts,
      behavior,
      hotspot_id: hotspot?.id ?? null,
      alt_hotspots: candidates.filter((h) => h.id !== hotspot?.id).map((h) => h.id),
      pathway,
      switch_state: switchState,
      motor_plan: motorPlan,
      trajectory_violations: violations,
      missing_explicit_edges: missing.slice(0, 10),
      dual_stream: dual,
      map_plan: mapPlan,
      circadian,
      identity: {
        required: identityRequired,
        passed: identityPassed,
        score,
      },
      kernel: 'in_process',
      persona: {
        name: 'Cam',
        voice: 'soft airy fluent English',
        sole_operator: 'Aaron',
      },
    };
  }
}

function rejected(sense: string, goal: string, reason: string): ConnectomeRoute {
  return {
    accepted: false,
    reason,
    sense,
    goal,
    area: null,
    center: null,
    columns: [],
    tracts: [],
    behavior: 'rejected',
    hotspot_id: null,
    alt_hotspots: [],
    pathway: [],
    switch_state: {},
    motor_plan: [],
    trajectory_violations: [],
    missing_explicit_edges: [],
    dual_stream: {
      winner: 'dorsal',
      act: 'default',
      tracts: [],
      policy: {},
    },
    map_plan: [],
    kernel: 'in_process',
    persona: { name: 'Cam', voice: 'soft airy fluent English', sole_operator: 'Aaron' },
  };
}

function resolveSwitches(
  switches: Array<{ id: string; default?: string }>,
  opts: {
    kill: boolean;
    autonomy: boolean;
    enhance: boolean;
    researchScan: boolean;
    slm: boolean;
    dl: boolean;
  },
): Record<string, string> {
  const state: Record<string, string> = {};
  const holdWhenNoAutonomy = new Set([
    'switch.autonomy',
    'switch.outbound',
    'switch.careers_submit',
    'switch.research_scan',
    'switch.slm_local',
    'switch.dl_local',
  ]);
  for (const s of switches) {
    const sid = s.id;
    const def = (s.default || '').toLowerCase();
    if (sid === 'switch.kill') {
      state[sid] = opts.kill ? 'act' : 'armed_allow_motor';
      continue;
    }
    if (sid === 'switch.cam_enhance') {
      state[sid] = opts.enhance ? 'act' : 'hold';
      continue;
    }
    if (sid === 'switch.research_scan' && !opts.researchScan) {
      state[sid] = 'hold';
      continue;
    }
    if (sid === 'switch.slm_local' && !opts.slm) {
      state[sid] = 'hold';
      continue;
    }
    if (sid === 'switch.dl_local' && !opts.dl) {
      state[sid] = 'hold';
      continue;
    }
    if (!opts.autonomy && holdWhenNoAutonomy.has(sid)) {
      state[sid] = 'hold';
      continue;
    }
    if (def === 'hold' || def.startsWith('hold')) {
      state[sid] = 'hold';
      continue;
    }
    state[sid] = 'act';
  }
  if (opts.kill) {
    for (const sid of Object.keys(state)) {
      if (sid !== 'switch.kill') state[sid] = 'hold';
    }
    state['switch.kill'] = 'act';
  }
  return state;
}

function motorAllowed(
  motorId: string,
  effectorReqs: Record<string, string[]>,
  switchState: Record<string, string>,
): boolean {
  if (switchState['switch.kill'] === 'act') return false;
  for (const req of effectorReqs[motorId] || []) {
    if (req === 'switch.kill') {
      if (switchState['switch.kill'] === 'act') return false;
      continue;
    }
    if (switchState[req] === 'hold') return false;
  }
  return true;
}

function motorsFromPathway(
  pathway: string[],
  switchState: Record<string, string>,
  effectorReqs: Record<string, string[]>,
): string[] {
  if (switchState['switch.kill'] === 'act') return [];
  if (pathway.some((p) => p.startsWith('switch.') && switchState[p] === 'hold')) return [];
  const out: string[] = [];
  for (const p of pathway) {
    if (p.startsWith('motor.') && motorAllowed(p, effectorReqs, switchState)) out.push(p);
  }
  return out;
}

function hotspotsForSense(hotspots: Hotspot[], senseId: string): Hotspot[] {
  const primary = hotspots.filter((h) => h.pathway?.[0] === senseId);
  if (primary.length) return primary;
  return hotspots.filter((h) => (h.pathway || []).includes(senseId));
}

function pickHotspot(
  candidates: Hotspot[],
  goal: string,
  hotspotId?: string,
): Hotspot | null {
  if (!candidates.length) return null;
  if (hotspotId) return candidates.find((h) => h.id === hotspotId) || null;
  if (candidates.length === 1 || !goal) return candidates[0]!;
  const g = goal.toLowerCase();
  const scored = candidates.map((h) => {
    const blob = `${h.id} ${h.behavior} ${h.center || ''} ${h.area || ''}`.toLowerCase();
    let score = g.split(/\s+/).filter((t) => t && blob.includes(t)).length;
    if (g.includes('doc') && blob.includes('doc')) score += 3;
    if ((g.includes('research') || g.includes('brief')) && blob.includes('research')) score += 3;
    if ((g.includes('job') || g.includes('career')) && blob.includes('career')) score += 3;
    if (
      (g.includes('qa') || g.includes('conflict')) &&
      (blob.includes('qa') || blob.includes('conflict') || blob.includes('cycle'))
    )
      score += 4;
    if ((g.includes('ios') || g.includes('swift') || g.includes('stack')) &&
      (blob.includes('ios') || blob.includes('swift') || blob.includes('stack') || blob.includes('cartograph')))
      score += 4;
    if ((g.includes('agi') || g.includes('arxiv') || g.includes('paper') || g.includes('scan')) &&
      (blob.includes('agi') || blob.includes('arxiv') || blob.includes('scan')))
      score += 4;
    if ((g.includes('enhance') || g.includes('upgrade')) && blob.includes('enhance')) score += 4;
    if ((g.includes('info') || g.includes('lookup')) && blob.includes('info')) score += 3;
    if (
      ['code', 'coding', 'cline', 'refactor', 'implement', 'typescript', 'python'].some((t) =>
        g.includes(t),
      ) &&
      (blob.includes('coding') || blob.includes('cline'))
    )
      score += 5;
    if (
      ['public api', 'public-apis', 'free api', 'api catalog'].some((t) => g.includes(t)) &&
      (blob.includes('public_apis') || blob.includes('api'))
    )
      score += 5;
    return { score, h };
  });
  scored.sort((a, b) => b.score - a.score);
  return scored[0]!.h;
}

function inferAct(
  hint: RouteOptions['actHint'],
  goal: string,
  behavior: string,
): string {
  if (hint) return hint;
  const g = `${goal} ${behavior}`.toLowerCase();
  if (g.includes('doc') || g.includes('draft') || g.includes('write')) return 'docs';
  if (g.includes('research') || g.includes('scholar') || g.includes('paper')) return 'research';
  if (g.includes('speak') || g.includes('say') || g.includes('reply') || g.includes('converse'))
    return 'speak';
  return 'default';
}

function resolveDualStream(data: ConnectomeData, act: string): DualStreamResult {
  const winnerKey = data.dualPolicy[act] || data.dualPolicy.default || 'dorsal';
  const winner = winnerKey === 'ventral' ? 'ventral' : 'dorsal';
  return {
    winner,
    act,
    tracts: data.dualStreams[winner].tracts.slice(0, 6),
    policy: { ...data.dualPolicy },
  };
}

function buildMapPlan(
  modules: Record<string, { area: string; neuron: string; bus: string }>,
  goal: string,
  behavior: string,
): MapStage[] {
  const order = [
    'error_monitoring',
    'state_prediction',
    'state_evaluation',
    'task_decomposition',
    'task_coordination',
    'action_proposal',
  ];
  const needsPlan =
    goal.length > 40 ||
    /plan|build|implement|team|decompose|complete/.test(`${goal} ${behavior}`.toLowerCase());
  return order
    .filter((id) => modules[id])
    .map((id) => {
      const m = modules[id]!;
      return {
        id,
        area: m.area,
        neuron: m.neuron,
        bus: m.bus,
        status: (needsPlan ? 'planned' : id === 'action_proposal' ? 'active' : 'skipped') as MapStage['status'],
      };
    });
}

function resolveCircadian(
  quiet: ConnectomeData['quietHours'],
): { quiet: boolean; intensity: number } {
  if (!quiet) return { quiet: false, intensity: 1 };
  // Parse HH:MM in given timezone roughly via locale string
  try {
    const fmt = new Intl.DateTimeFormat('en-US', {
      timeZone: quiet.timezone,
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
    const parts = fmt.formatToParts(new Date());
    const hour = Number(parts.find((p) => p.type === 'hour')?.value || '12');
    const minute = Number(parts.find((p) => p.type === 'minute')?.value || '0');
    const now = hour * 60 + minute;
    const [sh, sm] = quiet.start.split(':').map(Number);
    const [eh, em] = quiet.end.split(':').map(Number);
    const start = (sh || 0) * 60 + (sm || 0);
    const end = (eh || 0) * 60 + (em || 0);
    let inQuiet: boolean;
    if (start <= end) inQuiet = now >= start && now < end;
    else inQuiet = now >= start || now < end;
    return { quiet: inQuiet, intensity: inQuiet ? 0.35 : 1 };
  } catch {
    return { quiet: false, intensity: 1 };
  }
}

async function readJson(file: string): Promise<Record<string, unknown>> {
  const raw = await readFile(file, 'utf8');
  return JSON.parse(raw) as Record<string, unknown>;
}
