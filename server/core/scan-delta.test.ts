import { describe, expect, it } from 'vitest';
import { mkdtemp, mkdir, writeFile, utimes } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { ScanDeltaCache } from './scan-delta.js';

describe('ScanDeltaCache', () => {
  it('changes fingerprint when package.json mtime changes', async () => {
    const root = await mkdtemp(path.join(os.tmpdir(), 'scan-delta-'));
    await mkdir(path.join(root, 'src'), { recursive: true });
    await mkdir(path.join(root, 'server'), { recursive: true });
    await mkdir(path.join(root, 'shared'), { recursive: true });
    await mkdir(path.join(root, 'config'), { recursive: true });
    await writeFile(path.join(root, 'package.json'), '{"name":"t"}');
    await writeFile(path.join(root, 'package-lock.json'), '{}');

    const cache = new ScanDeltaCache();
    const fp1 = await cache.computeFingerprint(root);
    const fp2 = await cache.computeFingerprint(root);
    expect(fp1).toBe(fp2);

    const pkg = path.join(root, 'package.json');
    const future = new Date(Date.now() + 60_000);
    await utimes(pkg, future, future);
    const fp3 = await cache.computeFingerprint(root);
    expect(fp3).not.toBe(fp1);
  });
});
