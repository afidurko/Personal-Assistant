import { mkdtemp, mkdir, writeFile, rm, cp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { afterEach, describe, expect, it } from 'vitest';
import { RuntimeStore } from './runtime-store.js';
import { SystemBridge } from './system-bridge.js';
import { ConnectomeKernel } from './connectome-kernel.js';
import { applyTrajectoryPolicies, loadTrajectoryPolicies } from './trajectory-policies.js';

const dirs: string[] = [];
const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

afterEach(async () => {
  for (const d of dirs.splice(0)) {
    await rm(d, { recursive: true, force: true });
  }
});

async function fixtureWithConnectome(): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), 'cam-org-'));
  dirs.push(root);
  await mkdir(path.join(root, 'config/system'), { recursive: true });
  await mkdir(path.join(root, 'config/persona'), { recursive: true });
  await mkdir(path.join(root, 'server/core'), { recursive: true });
  await mkdir(path.join(root, 'vault/10-Mesh-Distillates'), { recursive: true });
  await mkdir(path.join(root, 'docs'), { recursive: true });
  // Copy real connectome so kernel matches production
  await cp(path.join(REPO, 'config/connectome'), path.join(root, 'config/connectome'), {
    recursive: true,
  });
  await writeFile(
    path.join(root, 'config/persona/voice.json'),
    JSON.stringify({
      availability: {
        always_on: true,
        quiet_hours: { start: '23:00', end: '07:00' },
        timezone: 'UTC',
      },
    }),
    'utf8',
  );
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
          paths: ['config/connectome'],
          slo: { max_latency_ms: 500 },
        },
        {
          id: 'piece.system_bridge',
          title: 'System bridge',
          layer: 'glue',
          paths: ['server/core/system-bridge.ts'],
        },
      ],
      blockers: ['test-blocker'],
    }),
    'utf8',
  );
  await writeFile(path.join(root, 'server/core/system-bridge.ts'), '// stub\n', 'utf8');
  await writeFile(path.join(root, 'docs/PERSONA.md'), '# Cam\n', 'utf8');
  return root;
}

describe('ConnectomeKernel', () => {
  it('routes chat in-process with dual-stream and map plan', async () => {
    const root = await fixtureWithConnectome();
    const kernel = new ConnectomeKernel(root);
    const route = await kernel.route({
      sense: 'sense.chat.aaron',
      goal: 'hi cam',
      source: 'text',
      actHint: 'speak',
    });
    expect(route.kernel).toBe('in_process');
    expect(route.accepted).toBe(true);
    expect(route.motor_plan.length).toBeGreaterThan(0);
    expect(route.dual_stream.winner).toBe('dorsal');
    expect(route.map_plan.length).toBeGreaterThan(0);
  });

  it('rejects mic without Aaron voice score', async () => {
    const root = await fixtureWithConnectome();
    const kernel = new ConnectomeKernel(root);
    const route = await kernel.route({
      sense: 'sense.ios.mic',
      goal: 'hello',
      source: 'mic',
      aaronVoiceScore: 0.2,
    });
    expect(route.accepted).toBe(false);
    expect(route.identity?.passed).toBe(false);
    expect(route.motor_plan).toEqual([]);
  });

  it('strips enhance without Aaron gate via trajectory physics', async () => {
    const root = await fixtureWithConnectome();
    await loadTrajectoryPolicies(root);
    const { plan, violations } = applyTrajectoryPolicies(
      ['motor.web_fetch', 'motor.enhance'],
      { 'switch.cam_enhance': 'hold', 'switch.kill': 'armed_allow_motor' },
    );
    expect(plan).not.toContain('motor.enhance');
    expect(violations.some((v) => v.stripped?.includes('motor.enhance'))).toBe(true);
  });
});

describe('SystemBridge organism bus', () => {
  it('onTurn routes, lights tracts, and executes safe motors', async () => {
    const root = await fixtureWithConnectome();
    const runtime = new RuntimeStore(root);
    await runtime.ensure();
    const bridge = new SystemBridge(root, runtime);
    const result = await bridge.onTurn('Hi Cam light the cortex', 'text');
    expect(result.route.accepted).toBe(true);
    expect(result.route.kernel).toBe('in_process');
    expect(result.activities.length).toBeGreaterThanOrEqual(3);
    expect(result.execution.results.length).toBeGreaterThan(0);
    expect(result.memory.tier).toBe('primary');
    const live = await runtime.readJson<{ firing?: unknown[] }>('live-activity.json', {});
    expect((live.firing?.length ?? 0) >= 3).toBe(true);
  });

  it('reports piece status and blockers', async () => {
    const root = await fixtureWithConnectome();
    const runtime = new RuntimeStore(root);
    await runtime.ensure();
    const bridge = new SystemBridge(root, runtime);
    const status = await bridge.status({ sessionId: 't' });
    expect(status.assistant).toBe('Cam');
    expect(status.blockers?.length).toBeGreaterThan(0);
    expect(status.pieces.some((p) => p.id === 'piece.connectome')).toBe(true);
  });
});
