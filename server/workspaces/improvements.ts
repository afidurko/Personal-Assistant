import { WORKSPACE_META, STATUS_COLORS } from '../../shared/types.js';
import type { Finding, WorkspaceKind, WorkspaceSnapshot } from '../../shared/types.js';
import type { WorkspaceScanner } from './types.js';
import { architectureScanner } from './architecture.js';
import { agiResearchScanner } from './agi-research.js';
import { healthScanner } from './health.js';
import { swarmScanner } from './swarm.js';
import { updatesScanner } from './updates.js';
import { vulnerabilityScanner } from './vulnerability.js';
import {
  makeFinding,
  now,
  pulseFromScore,
  scoreFromFindings,
  statusFromScore,
} from './utils.js';

const KIND = 'improvements' as const;
const ID = 'workspace-improvements';
const META = WORKSPACE_META[KIND];

export interface ImprovementsScanOptions {
  /** Prior snapshots from other workspaces; when omitted, a light re-scan runs. */
  prior?: WorkspaceSnapshot[];
}

async function lightRescan(rootDir: string): Promise<WorkspaceSnapshot[]> {
  // Avoid nesting improvements in the light pass
  return Promise.all([
    healthScanner.scan(rootDir),
    architectureScanner.scan(rootDir),
    vulnerabilityScanner.scan(rootDir),
    updatesScanner.scan(rootDir),
    agiResearchScanner.scan(rootDir),
    swarmScanner.scan(rootDir),
  ]);
}

function byKind(snapshots: WorkspaceSnapshot[]): Partial<Record<WorkspaceKind, WorkspaceSnapshot>> {
  const map: Partial<Record<WorkspaceKind, WorkspaceSnapshot>> = {};
  for (const s of snapshots) {
    if (s.kind !== 'improvements') map[s.kind] = s;
  }
  return map;
}

