import { describe, expect, it } from 'vitest';
import { STATUS_COLORS, WORKSPACE_META } from './types.js';

describe('shared status palette', () => {
  it('maps every scan status to a color', () => {
    for (const status of Object.keys(STATUS_COLORS) as (keyof typeof STATUS_COLORS)[]) {
      expect(STATUS_COLORS[status]).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });

  it('defines all workspace kinds with regions', () => {
    expect(Object.keys(WORKSPACE_META)).toEqual(
      expect.arrayContaining([
        'health',
        'architecture',
        'vulnerability',
        'updates',
        'improvements',
        'agi_research',
        'swarm',
        'needs_attention',
      ]),
    );
    for (const meta of Object.values(WORKSPACE_META)) {
      expect(meta.name.length).toBeGreaterThan(0);
      expect(meta.region).toBeTruthy();
    }
  });
});
