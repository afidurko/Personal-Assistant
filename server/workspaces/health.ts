import os from 'node:os';
import path from 'node:path';
import { promises as fs } from 'node:fs';
import { WORKSPACE_META, STATUS_COLORS } from '../../shared/types.js';
import type { Finding, WorkspaceSnapshot } from '../../shared/types.js';
import type { WorkspaceScanner } from './types.js';
import {
  makeFinding,
  now,
  pathExists,
  pulseFromScore,
  scoreFromFindings,
  statusFromScore,
} from './utils.js';

const KIND = 'health' as const;
const ID = 'workspace-health';
const META = WORKSPACE_META[KIND];

interface DiskStats {
  totalBytes: number;
  freeBytes: number;
  availableBytes: number;
}

async function getDiskStats(rootDir: string): Promise<DiskStats | null> {
  const fsAny = fs as typeof fs & {
    statfs?: (path: string) => Promise<{
      bsize: number;
      blocks: number;
      bfree: number;
      bavail: number;
    }>;
  };
  if (typeof fsAny.statfs === 'function') {
    try {
      const s = await fsAny.statfs(rootDir);
      return {
        totalBytes: s.bsize * s.blocks,
        freeBytes: s.bsize * s.bfree,
        availableBytes: s.bsize * s.bavail,
      };
    } catch {
      /* fall through */
    }
  }
  // Fallback: probe free space via a temp write estimate is unreliable;
  // surface unknown disk metrics as zeros and let findings note the gap.
  return null;
}

function cpuUsagePercent(): number {
  const cpus = os.cpus();
  if (!cpus.length) return 0;
  let idle = 0;
  let total = 0;
  for (const cpu of cpus) {
    const t = Object.values(cpu.times).reduce((a, b) => a + b, 0);
    idle += cpu.times.idle;
    total += t;
  }
  if (total === 0) return 0;
  return Math.round((1 - idle / total) * 1000) / 10;
}

