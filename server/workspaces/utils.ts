import { promises as fs } from 'node:fs';
import path from 'node:path';
import { v4 as uuid } from 'uuid';
import type { Finding, ScanStatus, Severity } from '../../shared/types.js';

const DEFAULT_IGNORE = new Set([
  'node_modules',
  'dist',
  'dist-server',
  '.git',
  '.next',
  'coverage',
  '.turbo',
  '.cache',
]);

export function now(): string {
  return new Date().toISOString();
}

export function makeFinding(
  workspaceId: string,
  partial: {
    title: string;
    detail: string;
    severity: Severity;
    category: string;
    suggestion?: string;
    relatedNodeIds?: string[];
  },
): Finding {
  return {
    id: uuid(),
    workspaceId,
    title: partial.title,
    detail: partial.detail,
    severity: partial.severity,
    category: partial.category,
    suggestion: partial.suggestion,
    relatedNodeIds: partial.relatedNodeIds,
    createdAt: now(),
  };
}

/** Map findings → score 0–100 (higher is healthier). */
export function scoreFromFindings(findings: Finding[], base = 100): number {
  const weights: Record<Severity, number> = {
    info: 1,
    low: 3,
    medium: 8,
    high: 16,
    critical: 28,
  };
  let score = base;
  for (const f of findings) {
    score -= weights[f.severity] ?? 5;
  }
  return Math.max(0, Math.min(100, Math.round(score)));
}

export function statusFromScore(score: number): ScanStatus {
  if (score >= 80) return 'healthy';
  if (score >= 50) return 'warning';
  return 'critical';
}

export async function readJsonSafe<T = unknown>(filePath: string): Promise<T | null> {
  try {
    const raw = await fs.readFile(filePath, 'utf8');
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function pathExists(p: string): Promise<boolean> {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

export async function walkDir(
  rootDir: string,
  options: {
    ignore?: Set<string>;
    maxDepth?: number;
    extensions?: string[];
  } = {},
): Promise<string[]> {
  const ignore = options.ignore ?? DEFAULT_IGNORE;
  const maxDepth = options.maxDepth ?? 12;
  const extensions = options.extensions;
  const results: string[] = [];

  async function walk(dir: string, depth: number): Promise<void> {
    if (depth > maxDepth) return;
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (ignore.has(entry.name)) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await walk(full, depth + 1);
      } else if (entry.isFile()) {
        if (extensions) {
          const ext = path.extname(entry.name).toLowerCase();
          if (!extensions.includes(ext)) continue;
        }
        results.push(full);
      }
    }
  }

  await walk(rootDir, 0);
  return results;
}

export async function readTextSafe(filePath: string, maxBytes = 256_000): Promise<string | null> {
  try {
    const buf = await fs.readFile(filePath);
    if (buf.byteLength > maxBytes) {
      return buf.subarray(0, maxBytes).toString('utf8');
    }
    return buf.toString('utf8');
  } catch {
    return null;
  }
}

export function pulseFromScore(score: number): number {
  // Lower score → higher pulse intensity (more urgent)
  return Math.max(0.15, Math.min(1, 1 - score / 120));
}
