import type { WorkspaceSnapshot } from '../../shared/types.js';
import type { WorkspaceScanner } from './types.js';
import { agiResearchScanner } from './agi-research.js';
import { architectureScanner } from './architecture.js';
import { healthScanner } from './health.js';
import { improvementsScanner } from './improvements.js';
import { needsAttentionScanner } from './needs-attention.js';
import { swarmScanner } from './swarm.js';
import { updatesScanner } from './updates.js';
import { vulnerabilityScanner } from './vulnerability.js';

export type { WorkspaceScanner } from './types.js';
export { agiResearchScanner } from './agi-research.js';
export { architectureScanner } from './architecture.js';
export { healthScanner } from './health.js';
export { improvementsScanner } from './improvements.js';
export { needsAttentionScanner } from './needs-attention.js';
export { swarmScanner } from './swarm.js';
export { updatesScanner } from './updates.js';
export { vulnerabilityScanner } from './vulnerability.js';
export * from './utils.js';

/** Core scanners excluding synthesizers (improvements + needs_attention). */
export const coreScanners: WorkspaceScanner[] = [
  healthScanner,
  architectureScanner,
  vulnerabilityScanner,
  updatesScanner,
  agiResearchScanner,
  swarmScanner,
];

export const allScanners: WorkspaceScanner[] = [
  ...coreScanners,
  improvementsScanner,
  needsAttentionScanner,
];

/**
 * Run all workspace scanners. Core scans run in Promise.all; improvements and
 * needs_attention synthesize from those results so the attention queue stays coherent.
 */
export async function runAllScans(rootDir: string): Promise<WorkspaceSnapshot[]> {
  console.log(`[workspaces] runAllScans → ${rootDir}`);
  const core = await Promise.all(coreScanners.map((s) => s.scan(rootDir)));
  const improvements = await improvementsScanner.scanWithPrior(rootDir, core);
  const needsAttention = await needsAttentionScanner.scanWithPrior(rootDir, [
    ...core,
    improvements,
  ]);
  return [...core, improvements, needsAttention];
}
