import { describe, expect, it } from 'vitest';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { needsAttentionScanner } from './needs-attention.js';
import { AGENT_LAYERS, MESH_AGENTS } from '../../shared/agentLayers.js';

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

describe('needs attention workspace', () => {
  it('registers attention layer agents', () => {
    expect(AGENT_LAYERS.some((l) => l.id === 'attention')).toBe(true);
    const ids = MESH_AGENTS.filter((a) => a.layer === 'attention').map((a) => a.id);
    expect(ids).toEqual(
      expect.arrayContaining([
        'attention-triage',
        'workspace-connector',
        'attention-dispatcher',
      ]),
    );
  });

  it('scans registry connectivity and emits a queue', async () => {
    const snap = await needsAttentionScanner.scanWithPrior(rootDir, []);
    expect(snap.kind).toBe('needs_attention');
    expect(snap.id).toBe('workspace-needs-attention');
    expect(Number(snap.metrics.codingWorkspaceCount)).toBeGreaterThan(0);
    expect(snap.findings.length).toBeGreaterThan(0);
    expect(typeof snap.metrics.connectedWorkspaces).toBe('number');
  });
});
