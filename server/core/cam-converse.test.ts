import { describe, expect, it } from 'vitest';
import { CamConverse, OVERLAYS_CONFIG_REL, OverlaysStore, camReply } from './cam-converse.js';
import path from 'node:path';
import { mkdirSync, mkdtempSync, readFileSync, utimesSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..');

describe('camReply (shared persona config)', () => {
  it('greets Aaron warmly', () => {
    expect(camReply('hi cam')).toMatch(/Aaron/i);
  });

  it('mentions Aaron-only listening when asked about mic', () => {
    expect(camReply('can you hear me')).toMatch(/voice only|your voice/i);
  });

  it('acknowledges brain/cortex prompts', () => {
    expect(camReply('show me the 3d brain')).toMatch(/cortex|brain|fiber/i);
  });

  it('confirms Aaron-only mode', () => {
    expect(camReply('only my voice please ignore other people')).toMatch(/Aaron-only|ignore/i);
  });

  it('matches the Python overlay line for camera (one voice)', () => {
    const cfg = JSON.parse(readFileSync(path.join(ROOT, OVERLAYS_CONFIG_REL), 'utf8')) as {
      overlays: Array<{ id: string; reply: string }>;
    };
    const camera = cfg.overlays.find((o) => o.id === 'camera');
    expect(camReply('can you see me')).toBe(camera?.reply);
  });
});

describe('OverlaysStore', () => {
  it('hot-reloads when the config mtime changes and falls back when missing', () => {
    const dir = mkdtempSync(path.join(tmpdir(), 'cam-overlays-'));
    const store = new OverlaysStore(dir);
    expect(store.status().fallback).toBe(true);
    expect(store.status().ok).toBe(false);

    mkdirSync(path.join(dir, 'config/persona'), { recursive: true });
    const file = path.join(dir, OVERLAYS_CONFIG_REL);
    const base = JSON.parse(readFileSync(path.join(ROOT, OVERLAYS_CONFIG_REL), 'utf8')) as Record<
      string,
      unknown
    >;
    writeFileSync(file, JSON.stringify({ ...base, empty: 'v1 line' }), 'utf8');
    utimesSync(file, new Date(1_700_000_000_000), new Date(1_700_000_000_000));
    expect(store.load().empty).toBe('v1 line');
    expect(store.status().fallback).toBe(false);
    expect(store.status().ok).toBe(true);

    writeFileSync(file, JSON.stringify({ ...base, empty: 'v2 line' }), 'utf8');
    utimesSync(file, new Date(1_700_000_100_000), new Date(1_700_000_100_000));
    expect(store.load().empty).toBe('v2 line');
  });
});

describe('CamConverse voice gate', () => {
  it('rejects low-score mic turns', async () => {
    const c = new CamConverse(ROOT);
    const reply = await c.turn({
      text: 'hey from someone else',
      source: 'mic',
      aaron_voice_score: 0.4,
      enrolled: true,
    });
    expect(reply.rejected).toBe(true);
    expect(reply.cam).toMatch(/voice|filtered|ignored|match/i);
    expect(reply.overlay).toBeUndefined();
  });

  it('accepts typed turns and reports which config branch spoke', async () => {
    const c = new CamConverse(ROOT);
    const reply = await c.turn({ text: 'hello cam', source: 'text' });
    expect(reply.rejected).toBeFalsy();
    expect(reply.cam).toMatch(/Aaron/i);
    expect(reply.overlay).toMatchObject({ kind: 'intent', id: 'greeting' });
    expect(reply.overlay?.intents).toContain('greeting');
    expect(reply.speak).toMatchObject({ rate: 0.95, pitch: 1.05, lang: 'en-US' });
  });

  it('composes slow-path replies from the bridge route via beforeReply', async () => {
    const c = new CamConverse(ROOT);
    let seen = '';
    const reply = await c.turn({ text: 'implement a small refactor', source: 'text' }, 'text', {
      beforeReply: async (text) => {
        seen = text;
        return { path: 'slow', hotspot_id: 'hotspot.coding', motor_plan: ['motor.cline'] };
      },
    });
    expect(seen).toBe('implement a small refactor');
    expect(reply.overlay).toMatchObject({ kind: 'slow_plan', id: 'hotspot.coding' });
    expect(reply.cam).toContain('motor.cline');
  });

  it('detects a repeated Aaron line across turns', async () => {
    const c = new CamConverse(ROOT);
    const first = await c.turn({ text: 'zzz unique line', source: 'text' });
    expect(first.overlay?.kind).toBe('echo');
    const second = await c.turn({ text: 'zzz unique line', source: 'text' });
    expect(second.overlay?.kind).toBe('echo_repeat');
    expect(second.history.filter((h) => h.role === 'cam').at(-1)?.overlay?.kind).toBe(
      'echo_repeat',
    );
  });

  it('preview never mutates history', () => {
    const c = new CamConverse(ROOT);
    const out = c.preview('who are you');
    expect(out.kind).toBe('overlay');
    expect(out.id).toBe('identity');
    expect(c.getHistory()).toEqual([]);
  });
});
