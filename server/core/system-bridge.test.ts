import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { RuntimeStore } from './runtime-store.js';
import { SystemBridge } from './system-bridge.js';

const dirs: string[] = [];

afterEach(async () => {
  for (const d of dirs.splice(0)) {
    await rm(d, { recursive: true, force: true });
  }
});

async function fixtureRoot(): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), 'cam-sys-'));
  dirs.push(root);
  await mkdir(path.join(root, 'config/system'), { recursive: true });
  await mkdir(path.join(root, 'server/core'), { recursive: true });
  await mkdir(path.join(root, 'vault/10-Mesh-Distillates'), { recursive: true });
  await writeFile(
    path.join(root, 'config/system/pieces.json'),
    JSON.stringify({
      assistant: 'Cam',
      bus: { mesh_api: 'http://127.0.0.1:8787' },
      pieces: [
        {
          id: 'piece.connectome',
          title: 'Connectome',
          layer: 'brain',
          paths: ['config/system/pieces.json'],
        },
        {
          id: 'piece.system_bridge',
          title: 'System bridge',
          layer: 'glue',
          paths: ['server/core/system-bridge.ts'],
        },
        {
          id: 'piece.missing',
          title: 'Missing',
          layer: 'ops',
          paths: ['does-not-exist/foo'],
        },
      ],
    }),
    'utf8',
  );
  await writeFile(path.join(root, 'server/core/system-bridge.ts'), '// stub\n', 'utf8');
  return root;
}

describe('SystemBridge', () => {
  it('reports piece status from inventory', async () => {
    const root = await fixtureRoot();
    const runtime = new RuntimeStore(root);
    await runtime.ensure();
    const bridge = new SystemBridge(root, runtime);
    const status = await bridge.status({ sessionId: 'test' });
    expect(status.assistant).toBe('Cam');
    expect(status.pieces.length).toBeGreaterThanOrEqual(3);
    const ok = status.pieces.find((p) => p.id === 'piece.connectome');
    expect(ok?.status).toBe('healthy');
    const bad = status.pieces.find((p) => p.id === 'piece.missing');
    expect(bad?.status).toBe('critical');
    expect(status.overall).toBe('critical');
    expect(status.ok).toBe(false);
  });

  it('emits converse activity into runtime live-activity', async () => {
    const root = await fixtureRoot();
    const runtime = new RuntimeStore(root);
    await runtime.ensure();
    const bridge = new SystemBridge(root, runtime);
    const rows = await bridge.emitConverseTurn('text');
    expect(rows.length).toBeGreaterThanOrEqual(3);
    const live = await runtime.readJson<{ firing_count?: number; firing?: unknown[] }>(
      'live-activity.json',
      {},
    );
    expect((live.firing_count ?? 0) >= 3 || (live.firing?.length ?? 0) >= 3).toBe(true);
  });

  it('emits mic and camera spikes', async () => {
    const root = await fixtureRoot();
    const runtime = new RuntimeStore(root);
    await runtime.ensure();
    const bridge = new SystemBridge(root, runtime);
    const mic = await bridge.emitMicSpike();
    expect(mic[0]?.neuron).toBe('neuron.asr');
    const cam = await bridge.emitCameraSpike();
    expect(cam[0]?.neuron).toBe('neuron.vision');
  });
});