function synthesize(prior: WorkspaceSnapshot[]): Finding[] {
  const map = byKind(prior);
  const findings: Finding[] = [];

  const health = map.health;
  const arch = map.architecture;
  const vuln = map.vulnerability;
  const updates = map.updates;
  const agi = map.agi_research;
  const swarm = map.swarm;

  if (swarm && (swarm.score < 50 || swarm.status === 'critical')) {
    findings.push(
      makeFinding(ID, {
        title: 'Repair swarm privilege / lineage wiring',
        detail: `Swarm workspace score is ${swarm.score} with ${swarm.findings.length} finding(s).`,
        severity: 'high',
        category: 'priority',
        suggestion:
          'Restore config/swarm/* + team.tooling + privilege_inheritance so all agents share the bus.',
        relatedNodeIds: ['workspace-swarm', 'layer-swarm'],
      }),
    );
  }

  if (agi && (agi.score < 50 || agi.status === 'critical')) {
    findings.push(
      makeFinding(ID, {
        title: 'Repair AGI research scan wiring',
        detail: `AGI research workspace score is ${agi.score} with ${agi.findings.length} finding(s).`,
        severity: 'high',
        category: 'priority',
        suggestion:
          'Restore team config / scripts / switch.cam_enhance hold before relying on daily enhancement proposals.',
        relatedNodeIds: ['workspace-agi-research'],
      }),
    );
  }

  if (vuln && (vuln.score < 50 || vuln.status === 'critical')) {
    findings.push(
      makeFinding(ID, {
        title: 'Prioritize security patching',
        detail: `Vulnerability workspace score is ${vuln.score} with ${vuln.findings.length} finding(s).`,
        severity: 'critical',
        category: 'priority',
        suggestion:
          'Address critical/high vulnerability findings first (secrets, lockfile, CORS) before feature work.',
        relatedNodeIds: [vuln.id],
      }),
    );
  } else if (vuln && vuln.score < 80) {
    findings.push(
      makeFinding(ID, {
        title: 'Reduce threat surface',
        detail: `Vulnerability score ${vuln.score} — residual medium risks remain.`,
        severity: 'medium',
        category: 'priority',
        suggestion: 'Schedule a hardening pass for scripts, CORS, and dependency hygiene.',
        relatedNodeIds: [vuln.id],
      }),
    );
  }

  if (arch && (arch.score < 50 || arch.status === 'critical')) {
    findings.push(
      makeFinding(ID, {
        title: 'Modularize architecture',
        detail: `Architecture score ${arch.score}; layering/coupling issues dominate.`,
        severity: 'high',
        category: 'structure',
        suggestion:
          'Restore clear src / server / shared boundaries and add tests around the neural mesh.',
        relatedNodeIds: [arch.id],
      }),
    );
  } else if (arch && Number(arch.metrics.deepImportHits ?? 0) > 0) {
    findings.push(
      makeFinding(ID, {
        title: 'Untangle deep import coupling',
        detail: `${arch.metrics.deepImportHits} deep relative import(s) flagged.`,
        severity: 'low',
        category: 'structure',
        suggestion: 'Introduce path aliases and shared barrels to flatten import graphs.',
        relatedNodeIds: [arch.id],
      }),
    );
  }

  if (health && health.score < 60) {
    findings.push(
      makeFinding(ID, {
        title: 'Stabilize host vitals',
        detail: `System health score ${health.score}.`,
        severity: health.score < 40 ? 'high' : 'medium',
        category: 'ops',
        suggestion: 'Resolve missing node_modules / project dirs and relieve memory/disk pressure.',
        relatedNodeIds: [health.id],
      }),
    );
  }

  if (updates && updates.score < 70) {
    findings.push(
      makeFinding(ID, {
        title: 'Close dependency drift',
        detail: `Updates workspace score ${updates.score}.`,
        severity: 'medium',
        category: 'maintenance',
        suggestion: 'Pin wildcards, align react/react-dom, and declare engines.node.',
        relatedNodeIds: [updates.id],
      }),
    );
  }

  // Cross-signal: weak arch + high vulns → governance
  if (arch && vuln && arch.score < 70 && vuln.score < 70) {
    findings.push(
      makeFinding(ID, {
        title: 'Establish scan-driven governance',
        detail: 'Both architecture and vulnerability workspaces are degraded.',
        severity: 'high',
        category: 'process',
        suggestion:
          'Gate merges on workspace scores (health + vuln floors) and document the layer map in README.',
        relatedNodeIds: [arch.id, vuln.id],
      }),
    );
  }

  // Cross-signal: good health but stubby docs / updates
  if (health && health.score >= 80 && updates && Number(updates.metrics.readmeLength ?? 0) < 80) {
    findings.push(
      makeFinding(ID, {
        title: 'Document a healthy system',
        detail: 'Vitals look fine but the README is still stubby.',
        severity: 'info',
        category: 'docs',
        suggestion: 'Capture runbooks for scan cycles, mesh regions, and recovery steps.',
        relatedNodeIds: [health.id, updates?.id].filter(Boolean) as string[],
      }),
    );
  }

  // Lift the top finding from each prior workspace as a concrete next action
  for (const snap of Object.values(map)) {
    if (!snap) continue;
    const top = [...snap.findings].sort((a, b) => severityRank(b.severity) - severityRank(a.severity))[0];
    if (!top || top.severity === 'info') continue;
    if (severityRank(top.severity) < severityRank('medium')) continue;
    findings.push(
      makeFinding(ID, {
        title: `Next action: ${top.title}`,
        detail: `From ${snap.name}: ${top.detail}`,
        severity: top.severity === 'critical' ? 'high' : top.severity === 'high' ? 'medium' : 'low',
        category: 'action',
        suggestion: top.suggestion ?? `Resolve “${top.title}” in the ${snap.name} workspace.`,
        relatedNodeIds: [snap.id, top.id],
      }),
    );
  }

  if (findings.length === 0) {
    findings.push(
      makeFinding(ID, {
        title: 'System looks well-tuned',
        detail: 'No cross-workspace priorities exceeded improvement thresholds.',
        severity: 'info',
        category: 'status',
        suggestion: 'Keep continuous scan cycles running and watch for score regressions.',
      }),
    );
  }

  return findings;
}

function severityRank(s: Finding['severity']): number {
  switch (s) {
    case 'critical':
      return 5;
    case 'high':
      return 4;
    case 'medium':
      return 3;
    case 'low':
      return 2;
    default:
      return 1;
  }
}

export const improvementsScanner: WorkspaceScanner & {
  scanWithPrior(rootDir: string, prior?: WorkspaceSnapshot[]): Promise<WorkspaceSnapshot>;
} = {
  id: ID,
  kind: KIND,

  async scan(rootDir: string): Promise<WorkspaceSnapshot> {
    return improvementsScanner.scanWithPrior(rootDir);
  },

  async scanWithPrior(rootDir: string, prior?: WorkspaceSnapshot[]): Promise<WorkspaceSnapshot> {
    console.log('[improvements] synthesizing cross-workspace suggestions…');
    const snapshots = prior?.length ? prior : await lightRescan(rootDir);
    const findings = synthesize(snapshots);
    const score = scoreFromFindings(findings);
    const status = statusFromScore(score);

    const map = byKind(snapshots);
    const metrics: Record<string, number | string | boolean> = {
      priorCount: snapshots.length,
      healthScore: map.health?.score ?? -1,
      architectureScore: map.architecture?.score ?? -1,
      vulnerabilityScore: map.vulnerability?.score ?? -1,
      updatesScore: map.updates?.score ?? -1,
      agiResearchScore: map.agi_research?.score ?? -1,
      swarmScore: map.swarm?.score ?? -1,
      suggestionCount: findings.length,
      findingCount: findings.length,
      usedPrior: Boolean(prior?.length),
    };

    console.log(`[improvements] score=${score} suggestions=${findings.length}`);

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
