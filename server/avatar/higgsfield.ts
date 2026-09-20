/**
 * Higgsfield Speak bridge — status + gated clip jobs.
 * Never auto-fires from /api/turn. Live jobs require keys + HIGGSFIELD_LIVE=1.
 */
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const LAST = path.join(ROOT, 'data/higgsfield/last.json');
const SCRIPT = path.join(ROOT, 'scripts/higgsfield.py');

export interface HiggsfieldStatus {
  engine: 'higgsfield_speak';
  configured: boolean;
  credentials_present: boolean;
  live_enabled: boolean;
  auto_on_turn: false;
  portrait: string;
  last_clip?: string | null;
  public_path?: string | null;
  notes: string;
}

function envOn(name: string): boolean {
  const v = (process.env[name] || '').trim().toLowerCase();
  return v === '1' || v === 'true' || v === 'yes' || v === 'on';
}

export async function higgsfieldStatus(): Promise<HiggsfieldStatus> {
  const last = existsSync(LAST)
    ? (JSON.parse(await readFile(LAST, 'utf8')) as { public_path?: string; clip_url?: string; local_path?: string })
    : null;
  return {
    engine: 'higgsfield_speak',
    configured: existsSync(path.join(ROOT, 'config/integrations/higgsfield.json')),
    credentials_present: Boolean(
      process.env.HIGGSFIELD_API_KEY_ID && process.env.HIGGSFIELD_API_KEY_SECRET,
    ),
    live_enabled: envOn('HIGGSFIELD_LIVE'),
    auto_on_turn: false,
    portrait: 'identity/persona/cam-face.jpg',
    last_clip: last?.clip_url || last?.local_path || null,
    public_path: last?.public_path || null,
    notes: 'Gated Speak clips. /api/turn never uploads Cam’s face.',
  };
}

export function runHiggsfield(args: string[]): Promise<{ ok: boolean; report: Record<string, unknown> }> {
  return new Promise((resolve) => {
    const child = spawn('python3', [SCRIPT, ...args], { cwd: ROOT, env: process.env });
    let out = '';
    child.stdout.on('data', (d) => {
      out += String(d);
    });
    child.stderr.on('data', (d) => {
      out += String(d);
    });
    child.on('error', (e) => resolve({ ok: false, report: { error: e.message } }));
    child.on('close', (code) => {
      try {
        const report = JSON.parse(out) as Record<string, unknown>;
        resolve({ ok: code === 0 && Boolean(report.ok), report });
      } catch {
        resolve({ ok: false, report: { error: out.trim() || `exit ${code}` } });
      }
    });
  });
}
