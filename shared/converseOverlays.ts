/**
 * Converse overlays — pure matcher shared by the TS home server and (via a
 * vanilla mirror) the web companion. Semantics must stay identical to
 * scripts/converse_overlays.py; scripts/converse-parity-check.py proves it.
 *
 * Keep this file import-free and free of TS-only runtime syntax (enums,
 * parameter properties) so Node can load it with --experimental-strip-types.
 */

export interface OverlayRule {
  id: string;
  any?: string[];
  words?: string[];
  all_groups?: string[][];
  must_contain?: string[];
  probes?: string[];
  reply: string;
}

export interface SpeakParams {
  rate: number;
  pitch: number;
  lang: string;
  style?: string;
}

export interface ConverseOverlaysConfig {
  version?: number;
  id?: string;
  speak?: Partial<SpeakParams>;
  empty?: string;
  overlays?: OverlayRule[];
  intent_rules?: Record<string, { regex?: string }>;
  intent_order?: string[];
  intents?: Record<string, string>;
  intent_probes?: Record<string, string>;
  slow_plan?: string;
  echo?: string;
  echo_repeat?: string;
  short_max?: number;
}

export type ReplyKind = 'empty' | 'overlay' | 'intent' | 'slow_plan' | 'echo_repeat' | 'echo';

export interface ReplyExplanation {
  text: string;
  kind: ReplyKind;
  id: string | null;
}

export interface ReplyTrace {
  intents?: string[];
  path?: 'fast' | 'slow' | string;
  hotspot_id?: string | null;
  motor_plan?: string[] | null;
}

/** History rows from either host shape. */
export type HistoryRow =
  | { role?: string; text?: string; aaron?: string }
  | Record<string, unknown>;

export const DEFAULT_INTENT_ORDER = ['greeting', 'mic_check', 'ack', 'presence_chatter'];
export const DEFAULT_SPEAK: SpeakParams = { rate: 0.95, pitch: 1.05, lang: 'en-US' };

/** Minimal fallback when the config file is unreachable (never silent). */
export const FALLBACK_OVERLAYS: ConverseOverlaysConfig = {
  version: 0,
  id: 'converse-overlays-fallback',
  empty: "I'm here, Aaron. Whenever you're ready — I'm listening.",
  overlays: [],
  intent_rules: {},
  intent_order: DEFAULT_INTENT_ORDER,
  intents: {},
  echo: 'I heard you: “{short}”. Tell me the next step and I\'ll take it from there.',
  short_max: 120,
};

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function wordHit(low: string, word: string): boolean {
  return new RegExp(`\\b${escapeRegex(word)}\\b`).test(low);
}

export function ruleMatches(low: string, rule: OverlayRule): boolean {
  const anyPhrases = rule.any ?? [];
  if (anyPhrases.length && anyPhrases.some((p) => low.includes(p))) return true;
  const words = rule.words ?? [];
  if (words.length && words.some((w) => wordHit(low, w))) return true;
  const groups = rule.all_groups ?? [];
  if (groups.length && groups.every((g) => g.some((p) => low.includes(p)))) return true;
  return false;
}

export function matchOverlay(low: string, cfg: ConverseOverlaysConfig): OverlayRule | null {
  for (const rule of cfg.overlays ?? []) {
    if (ruleMatches(low, rule)) return rule;
  }
  return null;
}

export function intentOrder(cfg: ConverseOverlaysConfig): string[] {
  const order = cfg.intent_order?.length ? cfg.intent_order : DEFAULT_INTENT_ORDER;
  return order.map(String);
}

const regexCache = new Map<string, RegExp>();

function intentRegex(pattern: string): RegExp {
  let re = regexCache.get(pattern);
  if (!re) {
    re = new RegExp(pattern, 'i');
    regexCache.set(pattern, re);
  }
  return re;
}

/** Config-driven fast intents (mirror of cam_reason._FAST_PATTERNS). */
export function classifyIntents(text: string, cfg: ConverseOverlaysConfig): string[] {
  const rules = cfg.intent_rules ?? {};
  const t = (text || '').trim();
  const hits: string[] = [];
  for (const name of intentOrder(cfg)) {
    const spec = rules[name];
    const pattern = spec?.regex;
    if (!pattern) continue;
    if (intentRegex(pattern).test(t)) hits.push(name);
  }
  return hits;
}

export function lastAaronLine(history: HistoryRow[] | undefined | null): string {
  if (!history) return '';
  for (let i = history.length - 1; i >= 0; i--) {
    const row = history[i] as { role?: unknown; text?: unknown; aaron?: unknown };
    if (!row || typeof row !== 'object') continue;
    if (typeof row.aaron === 'string' && row.aaron) return row.aaron;
    if (row.role === 'aaron' && typeof row.text === 'string' && row.text) return row.text;
  }
  return '';
}

export function shorten(text: string, cfg: ConverseOverlaysConfig): string {
  const limit = Number(cfg.short_max ?? 120);
  // Python slices by code points; use Array.from so astral chars match.
  const chars = Array.from(text);
  return chars.length < limit ? text : `${chars.slice(0, limit - 3).join('')}…`;
}

export function speakParams(cfg: ConverseOverlaysConfig): SpeakParams {
  const out: SpeakParams = { ...DEFAULT_SPEAK };
  const s = cfg.speak ?? {};
  if (typeof s.rate === 'number') out.rate = s.rate;
  if (typeof s.pitch === 'number') out.pitch = s.pitch;
  if (typeof s.lang === 'string' && s.lang) out.lang = s.lang;
  if (typeof s.style === 'string' && s.style) out.style = s.style;
  return out;
}

