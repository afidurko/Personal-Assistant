/**
 * Sentinel — sole permission authority at Cam's motor boundary (Muse pattern).
 * Mirrors scripts/cam_sentinel.py + scripts/cam_journal.py for in-process turns:
 * switches strip first, Sentinel decides allow / ask / deny on what survives,
 * and every intent is journaled append-only BEFORE the effect runs.
 */
import { createHash } from 'node:crypto';
import { appendFile, mkdir, readFile } from 'node:fs/promises';
import path from 'node:path';

export type SentinelDecision = 'allow' | 'ask' | 'deny';

export interface SentinelRow {
  class: string | null;
  decision: SentinelDecision;
  reason: string;
  authorizer?: string;
  tainted?: boolean;
  grant_options?: string[];
  grant_id?: string;
  grant_scope?: string;
  private_path?: string;
}

export interface SentinelVerdict {
  authority: 'sentinel';
  enforced: boolean;
  taint: { tainted: boolean; sources: string[] };
  private_path?: string | null;
  decisions: Record<string, SentinelRow>;
  allowed: string[];
  pending: string[];
  denied: string[];
}

export interface SentinelPolicy {
  enforce?: boolean;
  sole_operator?: string;
  classes: Record<string, { default?: SentinelDecision; motors?: string[] }>;
  unknown_motor_decision?: SentinelDecision;
  taint?: {
    untrusted_senses?: string[];
    taint_on_motors?: string[];
    classes_lose_auto_allow?: string[];
  };
  standing_grants?: Array<{
    id?: string;
    switch?: string;
    covers?: string[];
    scope?: string;
    granted_by?: string;
    covers_tainted?: boolean;
  }>;
  grant_scopes?: string[];
  tainted_grant_scopes?: string[];
  private_memory?: {
    paths?: string[];
    deny_classes?: string[];
    deny_motors?: string[];
  };
  grants_file?: string;
  session_file?: string;
  journal_dir?: string;
}

export interface Grant {
  id?: string;
  motor?: string;
  scope?: string;
  granted_by?: string;
  covers_tainted?: boolean;
  task?: string;
  until?: string;
  session_id?: string;
}

let cachedPolicy: SentinelPolicy | null = null;

export async function loadSentinelPolicy(rootDir: string): Promise<SentinelPolicy> {
  if (cachedPolicy) return cachedPolicy;
  const raw = await readFile(path.join(rootDir, 'config/connectome/sentinel-policy.json'), 'utf8');
  cachedPolicy = JSON.parse(raw) as SentinelPolicy;
  return cachedPolicy;
}

export async function loadGrants(rootDir: string, policy: SentinelPolicy): Promise<Grant[]> {
  try {
    const raw = await readFile(
      path.join(rootDir, policy.grants_file || 'data/runtime/sentinel-grants.json'),
      'utf8',
    );
    const doc = JSON.parse(raw) as { grants?: Grant[] };
    return doc.grants || [];
  } catch {
    return [];
  }
}

export async function currentSessionId(rootDir: string, policy: SentinelPolicy): Promise<string | null> {
  try {
    const raw = await readFile(
      path.join(rootDir, policy.session_file || 'data/runtime/sentinel-session.json'),
      'utf8',
    );
    return (JSON.parse(raw) as { session_id?: string }).session_id ?? null;
  } catch {
    return null;
  }
}

function classOf(motor: string, policy: SentinelPolicy): string | null {
  for (const [name, spec] of Object.entries(policy.classes || {})) {
    if ((spec.motors || []).includes(motor)) return name;
  }
  return null;
}

export function taintFor(
  sense: string,
  pathway: string[],
  motorPlan: string[],
  policy: SentinelPolicy,
): { tainted: boolean; sources: string[] } {
  const untrusted = new Set(policy.taint?.untrusted_senses || []);
  const taintMotors = new Set(policy.taint?.taint_on_motors || []);
  const sources: string[] = [];
  for (const node of [sense, ...pathway]) {
    if (untrusted.has(node) && !sources.includes(node)) sources.push(node);
  }
  for (const m of motorPlan) {
    if (taintMotors.has(m) && !sources.includes(m)) sources.push(m);
  }
  return { tainted: sources.length > 0, sources };
}

