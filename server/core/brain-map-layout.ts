import type { BrainRegion } from '../../shared/types.js';

/**
 * Canonical region anchors projected from FreeSurfer-like Cam cortex centroids
 * (config/connectome/anatomy-centroids.json) into a left-lateral 0–1 map:
 *   x ← anterior→posterior (FS Y)
 *   y ← superior→inferior (FS Z, flipped for SVG)
 */
const REGION_ANCHORS: Record<BrainRegion, { x: number; y: number }> = {
  prefrontal: { x: 0.18, y: 0.28 },
  cortex: { x: 0.42, y: 0.22 },
  thalamus: { x: 0.48, y: 0.48 },
  hippocampus: { x: 0.55, y: 0.62 },
  amygdala: { x: 0.52, y: 0.58 },
  insula: { x: 0.4, y: 0.42 },
  cerebellum: { x: 0.72, y: 0.78 },
  basal_ganglia: { x: 0.44, y: 0.45 },
  striatum: { x: 0.4, y: 0.4 },
  repair_loop: { x: 0.58, y: 0.34 },
  swarm_bus: { x: 0.32, y: 0.5 },
};

/**
 * Layout a node within (or near) a brain region.
 * Multiple nodes in the same region fan out in a small arc around the anchor.
 */
export function layoutForRegion(
  region: BrainRegion,
  index: number,
  total: number,
): { x: number; y: number } {
  const anchor = REGION_ANCHORS[region] ?? { x: 0.5, y: 0.5 };

  if (total <= 1) {
    return { x: clamp01(anchor.x), y: clamp01(anchor.y) };
  }

  // Fan along a gentle arc so co-located nodes don't stack.
  const spread = Math.min(0.12, 0.04 + total * 0.015);
  const t = index / (total - 1) - 0.5; // -0.5 … 0.5
  const angle = t * Math.PI * 0.55;
  const x = anchor.x + Math.sin(angle) * spread;
  const y = anchor.y + Math.cos(angle) * spread * 0.55 - spread * 0.15;

  return { x: clamp01(x), y: clamp01(y) };
}

export function regionAnchor(region: BrainRegion): { x: number; y: number } {
  return { ...REGION_ANCHORS[region] };
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}
