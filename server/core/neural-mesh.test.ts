import { describe, expect, it } from 'vitest';
import { NeuralMesh } from './neural-mesh';
import type { WorkspaceSnapshot } from '../../shared/types';
import { STATUS_COLORS } from '../../shared/types';

function snap(partial: Partial<WorkspaceSnapshot> & Pick<WorkspaceSnapshot, 'id' | 'kind'>): WorkspaceSnapshot {
  return {
    name: partial.name ?? partial.kind,
    description: '',
    status: partial.status ?? 'healthy',
    score: partial.score ?? 90,
    lastScanAt: new Date().toISOString(),
    findings: partial.findings ?? [],
    metrics: {},
    color: STATUS_COLORS.healthy,
    pulse: 0.2,
    ...partial,
  };
}

describe('NeuralMesh workspace linking', () => {
  it('updates node status colors from workspace snapshots', () => {
    const mesh = new NeuralMesh({ dataDir: '/tmp/pa-mesh-test' });
    mesh.seedDefaultTopology();

    mesh.applyScanResults([
      snap({ id: 'workspace-health', kind: 'health', status: 'healthy', score: 100 }),
      snap({ id: 'workspace-vulnerability', kind: 'vulnerability', status: 'critical', score: 20 }),
      snap({ id: 'workspace-updates', kind: 'updates', status: 'warning', score: 65 }),
    ]);

    const health = mesh.findWorkspaceNode('workspace-health', 'health');
    const vuln = mesh.findWorkspaceNode('vulnerability');
    const updates = mesh.findWorkspaceNode('workspace-updates');

    expect(health?.status).toBe('healthy');
    expect(health?.color).toBe(STATUS_COLORS.healthy);
    expect(health?.workspaceId).toBe('workspace-health');

    expect(vuln?.status).toBe('critical');
    expect(vuln?.color).toBe(STATUS_COLORS.critical);

    expect(updates?.status).toBe('warning');
    expect(updates?.color).toBe(STATUS_COLORS.warning);
  });

  it('marks workspace nodes scanning for live color pulse', () => {
    const mesh = new NeuralMesh({ dataDir: '/tmp/pa-mesh-test-2' });
    mesh.seedDefaultTopology();
    mesh.markScanning();
    const health = mesh.findWorkspaceNode('health');
    expect(health?.status).toBe('scanning');
    expect(health?.color).toBe(STATUS_COLORS.scanning);
  });
});