function grantMatches(
  g: Grant,
  motor: string,
  ctx: { task: string; now: number; sessionId: string | null; tainted: boolean },
): boolean {
  if (g.motor !== motor && g.motor !== '*') return false;
  if (ctx.tainted && !g.covers_tainted) return false;
  switch (g.scope) {
    case 'once':
    case 'perpetual':
      return true;
    case 'task':
      return !!ctx.task && g.task === ctx.task;
    case 'until': {
      const exp = g.until ? Date.parse(g.until) : NaN;
      return Number.isFinite(exp) && ctx.now < exp;
    }
    case 'session':
      return !!ctx.sessionId && g.session_id === ctx.sessionId;
    default:
      return false;
  }
}

/** First plan path inside private memory (mirrors cam_sentinel._private_hit). */
export function privatePathHit(paths: string[] | undefined, policy: SentinelPolicy, rootDir = ''): string | null {
  const globs = policy.private_memory?.paths || [];
  if (!globs.length || !paths?.length) return null;
  const root = rootDir ? rootDir.replace(/\\/g, '/').replace(/\/+$/, '') + '/' : '';
  for (const raw of paths) {
    let rel = String(raw).replace(/\\/g, '/');
    if (root && rel.startsWith(root)) rel = rel.slice(root.length);
    while (rel.startsWith('./')) rel = rel.slice(2);
    rel = rel.replace(/^\/+/, '');
    for (const g of globs) {
      const body = g.replace(/\/+$/, '');
      if (body.startsWith('**/')) {
        if (('/' + rel + '/').includes('/' + body.slice(3) + '/')) return rel;
      } else if (rel === body || rel.startsWith(body + '/')) {
        return rel;
      }
    }
  }
  return null;
}

function privateDenies(motor: string, cls: string | null, policy: SentinelPolicy): boolean {
  const cfg = policy.private_memory || {};
  return (cfg.deny_motors || []).includes(motor) || (cls !== null && (cfg.deny_classes || []).includes(cls));
}

export function evaluateSentinel(
  motorPlan: string[],
  opts: {
    sense?: string;
    pathway?: string[];
    switchState?: Record<string, string>;
    task?: string;
    paths?: string[];
    grants?: Grant[];
    sessionId?: string | null;
    now?: number;
  },
  policy: SentinelPolicy,
): SentinelVerdict {
  const state = opts.switchState || {};
  const taint = taintFor(opts.sense || '', opts.pathway || [], motorPlan, policy);
  const lose = new Set(policy.taint?.classes_lose_auto_allow || []);
  const privatePath = privatePathHit(opts.paths, policy);
  const ctx = {
    task: opts.task || '',
    now: opts.now ?? Date.now(),
    sessionId: opts.sessionId ?? null,
    tainted: false,
  };
  const kill = state['switch.kill'] === 'act';
  const decisions: Record<string, SentinelRow> = {};
  const allowed: string[] = [];
  const pending: string[] = [];
  const denied: string[] = [];

  for (const motor of motorPlan) {
    const cls = classOf(motor, policy);
    let row: SentinelRow;
    if (kill) {
      row = { class: cls, decision: 'deny', reason: 'switch.kill act' };
    } else if (privatePath && privateDenies(motor, cls, policy)) {
      row = {
        class: cls,
        decision: 'deny',
        reason: `private memory path ${privatePath} — personal information never leaves the host`,
        private_path: privatePath,
      };
    } else if (cls === null) {
      row = {
        class: null,
        decision: policy.unknown_motor_decision || 'ask',
        reason: 'unknown motor — fail closed',
        grant_options: ['once'],
      };
    } else if ((policy.classes[cls]?.default || 'allow') === 'allow') {
      row = { class: cls, decision: 'allow', reason: `class ${cls} default allow`, authorizer: 'policy' };
    } else {
      const tainted = taint.tainted && lose.has(cls);
      const grantCtx = { ...ctx, tainted };
      const runtime = (opts.grants || []).find((g) => grantMatches(g, motor, grantCtx));
      const standing = runtime
        ? undefined
        : (policy.standing_grants || []).find(
            (sg) =>
              (sg.covers || []).includes(motor) &&
              (!tainted || sg.covers_tainted) &&
              (state[sg.switch || ''] ?? 'act') === 'act',
          );
      const g = runtime || standing;
      if (g) {
        const auth = `grant:${g.scope}:${g.granted_by}`;
        row = {
          class: cls,
          decision: 'allow',
          reason: auth,
          authorizer: auth,
          tainted,
          grant_id: g.id,
          grant_scope: g.scope,
        };
      } else {
        row = {
          class: cls,
          decision: 'ask',
          reason: tainted
            ? `tainted egress — plan read ${taint.sources.join(', ')}`
            : `class ${cls} requires Aaron grant`,
          tainted,
          grant_options: [...((tainted ? policy.tainted_grant_scopes : policy.grant_scopes) || [])],
        };
      }
    }
    decisions[motor] = row;
    if (row.decision === 'allow') allowed.push(motor);
    else if (row.decision === 'ask') pending.push(motor);
    else denied.push(motor);
  }

  return {
    authority: 'sentinel',
    enforced: policy.enforce !== false,
    taint,
    private_path: privatePath,
    decisions,
    allowed,
    pending,
    denied,
  };
}

