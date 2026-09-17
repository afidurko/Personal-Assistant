import type { WorkspaceSnapshot } from '../../shared/types.js';
import type { WorkspaceScanner } from './types.js';
import { agiResearchScanner } from './agi-research.js';
import { architectureScanner } from './architecture.js';
import { healthScanner } from './health.js';
import { improvementsScanner } from './improvements.js';
import { updatesScanner } from './updates.js';
import { vulnerabilityScanner } from './vulnerability.js';

export type { WorkspaceScanner } from './types.js';
export { agiResearchScanner } from './agi-research.js';
export { architectureScanner } from './architecture.js';
export { healthScanner } from './health.js';
export { improvementsScanner } from './improvements.js';
export { updatesScanner } from './updates.js';
export { vulnerabilityScanner } from './vulnerability.js';
export * from './utils.js';

/** Core scanners excluding improvements (which synthesizes from the others). */
export const coreScanners: WorkspaceScanner[] = [
  healthScanner,
  architectureScanner,
  vulnerabilityScanner,
  updatesScanner,
  agiResearchScanner,
];

export const allScanners: WorkspaceScanner[] = [...coreScanners, improvementsScanner];

/**
 * Run all workspace scanners. Core scans run in Promise.all; improvements
 * synthesizes from those results so suggestions stay coherent.
 */
export async function runAllScans(rootDir: string): Promise<WorkspaceSnapshot[]> {
  console.log(`[workspaces] runAllScans → ${rootDir}`);
  const core = await Promise.all(coreScanners.map((s) => s.scan(rootDir)));
  const improvements = await improvementsScanner.scanWithPrior(rootDir, core);
  return [...core, improvements];
}
