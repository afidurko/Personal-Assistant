import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it } from 'vitest';
import { ConnectomeKernel } from './connectome-kernel.js';
import { MotorExecutor } from './motor-executor.js';
import { RuntimeStore } from './runtime-store.js';
import {
  evaluateSentinel,
  idempotencyKey,
  IntentJournal,
  loadSentinelPolicy,
  redact,
  type SentinelPolicy,
} from './sentinel.js';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const dirs: string[] = [];

afterEach(async () => {
  for (const d of dirs.splice(0)) await rm(d, { recursive: true, force: true });
});

async function fixture(): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), 'cam-sentinel-'));
  dirs.push(root);
  await cp(path.join(REPO, 'config/connectome'), path.join(root, 'config/connectome'), {
    recursive: true,
  });
  await mkdir(path.join(root, 'config/persona'), { recursive: true });
  await writeFile(
    path.join(root, 'config/persona/voice.json'),
    JSON.stringify({ availability: { always_on: true, quiet_hours: null, timezone: 'UTC' } }),
    'utf8',
  );
  return root;
}

async function policy(): Promise<SentinelPolicy> {
  return loadSentinelPolicy(REPO);
}

describe('Sentinel decisions (Muse: propose → allow/ask/deny)', () => {
  it('allows read + write_local classes by policy, no grant needed', async () => {
    const v = evaluateSentinel(['motor.vault', 'motor.mesh', 'motor.docs'], { sense: 'sense.chat.text' }, await policy());
    expect(v.allowed).toEqual(['motor.vault', 'motor.mesh', 'motor.docs']);
    expect(v.pending).toEqual([]);
    expect(v.decisions['motor.vault']?.authorizer).toBe('policy');
  });

  it('clean egress rides the standing switch.outbound grant', async () => {
    const v = evaluateSentinel(
      ['motor.text'],
      { sense: 'sense.chat.text', switchState: { 'switch.outbound': 'act' } },
      await policy(),
    );
    expect(v.allowed).toEqual(['motor.text']);
    expect(v.decisions['motor.text']?.authorizer).toBe('grant:perpetual:Aaron');
  });

  it('tainted egress (email → text) loses auto-allow and asks Aaron', async () => {
    const v = evaluateSentinel(
      ['motor.text', 'motor.vault'],
      { sense: 'sense.email.thread', switchState: { 'switch.outbound': 'act' } },
      await policy(),
    );
    expect(v.taint.tainted).toBe(true);
    expect(v.pending).toEqual(['motor.text']);
    expect(v.allowed).toEqual(['motor.vault']);
    expect(v.decisions['motor.text']?.grant_options).not.toContain('perpetual');
  });

  it('a tainted-covering Aaron grant re-allows tainted egress; a clean one does not', async () => {
    const pol = await policy();
    const opts = { sense: 'sense.email.thread', switchState: { 'switch.outbound': 'act' } };
    const clean = evaluateSentinel(['motor.text'], { ...opts, grants: [{ motor: 'motor.text', scope: 'perpetual', granted_by: 'Aaron' }] }, pol);
    expect(clean.pending).toEqual(['motor.text']);
    const covering = evaluateSentinel(
      ['motor.text'],
      { ...opts, grants: [{ id: 'g1', motor: 'motor.text', scope: 'once', granted_by: 'Aaron', covers_tainted: true }] },
      pol,
    );
    expect(covering.allowed).toEqual(['motor.text']);
    expect(covering.decisions['motor.text']?.grant_id).toBe('g1');
  });

  it('scoped grants: session must match, until must be in the future, task must match', async () => {
    const pol = await policy();
    const base = { sense: 'sense.chat.text', switchState: { 'switch.cam_enhance': 'hold' } };
    const session = (sid: string | null) =>
      evaluateSentinel(['motor.enhance'], { ...base, sessionId: sid, grants: [{ motor: 'motor.enhance', scope: 'session', session_id: 'abc', granted_by: 'Aaron' }] }, pol);
    expect(session('abc').allowed).toEqual(['motor.enhance']);
    expect(session('zzz').pending).toEqual(['motor.enhance']);

    const until = (iso: string) =>
      evaluateSentinel(['motor.enhance'], { ...base, now: Date.parse('2026-09-21T12:00:00Z'), grants: [{ motor: 'motor.enhance', scope: 'until', until: iso, granted_by: 'Aaron' }] }, pol);
    expect(until('2026-09-22T00:00:00Z').allowed).toEqual(['motor.enhance']);
    expect(until('2026-09-20T00:00:00Z').pending).toEqual(['motor.enhance']);

    const task = (t: string) =>
      evaluateSentinel(['motor.enhance'], { ...base, task: t, grants: [{ motor: 'motor.enhance', scope: 'task', task: 'batch-7', granted_by: 'Aaron' }] }, pol);
    expect(task('batch-7').allowed).toEqual(['motor.enhance']);
    expect(task('batch-8').pending).toEqual(['motor.enhance']);
  });

  it('kill denies everything; unknown motors fail closed to ask', async () => {
    const pol = await policy();
    const kill = evaluateSentinel(['motor.vault', 'motor.text'], { switchState: { 'switch.kill': 'act' } }, pol);
    expect(kill.denied).toEqual(['motor.vault', 'motor.text']);
    const unknown = evaluateSentinel(['motor.mystery'], {}, pol);
    expect(unknown.pending).toEqual(['motor.mystery']);
    expect(unknown.decisions['motor.mystery']?.grant_options).toEqual(['once']);
  });
});