export const healthScanner: WorkspaceScanner = {
  id: ID,
  kind: KIND,

  async scan(rootDir: string): Promise<WorkspaceSnapshot> {
    console.log('[health] scanning system vitals…');
    const findings: Finding[] = [];
    const mem = process.memoryUsage();
    const totalMem = os.totalmem();
    const freeMem = os.freemem();
    const usedMemRatio = 1 - freeMem / totalMem;
    const heapUsedMb = Math.round(mem.heapUsed / 1024 / 1024);
    const rssMb = Math.round(mem.rss / 1024 / 1024);
    const cpuPct = cpuUsagePercent();
    const load = os.loadavg();
    const uptimeSec = Math.round(os.uptime());
    const disk = await getDiskStats(rootDir);

    const hasPackageJson = await pathExists(path.join(rootDir, 'package.json'));
    const hasNodeModules = await pathExists(path.join(rootDir, 'node_modules'));
    const hasSrc = await pathExists(path.join(rootDir, 'src'));
    const hasServer = await pathExists(path.join(rootDir, 'server'));
    const hasShared = await pathExists(path.join(rootDir, 'shared'));

    if (usedMemRatio > 0.9) {
      findings.push(
        makeFinding(ID, {
          title: 'Host memory critically low',
          detail: `${Math.round(usedMemRatio * 100)}% of system memory in use (${Math.round(freeMem / 1024 / 1024)} MB free).`,
          severity: 'critical',
          category: 'resources',
          suggestion: 'Close heavy processes or increase available memory before long scan cycles.',
        }),
      );
    } else if (usedMemRatio > 0.75) {
      findings.push(
        makeFinding(ID, {
          title: 'Elevated host memory pressure',
          detail: `${Math.round(usedMemRatio * 100)}% of system memory in use.`,
          severity: 'medium',
          category: 'resources',
          suggestion: 'Monitor memory during scans; consider reducing concurrent workloads.',
        }),
      );
    }

    if (rssMb > 512) {
      findings.push(
        makeFinding(ID, {
          title: 'Process RSS is high',
          detail: `Node process resident set is ${rssMb} MB (heap ${heapUsedMb} MB).`,
          severity: 'medium',
          category: 'process',
          suggestion: 'Profile heap growth if RSS continues to climb across scan cycles.',
        }),
      );
    }

    const cores = os.cpus().length || 1;
    if (load[0] > cores * 2) {
      findings.push(
        makeFinding(ID, {
          title: 'Load average critically high',
          detail: `1-min load ${load[0].toFixed(2)} on ${cores} core(s).`,
          severity: 'high',
          category: 'resources',
          suggestion: 'Defer non-critical scans until load settles.',
        }),
      );
    } else if (load[0] > cores) {
      findings.push(
        makeFinding(ID, {
          title: 'Load average above core count',
          detail: `1-min load ${load[0].toFixed(2)} vs ${cores} core(s).`,
          severity: 'low',
          category: 'resources',
          suggestion: 'Expect slower scan throughput under contention.',
        }),
      );
    }

    if (disk) {
      const usedRatio = 1 - disk.availableBytes / disk.totalBytes;
      if (usedRatio > 0.95) {
        findings.push(
          makeFinding(ID, {
            title: 'Disk nearly full',
            detail: `${Math.round(usedRatio * 100)}% disk used; ${Math.round(disk.availableBytes / 1024 / 1024)} MB available.`,
            severity: 'critical',
            category: 'disk',
            suggestion: 'Free space under the project root before writing scan artifacts.',
          }),
        );
      } else if (usedRatio > 0.85) {
        findings.push(
          makeFinding(ID, {
            title: 'Disk space running low',
            detail: `${Math.round(usedRatio * 100)}% disk used.`,
            severity: 'medium',
            category: 'disk',
            suggestion: 'Clean build outputs (dist, coverage) if space tightens further.',
          }),
        );
      }
    } else {
      findings.push(
        makeFinding(ID, {
          title: 'Disk stats unavailable',
          detail: 'fs.statfs is not available in this runtime; disk free space was not measured.',
          severity: 'info',
          category: 'disk',
          suggestion: 'Run on Node 18.15+ or a platform that exposes fs.statfs for full vitals.',
        }),
      );
    }

    if (!hasPackageJson) {
      findings.push(
        makeFinding(ID, {
          title: 'Missing package.json',
          detail: `No package.json found at ${rootDir}.`,
          severity: 'critical',
          category: 'project',
          suggestion: 'Confirm the scan root points at the application workspace.',
        }),
      );
    }

    if (!hasNodeModules) {
      findings.push(
        makeFinding(ID, {
          title: 'Dependencies not installed',
          detail: 'node_modules is missing — runtime and scanners may fail.',
          severity: 'high',
          category: 'project',
          suggestion: 'Run npm install (or equivalent) before starting continuous scans.',
        }),
      );
    }

    const missingDirs = (
      [
        ['src', hasSrc],
        ['server', hasServer],
        ['shared', hasShared],
      ] as const
    ).filter(([, ok]) => !ok);

    if (missingDirs.length) {
      findings.push(
        makeFinding(ID, {
          title: 'Expected project directories missing',
          detail: `Missing: ${missingDirs.map(([n]) => n).join(', ')}.`,
          severity: missingDirs.length >= 2 ? 'high' : 'medium',
          category: 'project',
          suggestion: 'Restore the src / server / shared layout expected by this assistant.',
        }),
      );
    }

    if (uptimeSec < 120) {
      findings.push(
        makeFinding(ID, {
          title: 'Host recently rebooted',
          detail: `System uptime is only ${uptimeSec}s.`,
          severity: 'info',
          category: 'uptime',
          suggestion: 'Allow services to warm up before treating early scan noise as critical.',
        }),
      );
    }

    const score = scoreFromFindings(findings);
    const status = statusFromScore(score);

    const metrics: Record<string, number | string | boolean> = {
      heapUsedMb,
      rssMb,
      cpuPercent: cpuPct,
      memUsedPercent: Math.round(usedMemRatio * 1000) / 10,
      freeMemMb: Math.round(freeMem / 1024 / 1024),
      totalMemMb: Math.round(totalMem / 1024 / 1024),
      load1: Math.round(load[0] * 100) / 100,
      load5: Math.round(load[1] * 100) / 100,
      load15: Math.round(load[2] * 100) / 100,
      uptimeSec,
      cpuCores: cores,
      hasPackageJson,
      hasNodeModules,
      hasSrc,
      hasServer,
      hasShared,
      diskTotalMb: disk ? Math.round(disk.totalBytes / 1024 / 1024) : 0,
      diskAvailableMb: disk ? Math.round(disk.availableBytes / 1024 / 1024) : 0,
      diskMeasured: Boolean(disk),
      findingCount: findings.length,
    };

    console.log(`[health] score=${score} status=${status} findings=${findings.length}`);

    return {
      id: ID,
      kind: KIND,
      name: META.name,
      description: META.description,
      status,
      score,
      lastScanAt: now(),
      findings,
      metrics,
      color: STATUS_COLORS[status] ?? META.defaultColor,
      pulse: pulseFromScore(score),
    };
  },
};
