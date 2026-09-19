/**
 * Runtime distillates under data/runtime (gitignored churn).
 * Seeds from vault copies when missing so cortex has something to light.
 */
import { mkdir, readFile, writeFile, copyFile, access } from 'node:fs/promises';
import path from 'node:path';

const RUNTIME_FILES = [
  'live-activity.json',
  'improve-tasks.json',
  'activity-events.jsonl',
  'system-health.json',
  'tract-weights.json',
  'plasticity-timeline.json',
  'neurogenesis-columns.json',
] as const;

export type RuntimeFile = (typeof RUNTIME_FILES)[number];

export class RuntimeStore {
  readonly dir: string;
  private readonly vaultDir: string;

  constructor(rootDir: string) {
    this.dir = path.join(rootDir, 'data', 'runtime');
    this.vaultDir = path.join(rootDir, 'vault', '10-Mesh-Distillates');
  }

  async ensure(): Promise<void> {
    await mkdir(this.dir, { recursive: true });
    for (const name of RUNTIME_FILES) {
      const dest = path.join(this.dir, name);
      try {
        await access(dest);
      } catch {
        const src = path.join(this.vaultDir, name);
        try {
          await copyFile(src, dest);
        } catch {
          if (name.endsWith('.jsonl')) await writeFile(dest, '', 'utf8');
          else if (name === 'live-activity.json') {
            await writeFile(
              dest,
              JSON.stringify(
                {
                  at: new Date().toISOString(),
                  epoch: Date.now(),
                  firing: [],
                  firing_count: 0,
                  standing: true,
                },
                null,
                2,
              ),
              'utf8',
            );
          } else {
            await writeFile(dest, '{}\n', 'utf8');
          }
        }
      }
    }
  }

  pathFor(name: RuntimeFile | string): string {
    return path.join(this.dir, name);
  }

  async readJson<T = unknown>(name: RuntimeFile | string, fallback: T): Promise<T> {
    try {
      const raw = await readFile(this.pathFor(name), 'utf8');
      return JSON.parse(raw) as T;
    } catch {
      return fallback;
    }
  }

  async writeJson(name: RuntimeFile | string, value: unknown): Promise<void> {
    await mkdir(this.dir, { recursive: true });
    await writeFile(this.pathFor(name), `${JSON.stringify(value, null, 2)}\n`, 'utf8');
  }

  async appendLine(name: RuntimeFile | string, line: string): Promise<void> {
    await mkdir(this.dir, { recursive: true });
    const { appendFile } = await import('node:fs/promises');
    await appendFile(this.pathFor(name), line.endsWith('\n') ? line : `${line}\n`, 'utf8');
  }
}
