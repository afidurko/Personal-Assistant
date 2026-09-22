import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import {
  FALLBACK_OVERLAYS,
  checkOverlays,
  classifyIntents,
  explainReply,
  lastAaronLine,
  matchOverlay,
  overlayProbes,
  shorten,
  speakParams,
  type ConverseOverlaysConfig,
} from './converseOverlays.js';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const cfg = JSON.parse(
  readFileSync(path.join(ROOT, 'config/persona/converse-overlays.json'), 'utf8'),
) as ConverseOverlaysConfig;

describe('converse overlays config contract', () => {
  it('passes the static check', () => {
    const report = checkOverlays(cfg);
    expect(report.errors).toEqual([]);
    expect(report.ok).toBe(true);
    expect(report.overlay_count).toBeGreaterThanOrEqual(6);
  });

  it('every probe lands on its own overlay with must_contain in the reply', () => {
    for (const { id, probe, must } of overlayProbes(cfg)) {
      const hit = matchOverlay(probe.toLowerCase(), cfg);
      expect(hit?.id, probe).toBe(id);
      const out = explainReply(probe, { intents: [], path: 'fast' }, null, cfg);
      expect(out.kind).toBe('overlay');
      expect(out.id).toBe(id);
      expect(out.text).toContain(must);
    }
  });

  it('intent probes classify from config regexes and reply from intents', () => {
    for (const [intent, probe] of Object.entries(cfg.intent_probes ?? {})) {
      expect(classifyIntents(probe, cfg)).toContain(intent);
      const out = explainReply(probe, { intents: [], path: 'fast' }, null, cfg);
      // an overlay may legitimately win first (e.g. "thanks" → thanks overlay)
      if (out.kind === 'intent') {
        expect(out.id).toBe(intent);
        expect(out.text).toBe(cfg.intents?.[intent]);
      }
    }
  });

  it('never wires Higgsfield Speak clips into presence phrases', () => {
    const blob = JSON.stringify(cfg);
    expect(blob).not.toMatch(/cam-face-higgsfield|Speak clip/);
  });
});

describe('explainReply branches', () => {
  it('empty text → empty line', () => {
    const out = explainReply('   ', {}, null, cfg);
    expect(out.kind).toBe('empty');
    expect(out.text).toBe(cfg.empty);
  });

  it('slow path names hotspot + motors', () => {
    const out = explainReply(
      'implement a small refactor',
      { intents: ['general'], path: 'slow', hotspot_id: 'hotspot.coding', motor_plan: ['motor.cline'] },
      null,
      cfg,
    );
    expect(out.kind).toBe('slow_plan');
    expect(out.text).toContain('hotspot.coding');
    expect(out.text).toContain('motor.cline');
  });

  it('echo vs echo_repeat uses the previous Aaron line from either history shape', () => {
    const first = explainReply('ping', { intents: ['general'] }, [], cfg);
    expect(first.kind).toBe('echo');
    expect(first.text).toContain('ping');
    const tsShape = explainReply('ping', { intents: ['general'] }, [{ role: 'aaron', text: 'Ping' }], cfg);
    expect(tsShape.kind).toBe('echo_repeat');
    const pyShape = explainReply('ping', { intents: ['general'] }, [{ aaron: 'ping', cam: 'x' }], cfg);
    expect(pyShape.kind).toBe('echo_repeat');
    expect(pyShape.text).toBe(tsShape.text);
  });

  it('shortens long echo by code points', () => {
    const long = 'x'.repeat(200);
    expect(shorten(long, cfg).length).toBe((cfg.short_max ?? 120) - 3 + 1);
    expect(explainReply(long, { intents: ['general'] }, null, cfg).text).toContain('…');
  });

  it('lastAaronLine ignores cam/system rows', () => {
    expect(
      lastAaronLine([
        { role: 'aaron', text: 'first' },
        { role: 'cam', text: 'reply' },
        { role: 'system', text: 'noise' },
      ]),
    ).toBe('first');
    expect(lastAaronLine([])).toBe('');
  });

  it('speak params come from config with defaults', () => {
    expect(speakParams(cfg)).toMatchObject({ rate: 0.95, pitch: 1.05, lang: 'en-US' });
    expect(speakParams(FALLBACK_OVERLAYS)).toEqual({ rate: 0.95, pitch: 1.05, lang: 'en-US' });
  });

  it('fallback config still answers (never silent)', () => {
    const out = explainReply('anything', {}, null, FALLBACK_OVERLAYS);
    expect(out.kind).toBe('echo');
    expect(out.text).toContain('anything');
    expect(explainReply('', {}, null, FALLBACK_OVERLAYS).text).toContain('Aaron');
  });
});
