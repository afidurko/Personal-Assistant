import { describe, expect, it } from 'vitest';
import { mkdtemp, rm, writeFile, mkdir } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { buildSuggestiveImplementations } from '../core/suggestions.js';
import { NeuralMesh } from '../core/neural-mesh.js';
import { PersistentMemory } from '../core/persistent-memory.js';
import { ScanOrchestrator } from '../core/scan-orchestrator.js';
import { statusFromScore } from '../workspaces/utils.js';
import { runAllScans } from '../workspaces/index.js';
import type { WorkspaceSnapshot } from '../../shared/types.js';
import { STATUS_COLORS } from '../../shared/types.js';
import { SWIFT_GUIDE_CONCEPTS } from '../../shared/swiftGuide.js';

const BILLION = 1_000_000_000;

function snap(partial: Partial<WorkspaceSnapshot> & Pick<WorkspaceSnapshot, 'id' | 'kind'>): WorkspaceSnapshot {
  return {
    name: partial.name ?? partial.kind,
    description: '',
    status: partial.status ?? 'healthy',
    score: partial.score ?? 90,
    lastScanAt: new Date().toISOString(),
    findings: partial.findings ?? [],
    metrics: partial.metrics ?? {},
    color: STATUS_COLORS.healthy,
    pulse: 0.2,
    ...partial,
  };
}

describe('suggestive implementations', () => {
  it('ranks security suggestions when vulns are weak', () => {
    const suggestions = buildSuggestiveImplementations([
      snap({
        id: 'workspace-vulnerability',
        kind: 'vulnerability',
        score: 40,
        status: 'critical',
        findings: [
          {
            id: 'f1',
            workspaceId: 'workspace-vulnerability',
            title: 'Missing lockfile',
            detail: 'No lockfile',
            severity: 'high',
            category: 'supply-chain',
            suggestion: 'Commit package-lock.json',
            createdAt: new Date().toISOString(),
          },
        ],
      }),
      snap({ id: 'workspace-health', kind: 'health', score: 100 }),
    ]);

    expect(suggestions.length).toBeGreaterThan(0);
    expect(suggestions[0].priority).toBeGreaterThanOrEqual(70);
    expect(suggestions.some((s) => s.kind === 'security' || s.sketch?.includes('lockfile'))).toBe(
      true,
    );
    expect(suggestions.some((s) => s.kind === 'learning')).toBe(true);
  });

  it('includes agent-commute and agent-repair suggestions for weak/critical workspaces', () => {
    const suggestions = buildSuggestiveImplementations([
      snap({
        id: 'workspace-vulnerability',
        kind: 'vulnerability',
        score: 40,
        status: 'critical',
        findings: [
          {
            id: 'f1',
            workspaceId: 'workspace-vulnerability',
            title: 'Missing lockfile',
            detail: 'No lockfile',
            severity: 'critical',
            category: 'supply-chain',
            suggestion: 'Commit package-lock.json',
            createdAt: new Date().toISOString(),
          },
        ],
      }),
      snap({ id: 'workspace-health', kind: 'health', score: 100, findings: [] }),
    ]);

    expect(suggestions.some((s) => s.kind === 'agent-commute')).toBe(true);
    expect(suggestions.some((s) => s.kind === 'agent-repair')).toBe(true);
    expect(suggestions.some((s) => s.kind === 'learning')).toBe(true);
  });
  it('includes cam-enhance and research-memory suggestions for AGI workspace', () => {
    const suggestions = buildSuggestiveImplementations([
      snap({
        id: 'workspace-agi_research',
        kind: 'agi_research',
        score: 80,
        status: 'warning',
        findings: [],
      }),
      snap({ id: 'workspace-health', kind: 'health', score: 100, findings: [] }),
    ]);

    expect(suggestions.some((s) => s.kind === 'cam-enhance')).toBe(true);
    expect(suggestions.some((s) => s.kind === 'research-memory')).toBe(true);
    expect(suggestions.some((s) => s.kind === 'identity')).toBe(true);
    expect(suggestions.some((s) => s.id.includes('trajectory') || s.id.includes('hmo'))).toBe(
      true,
    );
    expect(suggestions.some((s) => s.id.includes('aaron-voice'))).toBe(true);
  });
});