// --- append-only intent journal (same envelope as scripts/cam_journal.py) -----

export type JournalKind =
  | 'proposed'
  | 'approval.requested'
  | 'decision_applied'
  | 'side_effect_intent'
  | 'effect.started'
  | 'effect.terminal'
  | 'session.end';

const REDACT: Array<[RegExp, string]> = [
  [/(authorization\s*[:=]\s*)([A-Za-z]+\s+)?(\S+)/gi, '$1$2[REDACTED]'],
  [/\b(bearer)\s+[A-Za-z0-9._~+/=-]{8,}/gi, '$1 [REDACTED]'],
  [/\bsk-[A-Za-z0-9_-]{8,}/g, '[REDACTED]'],
  [/\bgh[pousr]_[A-Za-z0-9]{8,}/g, '[REDACTED]'],
  [/\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g, '[REDACTED]'],
  [/-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g, '[REDACTED]'],
  [/\b([a-z0-9_]*(?:secret|token|password|api_key|apikey)[a-z0-9_]*\s*[:=]\s*)(['"]?)[^\s'",]{6,}\2/gi, '$1[REDACTED]'],
  // Personal information — mirrors the block rules in config/privacy/pii-guard.json.
  [/(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}(?![\w-])/g, '[REDACTED:email]'],
  [/(?<![\w./:-])(?:\+?1[\s.-]?)?\(?[2-9]\d{2}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w-])/g, '[REDACTED:phone]'],
  [/(?<![\w./:-])\+(?!1\b)\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?![\w-])/g, '[REDACTED:phone]'],
  [/(?<!\d)(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}(?!\d)/g, '[REDACTED:ssn]'],
  [/\b\d{1,6}\s+(?:[A-Z][a-z]+\s+){1,3}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl|Terrace|Ter|Parkway|Pkwy|Highway|Hwy)\.?(?=[\s,.;]|$)/g, '[REDACTED:street_address]'],
  [/\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s?[A-Z]{2}\s\d{5}(?:-\d{4})?\b/g, '[REDACTED:postal_address_line]'],
  [/(?:\/Users\/(?!Shared\b|<)[A-Za-z0-9._-]{2,}|\/home\/(?!ubuntu\b|runner\b|user\b|node\b|<|\$)[A-Za-z0-9._-]{2,})/g, '[REDACTED:home_path]'],
  [/\b(?:Africa|America|Antarctica|Asia|Atlantic|Australia|Europe|Indian|Pacific)\/[A-Z][A-Za-z_]+(?:\/[A-Z][A-Za-z_]+)?\b/g, '[REDACTED:operator_timezone]'],
  [/\b(?:goatee|mo?ustache|buzz[ -]?cut|tattoos?|olive[ -]skin|skin tone|facial hair|clean[ -]shaven|selfie|glasses glare|birthmark|eye colou?r|hair colou?r)\b/gi, '[REDACTED:physical_description]'],
  [/\baaron-\d{2}[a-z0-9-]*\.(?:jpe?g|png|heic|mov|mp4|m4a|wav)\b/g, '[REDACTED:enrollment_media_ref]'],
];

