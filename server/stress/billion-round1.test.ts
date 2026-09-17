import { describe, expect, it } from 'vitest';
import { scoreFromFindings, statusFromScore } from '../workspaces/utils.js';
import { layoutForRegion } from '../core/brain-map-layout.js';
import { STATUS_COLORS, type BrainRegion, type Finding, type Severity } from '../../shared/types.js';
import { SWIFT_GUIDE_CONCEPTS, conceptNodeId } from '../../shared/swiftGuide.js';

const BILLION = 1_000_000_000;
const SEVERITIES: Severity[] = ['info', 'low', 'medium', 'high', 'critical'];
const REGIONS: BrainRegion[] = [
  'cortex',
  'hippocampus',
  'amygdala',
  'thalamus',
  'prefrontal',
  'cerebellum',
  'insula',
  'basal_ganglia',
  'striatum',
  'repair_loop',
];

describe('billion-scale round 1', () => {
  it(
    'runs 1e9 statusFromScore property checks',
    () => {
      let healthy = 0;
      let warning = 0;
      let critical = 0;
      for (let i = 0; i < BILLION; i++) {
        const score = i % 101;
        const status = statusFromScore(score);
        if (score >= 80) {
          if (status !== 'healthy') throw new Error(`bad healthy ${score}`);
          healthy++;
        } else if (score >= 50) {
          if (status !== 'warning') throw new Error(`bad warning ${score}`);
          warning++;
        } else {
          if (status !== 'critical') throw new Error(`bad critical ${score}`);
          critical++;
        }
      }
      expect(healthy + warning + critical).toBe(BILLION);
    },
    300_000,
  );

  it('scoreFromFindings + layout + catalogs stay coherent (1e7 each)', () => {
    const baseFindings: Finding[] = SEVERITIES.map((severity, idx) => ({
      id: `f-${idx}`,
      workspaceId: 'ws',
      title: severity,
      detail: severity,
      severity,
      category: 'stress',
      createdAt: '2026-01-01T00:00:00.000Z',
    }));

    for (let i = 0; i < 10_000_000; i++) {
      const score = scoreFromFindings(baseFindings.slice(0, i % 6), 100);
      if (score < 0 || score > 100) throw new Error(`score ${score}`);
      const region = REGIONS[i % REGIONS.length];
      const total = (i % 12) + 1;
      const { x, y } = layoutForRegion(region, i % total, total);
      if (x < 0 || x > 1 || y < 0 || y > 1) throw new Error('layout oob');
    }

    for (const color of Object.values(STATUS_COLORS)) {
      expect(color).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
    expect(SWIFT_GUIDE_CONCEPTS).toHaveLength(9);
    for (const c of SWIFT_GUIDE_CONCEPTS) {
      expect(conceptNodeId(c.id)).toBe(`swift-${c.id}`);
      expect(c.relatedWorkspaceKinds.length).toBeGreaterThan(0);
    }
  }, 120_000);
});