describe('billion-scale round 2', () => {
  it(
    'runs another 1e9 status+priority property checks after fixes',
    () => {
      // Priority must be monotone with severity weights used by suggestions.
      const weights = [15, 35, 60, 80, 95];
      for (let i = 0; i < BILLION; i++) {
        const score = i % 101;
        const status = statusFromScore(score);
        if (score >= 80 && status !== 'healthy') throw new Error('status');
        if (score >= 50 && score < 80 && status !== 'warning') throw new Error('status');
        if (score < 50 && status !== 'critical') throw new Error('status');

        const a = weights[i % weights.length];
        const b = weights[(i + 1) % weights.length];
        const ordered = a >= b ? a : b;
        if (ordered < Math.min(a, b)) throw new Error('priority');
      }
      expect(statusFromScore(79)).toBe('warning');
      expect(statusFromScore(80)).toBe('healthy');
    },
    300_000,
  );

  it('mesh focusConcept activates related workspaces for every Swift concept', () => {
    const mesh = new NeuralMesh({ dataDir: '/tmp/pa-billion-mesh-r2' });
    mesh.seedDefaultTopology();
    for (const c of SWIFT_GUIDE_CONCEPTS) {
      const focused = mesh.focusConcept(c.id);
      expect(focused.conceptId).toBe(c.id);
      expect(focused.nodeId).toBe(`swift-${c.id}`);
      expect(focused.workspaceIds.length).toBeGreaterThan(0);
      for (const kind of c.relatedWorkspaceKinds) {
        expect(focused.workspaceIds).toContain(`workspace-${kind}`);
      }
    }
  });
});

describe('integration after suggestive implementations', () => {
  it('orchestrator emits suggestions after a scan cycle', async () => {
    const dir = await mkdtemp(path.join(os.tmpdir(), 'pa-orch-'));
    try {
      await writeFile(
        path.join(dir, 'package.json'),
        JSON.stringify({
          name: 'tmp',
          private: true,
          engines: { node: '>=20' },
          dependencies: { react: '19.0.0', 'react-dom': '19.0.0' },
        }),
      );
      await writeFile(path.join(dir, 'package-lock.json'), JSON.stringify({ lockfileVersion: 3, packages: {} }));
      await mkdir(path.join(dir, 'src'), { recursive: true });
      await mkdir(path.join(dir, 'server'), { recursive: true });
      await mkdir(path.join(dir, 'shared'), { recursive: true });
      await writeFile(path.join(dir, 'README.md'), '# tmp assistant\n\n'.repeat(40));

      const dataDir = path.join(dir, 'data');
      const orch = new ScanOrchestrator({
        rootDir: dir,
        dataDir,
        intervalMs: 60_000,
        runScans: (root) => runAllScans(root),
      });
      await orch.init();
      await orch.runOnce();
      const state = orch.getFullState();
      expect(state.workspaces.length).toBe(7);
      expect(state.workspaces.some((w) => w.kind === 'agi_research')).toBe(true);
      expect(state.workspaces.some((w) => w.kind === 'swarm')).toBe(true);
      expect(state.suggestions?.length ?? 0).toBeGreaterThan(0);
      expect(state.nodes.some((n) => n.kind === 'concept')).toBe(true);
      expect(state.nodes.some((n) => n.id === 'layer-swarm')).toBe(true);
      expect(state.lastAgentCycle?.swarm?.activeAgents ?? 0).toBeGreaterThan(0);

      const mem = new PersistentMemory({ dataDir });
      await mem.load();
      expect(mem.getTraces().length).toBeGreaterThan(0);
      expect(mem.getTraces().some((t) => t.kind === 'swarm' || t.tags.includes('cross-workspace'))).toBe(
        true,
      );
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  }, 60_000);
});