const SECRET_KEY = /(secret|token|password|passwd|api_key|apikey|private_key|credential)/i;
/** Keys whose values are personal by nature — blanked regardless of content (mirrors privacy.scrub_obj). */
const PRIVATE_KEY = /^(?:timezone|tz|phone|phone_number|mobile|email|e-mail|address|street|home_address|dob|date_of_birth|birthday|ssn|passport|licen[cs]e|latitude|longitude|lat|lng|lon|voiceprint|faceprint|embedding|embeddings|face_vector|voice_vector)$/i;

export function redact(text: string): string {
  let out = text;
  for (const [pat, rep] of REDACT) out = out.replace(pat, rep);
  return out;
}

/** Same walk as cam_journal._redact_obj: scan strings, blank any secret-named key. */
export function redactObject<T>(obj: T): T {
  if (typeof obj === 'string') return redact(obj) as T;
  if (Array.isArray(obj)) return obj.map((x) => redactObject(x)) as T;
  if (obj && typeof obj === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      const empty = v === null || v === undefined || v === '' || (Array.isArray(v) && !v.length);
      if (SECRET_KEY.test(k) && !empty) out[k] = '[REDACTED]';
      else if (PRIVATE_KEY.test(k) && !empty && v !== 'operator_local') out[k] = '[REDACTED:private_field]';
      else out[k] = redactObject(v);
    }
    return out as T;
  }
  return obj;
}

export class IntentJournal {
  private lastSeq: Record<string, number> = {};

  constructor(
    private readonly rootDir: string,
    private readonly journalDir = 'data/runtime/journal',
  ) {}

  private fileFor(day: string): string {
    return path.join(this.rootDir, this.journalDir, `${day}.jsonl`);
  }

  private async nextSequence(day: string, file: string): Promise<number> {
    if (this.lastSeq[day] === undefined) {
      let last = 0;
      try {
        const lines = (await readFile(file, 'utf8')).trim().split('\n');
        for (let i = lines.length - 1; i >= 0; i--) {
          try {
            last = Number((JSON.parse(lines[i]!) as { sequence?: number }).sequence || 0);
            break;
          } catch {
            /* skip unparseable tail */
          }
        }
      } catch {
        last = 0;
      }
      this.lastSeq[day] = last;
    }
    this.lastSeq[day] = (this.lastSeq[day] ?? 0) + 1;
    return this.lastSeq[day]!;
  }

  async append(
    kind: JournalKind,
    payload: Record<string, unknown>,
    sessionId = 'home',
  ): Promise<{ sequence: number; recorded_at: string }> {
    const now = new Date();
    const day = now.toISOString().slice(0, 10);
    const file = this.fileFor(day);
    await mkdir(path.dirname(file), { recursive: true });
    const sequence = await this.nextSequence(day, file);
    const env = {
      kind,
      payload: redactObject(JSON.parse(JSON.stringify(payload)) as Record<string, unknown>),
      recorded_at: now.toISOString(),
      sequence,
      session_id: sessionId,
    };
    await appendFile(file, `${JSON.stringify(env)}\n`, 'utf8');
    return { sequence, recorded_at: env.recorded_at };
  }
}

export function idempotencyKey(motor: string, ...parts: string[]): string {
  // Same material + digest as scripts/cam_journal.py so both runtimes share one ledger key space.
  const digest = createHash('sha256').update([motor, ...parts].join('|'), 'utf8').digest('hex');
  return `${motor}:${digest.slice(0, 12)}`;
}
