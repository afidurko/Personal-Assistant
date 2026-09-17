import { randomUUID } from 'node:crypto';
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { MemoryTrace } from '../../shared/types.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_DATA_DIR = path.resolve(__dirname, '../../data');
const DEFAULT_MAX_SCAN_TRACES = 200;
const WEAK_SALIENCE = 0.05;

export interface PersistentMemoryOptions {
  dataDir?: string;
  maxScanTraces?: number;
}

export class PersistentMemory {
  private traces: MemoryTrace[] = [];
  private readonly filePath: string;
  private readonly dataDir: string;
  private readonly maxScanTraces: number;
  private loaded = false;

  constructor(options: PersistentMemoryOptions = {}) {
    this.dataDir = options.dataDir ?? DEFAULT_DATA_DIR;
    this.filePath = path.join(this.dataDir, 'memory.json');
    this.maxScanTraces = options.maxScanTraces ?? DEFAULT_MAX_SCAN_TRACES;
  }

  async load(): Promise<MemoryTrace[]> {
    await mkdir(this.dataDir, { recursive: true });
    try {
      const raw = await readFile(this.filePath, 'utf8');
      const parsed = JSON.parse(raw) as MemoryTrace[];
      this.traces = Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      const code = (err as NodeJS.ErrnoException).code;
      if (code !== 'ENOENT') throw err;
      this.traces = [];
    }
    this.loaded = true;
    return this.getTraces();
  }

  async save(): Promise<void> {
    if (!this.loaded) await this.load();
    await mkdir(this.dataDir, { recursive: true });
    await atomicWriteJson(this.filePath, this.traces);
  }

  async write(trace: Omit<MemoryTrace, 'id'> & { id?: string }): Promise<MemoryTrace> {
    if (!this.loaded) await this.load();
    const now = new Date().toISOString();
    const entry: MemoryTrace = {
      id: trace.id ?? randomUUID(),
      kind: trace.kind,
      content: trace.content,
      workspaceIds: [...trace.workspaceIds],
      nodeIds: [...trace.nodeIds],
      salience: clamp01(trace.salience),
      createdAt: trace.createdAt ?? now,
      lastAccessedAt: trace.lastAccessedAt ?? now,
      decay: clamp01(trace.decay ?? 0),
      tags: [...trace.tags],
    };
    this.traces.push(entry);
    this.prune();
    this.consolidate();
    await this.save();
    return entry;
  }

  async reinforce(id: string, amount = 0.1): Promise<MemoryTrace | null> {
    if (!this.loaded) await this.load();
    const trace = this.traces.find((t) => t.id === id);
    if (!trace) return null;
    trace.salience = clamp01(trace.salience + amount);
    trace.decay = clamp01(trace.decay - amount * 0.5);
    trace.lastAccessedAt = new Date().toISOString();
    await this.save();
    return { ...trace, workspaceIds: [...trace.workspaceIds], nodeIds: [...trace.nodeIds], tags: [...trace.tags] };
  }

  async decayAll(rate: number): Promise<void> {
    if (!this.loaded) await this.load();
    const r = Math.max(0, rate);
    for (const trace of this.traces) {
      trace.decay = clamp01(trace.decay + r * (1 - trace.salience * 0.3));
      trace.salience = clamp01(trace.salience * (1 - r * 0.15));
    }
    this.prune();
    await this.save();
  }

  /**
   * Ranked query by salience * (1 - decay) * recency.
   * Matches free-text against content/tags, or exact tag overlap when tags[] given.
   */
  query(input: string | string[]): MemoryTrace[] {
    const now = Date.now();
    const tags = Array.isArray(input)
      ? input.map((t) => t.toLowerCase())
      : null;
    const text = typeof input === 'string' ? input.trim().toLowerCase() : null;

    const scored = this.traces
      .filter((trace) => {
        if (tags) {
          if (tags.length === 0) return true;
          const traceTags = trace.tags.map((t) => t.toLowerCase());
          return tags.some((t) => traceTags.includes(t));
        }
        if (!text) return true;
        const hay = `${trace.content} ${trace.tags.join(' ')}`.toLowerCase();
        return hay.includes(text) || text.split(/\s+/).some((w) => w && hay.includes(w));
      })
      .map((trace) => {
        const ageMs = Math.max(0, now - Date.parse(trace.lastAccessedAt || trace.createdAt));
        const recency = Math.exp(-ageMs / (1000 * 60 * 60 * 24 * 7)); // ~week half-life feel
        const score = trace.salience * (1 - trace.decay) * recency;
        return { trace, score };
      })
      .sort((a, b) => b.score - a.score);

    return scored.map(({ trace }) => ({
      ...trace,
      workspaceIds: [...trace.workspaceIds],
      nodeIds: [...trace.nodeIds],
      tags: [...trace.tags],
    }));
  }

