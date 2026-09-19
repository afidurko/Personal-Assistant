import { describe, expect, it } from 'vitest';
import { CamConverse, camReply } from './cam-converse.js';
import path from 'node:path';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';

describe('camReply', () => {
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
});

describe('CamConverse voice gate', () => {
  it('rejects low-score mic turns', async () => {
    const dir = mkdtempSync(path.join(tmpdir(), 'cam-converse-'));
    // Point at repo root so policy JSON loads
    const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..');
    const c = new CamConverse(root);
    const reply = await c.turn({
      text: 'hey from someone else',
      source: 'mic',
      aaron_voice_score: 0.4,
      enrolled: true,
    });
    expect(reply.rejected).toBe(true);
    expect(reply.cam).toMatch(/voice|filtered|ignored|match/i);
    void dir;
  });

  it('accepts typed turns', async () => {
    const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../..');
    const c = new CamConverse(root);
    const reply = await c.turn({ text: 'hello cam', source: 'text' });
    expect(reply.rejected).toBeFalsy();
    expect(reply.cam).toMatch(/Aaron/i);
  });
});
