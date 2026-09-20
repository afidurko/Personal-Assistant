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
  credential_source?: string | null;
  live_enabled: boolean;
  auto_on_turn: false;
  portrait: string;
  portrait_exists: boolean;
  tts?: { id?: string | null; ready?: boolean };
  last_clip?: string | null;
  public_path?: string | null;
  last_error?: string | null;
  last_status?: string | null;
  ready_to_render: boolean;
  notes: string;
}

function envOn(name: string): boolean {
  const v = (process.env[name] || '').trim().toLowerCase();
  return v === '1' || v === 'true' || v === 'yes' || v === 'on';
}

function credentialsPresent(): { present: boolean; source: string | null } {
  const combined = ['HIGGSFIELD_CREDENTIALS', 'HF_CREDENTIALS', 'HF_KEY'];
  for (const name of combined) {
    const raw = (process.env[name] || '').trim();
    if (raw.includes(':')) return { present: true, source: name };
  }
  const pairs: Array<[string, string]> = [
    ['HIGGSFIELD_API_KEY_ID', 'HIGGSFIELD_API_KEY_SECRET'],
    ['HF_API_KEY_ID', 'HF_API_KEY_SECRET'],
    ['HF_API_KEY', 'HF_SECRET'],
  ];
  for (const [id, secret] of pairs) {
    if (process.env[id] && process.env[secret]) return { present: true, source: `${id}+${secret}` };
  }
  return { present: false, source: null };
}

export async function higgsfieldStatus(): Promise<HiggsfieldStatus> {
  const last = existsSync(LAST)
    ? (JSON.parse(await readFile(LAST, 'utf8')) as {
        public_path?: string;
        clip_url?: string;
        local_path?: string;
        error?: string;
        status?: string;
      })
    : null;
  const creds = credentialsPresent();
  const live = envOn('HIGGSFIELD_LIVE');
  const portrait = 'identity/persona/cam-face.jpg';
  return {
    engine: 'higgsfield_speak',
    configured: existsSync(path.join(ROOT, 'config/integrations/higgsfield.json')),
    credentials_present: creds.present,
    credential_source: creds.source,
    live_enabled: live,
    auto_on_turn: false,
    portrait,
    portrait_exists: existsSync(path.join(ROOT, portrait)),
    last_clip: last?.clip_url || last?.local_path || null,
    public_path: last?.public_path || null,
    last_error: last?.error || null,
    last_status: last?.status || null,
    ready_to_render: creds.present && live,
    notes:
      'Local portrait + WAV upload via /files/generate-upload-url. /api/turn never uploads Cam’s face.',
  };
}

export function underRoot(rel: string | undefined): string | null {
  if (!rel) return null;
  const abs = path.resolve(ROOT, rel);
  if (abs !== ROOT && !abs.startsWith(ROOT + path.sep)) return null;
  return abs;
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
