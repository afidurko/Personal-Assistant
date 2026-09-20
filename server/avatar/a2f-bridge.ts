/**
 * NVIDIA Audio2Face bridge — talks to the LLMAvatarTalk gRPC client
 * (integrations/llmavatartalk) when a desk A2F / A2F-3D NIM is live.
 * Browser Cam avatar always uses the same ARKit weight contract.
 */
import { spawn } from 'node:child_process';
import { createConnection } from 'node:net';
import path from 'node:path';

export interface A2FStudioStatus {
  engine: 'audio2face';
  portrait: string;
  studio: string;
  instance: string;
  live: boolean;
  mode: 'desk-omniverse' | 'nim' | 'browser-arkit';
  notes: string;
}

function studioHost(): { host: string; port: number; url: string } {
  const raw = process.env.A2F_URL || process.env.A2F_NIM_URL || '127.0.0.1:50051';
  const cleaned = raw.replace(/^https?:\/\//, '');
  const [host, portStr] = cleaned.split(':');
  return { host: host || '127.0.0.1', port: Number(portStr || 50051), url: `${host || '127.0.0.1'}:${portStr || 50051}` };
}

function probePort(host: string, port: number, ms = 350): Promise<boolean> {
  return new Promise((resolve) => {
    const sock = createConnection({ host, port });
    const done = (ok: boolean) => {
      sock.removeAllListeners();
      sock.destroy();
      resolve(ok);
    };
    const t = setTimeout(() => done(false), ms);
    sock.once('connect', () => {
      clearTimeout(t);
      done(true);
    });
    sock.once('error', () => {
      clearTimeout(t);
      done(false);
    });
  });
}

export async function a2fStatus(): Promise<A2FStudioStatus> {
  const { host, port, url } = studioHost();
  const live = await probePort(host, port);
  return {
    engine: 'audio2face',
    portrait: 'identity/persona/cam-face.jpg',
    studio: url,
    instance: process.env.A2F_INSTANCE || '/World/audio2face/PlayerStreaming',
    live,
    mode: live ? (port === 52000 ? 'nim' : 'desk-omniverse') : 'browser-arkit',
    notes: live
      ? 'Desk Audio2Face is reachable — PushAudio uses integrations/llmavatartalk'
      : 'Studio offline — Cam photo mesh is driven by the A2F ARKit contract in-browser',
  };
}

/** Push PCM/WAV bytes to desk Audio2Face via the NVIDIA submodule helper. */
export function pushAudioToA2F(wavPath: string): Promise<{ ok: boolean; detail: string }> {
  const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..');
  const script = path.join(root, 'scripts/a2f-push.py');
  return new Promise((resolve) => {
    const child = spawn('python3', [script, wavPath], {
      cwd: root,
      env: process.env,
    });
    let out = '';
    child.stdout.on('data', (d) => {
      out += String(d);
    });
    child.stderr.on('data', (d) => {
      out += String(d);
    });
    child.on('error', (e) => resolve({ ok: false, detail: e.message }));
    child.on('close', (code) => {
      resolve({ ok: code === 0, detail: out.trim() || `exit ${code}` });
    });
  });
}