describe('Intent journal (append-only, redacted, shared key space with Python)', () => {
  it('idempotency key matches scripts/cam_journal.py sha256 form', () => {
    // python3 -c "import hashlib; print(hashlib.sha256(b'motor.text|a|b').hexdigest()[:12])"
    expect(idempotencyKey('motor.text', 'a', 'b')).toBe('motor.text:bfc92021d785');
    expect(idempotencyKey('motor.text', 'a', 'c')).not.toBe(idempotencyKey('motor.text', 'a', 'b'));
  });

  it('redacts bearer tokens, api keys and JWTs before they reach disk', () => {
    const out = redact('Authorization: Bearer abcdefghijklmnop api_key=supersecret123 eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJlX3g');
    expect(out).not.toContain('abcdefghijklmnop');
    expect(out).not.toContain('supersecret123');
    expect(out).not.toContain('eyJhbGci');
    expect(out).toContain('[REDACTED]');
  });

  it('sequence is monotonic per day and payloads land redacted', async () => {
    const root = await fixture();
    const j = new IntentJournal(root);
    const a = await j.append('proposed', { motor_plan: ['motor.vault'], token: 'shhh-very-secret' });
    const b = await j.append('side_effect_intent', { motor: 'motor.vault', idempotency_key: 'k' });
    expect(b.sequence).toBe(a.sequence + 1);
    const day = new Date().toISOString().slice(0, 10);
    const lines = (await readFile(path.join(root, 'data/runtime/journal', `${day}.jsonl`), 'utf8')).trim().split('\n');
    expect(lines).toHaveLength(2);
    expect(lines[0]).toContain('[REDACTED]');
    expect(lines[0]).not.toContain('shhh-very-secret');
  });
});

describe('Kernel + executor honour Sentinel', () => {
  it('email → outbound is held as pending_approval and journaled, safe motors still run', async () => {
    const root = await fixture();
    const kernel = new ConnectomeKernel(root);
    const route = await kernel.route({ sense: 'sense.email.thread', goal: 'reply to the recruiter' });
    expect(route.accepted).toBe(true);
    expect(route.sentinel.taint.tainted).toBe(true);
    const held = route.motor_pending;
    for (const m of held) expect(route.motor_plan).not.toContain(m);
    if (held.length) {
      expect(route.sentinel.decisions[held[0]!]?.decision).toBe('ask');
    }

    const runtime = new RuntimeStore(root);
    await runtime.ensure();
    const exec = new MotorExecutor(root, runtime);
    const report = await exec.execute(route);
    const pendingResults = report.results.filter((r) => r.status === 'pending_approval');
    expect(pendingResults.map((r) => r.motor)).toEqual(held);

    const day = new Date().toISOString().slice(0, 10);
    const rows = (await readFile(path.join(root, 'data/runtime/journal', `${day}.jsonl`), 'utf8'))
      .trim()
      .split('\n')
      .map((l) => JSON.parse(l) as { kind: string; sequence: number; payload: Record<string, unknown> });
    expect(rows[0]?.kind).toBe('proposed');
    expect(rows.filter((r) => r.kind === 'approval.requested')).toHaveLength(held.length);
    const intents = rows.filter((r) => r.kind === 'side_effect_intent');
    const terminals = rows.filter((r) => r.kind === 'effect.terminal');
    expect(terminals.length).toBe(intents.length);
    for (let i = 1; i < rows.length; i++) expect(rows[i]!.sequence).toBe(rows[i - 1]!.sequence + 1);
  });

  it('kill switch silences motor_plan and motor_pending alike', async () => {
    const root = await fixture();
    const kernel = new ConnectomeKernel(root);
    const route = await kernel.route({ sense: 'sense.email.thread', goal: 'x', kill: true });
    expect(route.motor_plan).toEqual([]);
    expect(route.motor_pending).toEqual([]);
  });
});