function fill(template: string, vars: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? vars[k] : m));
}

/** Reply text + which config branch produced it. Mirrors Python explain_reply. */
export function explainReply(
  aaronText: string,
  trace: ReplyTrace,
  history: HistoryRow[] | undefined | null,
  cfg: ConverseOverlaysConfig,
): ReplyExplanation {
  const t = (aaronText || '').trim();
  if (!t) {
    return { text: cfg.empty || "I'm here, Aaron.", kind: 'empty', id: null };
  }
  const low = t.toLowerCase();
  const rule = matchOverlay(low, cfg);
  if (rule) {
    return { text: rule.reply || '', kind: 'overlay', id: String(rule.id || '') };
  }
  let intents = trace.intents?.length ? [...trace.intents] : [];
  if (!intents.length) intents = classifyIntents(t, cfg);
  const intentReplies = cfg.intents ?? {};
  for (const key of intentOrder(cfg)) {
    if (intents.includes(key) && intentReplies[key]) {
      return { text: intentReplies[key], kind: 'intent', id: key };
    }
  }
  if ((trace.path || '') === 'slow') {
    const hotspot = trace.hotspot_id || 'capability';
    const motors = (trace.motor_plan?.length ? trace.motor_plan : ['motor.mesh']).join(', ');
    const text = fill(cfg.slow_plan || 'I have a plan.', { hotspot, motors });
    return { text, kind: 'slow_plan', id: String(hotspot) };
  }
  const short = shorten(t, cfg);
  const previous = lastAaronLine(history).trim().toLowerCase();
  if (previous && previous === low && cfg.echo_repeat) {
    return { text: fill(cfg.echo_repeat, { short }), kind: 'echo_repeat', id: null };
  }
  return {
    text: fill(cfg.echo || 'I heard you: “{short}”.', { short }),
    kind: 'echo',
    id: null,
  };
}

export function overlayProbes(
  cfg: ConverseOverlaysConfig,
): Array<{ id: string; probe: string; must: string }> {
  const rows: Array<{ id: string; probe: string; must: string }> = [];
  for (const rule of cfg.overlays ?? []) {
    const must = rule.must_contain?.[0] ?? ' ';
    for (const probe of rule.probes ?? []) {
      rows.push({ id: String(rule.id || ''), probe: String(probe), must: String(must) });
    }
  }
  return rows;
}

export interface OverlayCheck {
  ok: boolean;
  errors: string[];
  overlay_count: number;
  intent_count: number;
  version?: number;
}

/** Static contract check — TS mirror of Python check_overlays (minus cam_reason drift). */
export function checkOverlays(cfg: ConverseOverlaysConfig): OverlayCheck {
  const errors: string[] = [];
  const ids: string[] = [];
  for (const rule of cfg.overlays ?? []) {
    const rid = rule.id || '';
    if (!rid) {
      errors.push('overlay_missing_id');
      continue;
    }
    if (ids.includes(rid)) errors.push(`duplicate_overlay:${rid}`);
    ids.push(rid);
    if (!(rule.reply || '').trim()) errors.push(`empty_reply:${rid}`);
    if (!(rule.any?.length || rule.all_groups?.length || rule.words?.length)) {
      errors.push(`no_matchers:${rid}`);
    }
    const must = rule.must_contain?.[0];
    if (must && !(rule.reply || '').includes(must)) errors.push(`must_contain_missing:${rid}`);
    if (!rule.probes?.length) errors.push(`no_probes:${rid}`);
    for (const probe of rule.probes ?? []) {
      const hit = matchOverlay(probe.toLowerCase(), cfg);
      if (!hit || hit.id !== rid) errors.push(`probe_mismatch:${rid}:${probe}`);
    }
  }
  if (!(cfg.empty || '').trim()) errors.push('empty_line_missing');
  for (const key of ['echo', 'echo_repeat'] as const) {
    if (!String(cfg[key] ?? '').includes('{short}')) errors.push(`template_missing_short:${key}`);
  }
  if (!String(cfg.slow_plan ?? '').includes('{hotspot}')) {
    errors.push('template_missing_hotspot:slow_plan');
  }
  const order = intentOrder(cfg);
  const rules = cfg.intent_rules ?? {};
  const probes = cfg.intent_probes ?? {};
  for (const key of order) {
    if (!cfg.intents?.[key]) errors.push(`intent_missing:${key}`);
    const pattern = rules[key]?.regex;
    if (!pattern) {
      errors.push(`intent_rule_missing:${key}`);
      continue;
    }
    try {
      intentRegex(pattern);
    } catch {
      errors.push(`intent_rule_invalid:${key}`);
      continue;
    }
    const probe = probes[key];
    if (!probe) errors.push(`intent_probe_missing:${key}`);
    else if (!classifyIntents(probe, cfg).includes(key)) {
      errors.push(`intent_probe_mismatch:${key}:${probe}`);
    }
  }
  const speak = cfg.speak ?? {};
  if (typeof speak.rate !== 'number') errors.push('speak_missing:rate');
  if (typeof speak.pitch !== 'number') errors.push('speak_missing:pitch');
  if (!speak.lang) errors.push('speak_missing:lang');
  return {
    ok: errors.length === 0,
    errors,
    overlay_count: ids.length,
    intent_count: order.length,
    version: cfg.version,
  };
}