  getTraces(): MemoryTrace[] {
    return this.traces.map((t) => ({
      ...t,
      workspaceIds: [...t.workspaceIds],
      nodeIds: [...t.nodeIds],
      tags: [...t.tags],
    }));
  }

  /** Drop weak traces and cap always-on scan history. */
  private prune(): void {
    this.traces = this.traces.filter((t) => t.salience >= WEAK_SALIENCE || t.kind !== 'scan');

    const scans = this.traces
      .filter((t) => t.kind === 'scan')
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));

    if (scans.length > this.maxScanTraces) {
      const drop = new Set(scans.slice(this.maxScanTraces).map((t) => t.id));
      this.traces = this.traces.filter((t) => !drop.has(t.id));
    }

    const semantics = this.traces
      .filter((t) => t.kind === 'semantic')
      .sort((a, b) => b.salience - a.salience);
    if (semantics.length > 80) {
      const drop = new Set(semantics.slice(80).map((t) => t.id));
      this.traces = this.traces.filter((t) => !drop.has(t.id));
    }

    // Cap agent / loop traces so continuous autonomy doesn't balloon memory.json
    const agents = this.traces
      .filter((t) => t.kind === 'agent' || t.kind === 'loop')
      .sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
    if (agents.length > 120) {
      const drop = new Set(agents.slice(120).map((t) => t.id));
      this.traces = this.traces.filter((t) => !drop.has(t.id));
    }

    // Also prune non-scan traces that are extremely weak and fully decayed.
    this.traces = this.traces.filter(
      (t) => !(t.salience < WEAK_SALIENCE && t.decay > 0.9 && t.kind !== 'semantic'),
    );
  }

  /** Merge similar scan tags into semantic traces. */
  private consolidate(): void {
    const scans = this.traces.filter((t) => t.kind === 'scan');
    const byTagKey = new Map<string, MemoryTrace[]>();

    for (const scan of scans) {
      const key = [...scan.tags].map((t) => t.toLowerCase()).sort().join('|');
      if (!key) continue;
      const list = byTagKey.get(key) ?? [];
      list.push(scan);
      byTagKey.set(key, list);
    }

    for (const [key, group] of byTagKey) {
      if (group.length < 3) continue;
      const existing = this.traces.find(
        (t) => t.kind === 'semantic' && t.tags.map((x) => x.toLowerCase()).sort().join('|') === key,
      );

      const workspaceIds = unique(group.flatMap((g) => g.workspaceIds));
      const nodeIds = unique(group.flatMap((g) => g.nodeIds));
      const tags = unique(group.flatMap((g) => g.tags));
      const salience = clamp01(
        group.reduce((s, g) => s + g.salience, 0) / group.length + 0.05 * Math.min(group.length, 10),
      );
      const content = `Consolidated pattern [${tags.join(', ')}]: ${group.length} scan traces across ${workspaceIds.join(', ') || 'system'}.`;

      if (existing) {
        existing.content = content;
        existing.workspaceIds = workspaceIds;
        existing.nodeIds = nodeIds;
        existing.salience = Math.max(existing.salience, salience);
        existing.lastAccessedAt = new Date().toISOString();
        existing.decay = clamp01(existing.decay * 0.7);
      } else {
        this.traces.push({
          id: randomUUID(),
          kind: 'semantic',
          content,
          workspaceIds,
          nodeIds,
          salience,
          createdAt: new Date().toISOString(),
          lastAccessedAt: new Date().toISOString(),
          decay: 0,
          tags,
        });
      }
    }
  }
}

async function atomicWriteJson(filePath: string, data: unknown): Promise<void> {
  const tmp = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(tmp, JSON.stringify(data, null, 2), 'utf8');
  await rename(tmp, filePath);
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

function unique(values: string[]): string[] {
  return [...new Set(values)];
}
