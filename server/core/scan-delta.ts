/**
 * Scan delta — skip expensive architecture tree walks when source mtimes unchanged.
 */
import { stat } from 'node:fs/promises';
import path from 'node:path';
import type { WorkspaceSnapshot } from '../../shared/types.js';
import { runAllScans as runAllScansFresh } from '../workspaces/index.js';

const WATCH_ROOTS = ['src', 'server', 'shared', 'package.json', 'package-lock.json', 'config'];

export class ScanDeltaCache {
  private lastFingerprint: string | null = null;
  private snapshots: WorkspaceSnapshot[] | null = null;

  async computeFingerprint(rootDir: string): Promise<string> {
    const parts: string[] = [];
    for (const rel of WATCH_ROOTS) {
      try {
        const s = await stat(path.join(rootDir, rel));
        parts.push(`${rel}:${s.mtimeMs}:${s.size}`);
      } catch {
        parts.push(`${rel}:missing`);
      }
    }
    return parts.join('|');
  }

  async run(rootDir: string): Promise<{ snapshots: WorkspaceSnapshot[]; cacheHit: boolean }> {
    const fp = await this.computeFingerprint(rootDir);
    if (this.lastFingerprint === fp && this.snapshots) {
      const at = new Date().toISOString();
      const snapshots = this.snapshots.map((s) => ({
        ...s,
        lastScanAt: at,
        findings: [...s.findings],
        metrics: { ...s.metrics, cacheHit: true },
      }));
      return { snapshots, cacheHit: true };
    }
    const snapshots = await runAllScansFresh(rootDir);
    this.lastFingerprint = fp;
    this.snapshots = snapshots.map((s) => ({
      ...s,
      findings: [...s.findings],
      metrics: { ...s.metrics },
    }));
    return { snapshots, cacheHit: false };
  }

  invalidate(): void {
    this.lastFingerprint = null;
    this.snapshots = null;
  }
}
