import path from 'node:path';
import { promises as fs } from 'node:fs';
import { WORKSPACE_META, STATUS_COLORS } from '../../shared/types.js';
import type { Finding, WorkspaceKind, WorkspaceSnapshot } from '../../shared/types.js';
import type { WorkspaceScanner } from './types.js';
import {
  makeFinding,
  now,
  pathExists,
  pulseFromScore,
  readJsonSafe,
  scoreFromFindings,
  statusFromScore,
} from './utils.js';

const KIND = 'needs_attention' as const;
const ID = 'workspace-needs-attention';
const META = WORKSPACE_META[KIND];

interface RegistryWorkspace {
  id?: string;
  label?: string;
  path?: string;
  remote?: string;
  primary?: boolean;
}

interface RegistryDoc {
  workspaces?: RegistryWorkspace[];
  layers?: { coding_workspaces?: RegistryWorkspace[] };
}

interface TeamDoc {
  id?: string;
  cross_workspace?: boolean;
  all_coding_workspaces?: boolean;
  members?: unknown[];
}

function byKind(snapshots: WorkspaceSnapshot[]): Partial<Record<WorkspaceKind, WorkspaceSnapshot>> {
  const map: Partial<Record<WorkspaceKind, WorkspaceSnapshot>> = {};
  for (const s of snapshots) {
    if (s.kind !== 'needs_attention') map[s.kind] = s;
  }
  return map;
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

async function codingWorkspaceConnected(
  rootDir: string,
  ws: RegistryWorkspace,
): Promise<{ connected: boolean; empty: boolean; absPath: string }> {
  const rel = ws.path ?? '.';
  const absPath = path.isAbsolute(rel) ? rel : path.join(rootDir, rel);
  const exists = await pathExists(absPath);
  if (!exists) return { connected: false, empty: true, absPath };
  try {
    const entries = await fs.readdir(absPath);
    const useful = entries.filter((n) => n !== '.git' && n !== '.gitignore');
    return { connected: useful.length > 0, empty: useful.length === 0, absPath };
  } catch {
    return { connected: false, empty: true, absPath };
  }
}

async function synthesize(
  rootDir: string,
  prior: WorkspaceSnapshot[],
): Promise<{ findings: Finding[]; metrics: Record<string, number | string | boolean> }> {
  const findings: Finding[] = [];
  const map = byKind(prior);

  const teamPath = path.join(rootDir, 'config/teams/needs-attention.json');
  const team = await readJsonSafe<TeamDoc>(teamPath);
  if (!team?.id) {
    findings.push(
      makeFinding(ID, {
        title: 'Needs Attention team missing',
        detail: 'config/teams/needs-attention.json is missing or invalid.',
        severity: 'critical',
        category: 'wiring',
        suggestion: 'Restore team.needs-attention so triage agents can run across workspaces.',
        relatedNodeIds: ['ws-needs_attention', 'layer-attention'],
      }),
    );
  } else if (!team.cross_workspace || !team.all_coding_workspaces) {
    findings.push(
      makeFinding(ID, {
        title: 'Needs Attention team not cross-workspace',
        detail: 'Team must set cross_workspace and all_coding_workspaces true.',
        severity: 'high',
        category: 'wiring',
        suggestion: 'Enable cross-workspace connectivity on team.needs-attention.',
        relatedNodeIds: ['ws-needs_attention'],
      }),
    );
  }

  const scriptPath = path.join(rootDir, 'scripts/needs-attention.py');
  if (!(await pathExists(scriptPath))) {
    findings.push(
      makeFinding(ID, {
        title: 'Needs Attention triage script missing',
        detail: 'scripts/needs-attention.py not found.',
        severity: 'high',
        category: 'wiring',
        suggestion: 'Restore scripts/needs-attention.py for registry-wide attention sweeps.',
      }),
    );
  }

  const regPath = path.join(rootDir, 'config/workspaces/registry.json');
  const reg = await readJsonSafe<RegistryDoc>(regPath);
  // Prefer full flat workspaces list so sgr/litserve/etc. are included
  const coding =
    (reg?.workspaces && reg.workspaces.length > 0
      ? reg.workspaces
      : reg?.layers?.coding_workspaces) ?? [];
  let connected = 0;
  let missing = 0;
  let empty = 0;

  for (const ws of coding) {
    if (!ws.id) continue;
    const state = await codingWorkspaceConnected(rootDir, ws);
    if (state.connected) {
      connected += 1;
    } else if (state.empty && (await pathExists(state.absPath))) {
      empty += 1;
      findings.push(
        makeFinding(ID, {
          title: `Empty coding workspace: ${ws.id}`,
          detail: `${ws.label ?? ws.id} at ${ws.path ?? '.'} has no checkout content (often an uninitialized submodule).`,
          severity: ws.primary ? 'high' : 'medium',
          category: 'connectivity',
          suggestion: ws.remote
            ? `Init or clone ${ws.remote} into ${ws.path ?? '.'}, then re-run needs-attention connect.`
            : `Populate ${ws.path ?? '.'} or mark the workspace optional in the registry.`,
          relatedNodeIds: ['ws-needs_attention', 'layer-attention'],
        }),
      );
    } else {
      missing += 1;
      findings.push(
        makeFinding(ID, {
          title: `Disconnected coding workspace: ${ws.id}`,
          detail: `Path ${ws.path ?? '.'} is missing under the Cam checkout.`,
          severity: 'high',
          category: 'connectivity',
          suggestion: `Connect workspace ${ws.id} so attention dispatch can route coding work there.`,
          relatedNodeIds: ['ws-needs_attention'],
        }),
      );
    }
  }

  if (coding.length === 0) {
    findings.push(
      makeFinding(ID, {
        title: 'No coding workspaces in registry',
        detail: 'config/workspaces/registry.json has no coding_workspaces / workspaces list.',
        severity: 'critical',
        category: 'connectivity',
        suggestion: 'Restore layers.coding_workspaces so agents can connect to all targets.',
      }),
    );
  }

  // Pull urgent findings from other scan workspaces into the attention queue
  for (const snap of prior) {
    if (snap.kind === 'needs_attention') continue;
    const urgent = snap.findings.filter(
      (f) => severityRank(f.severity) >= severityRank('high'),
    );
    for (const f of urgent.slice(0, 3)) {
      findings.push(
        makeFinding(ID, {
          title: `Attention: ${f.title}`,
          detail: `From ${snap.name}: ${f.detail}`,
          severity: f.severity,
          category: 'queue',
          suggestion:
            f.suggestion ??
            `Triage in ${snap.name}; auto-dispatch via team.needs-attention when Aaron-gated steps are not required.`,
          relatedNodeIds: [snap.id, f.id, 'ws-needs_attention'],
        }),
      );
    }
    if (snap.score < 50) {
      findings.push(
        makeFinding(ID, {
          title: `Weak workspace needs attention: ${snap.name}`,
          detail: `Score ${snap.score} with ${snap.findings.length} finding(s).`,
          severity: snap.score < 30 ? 'critical' : 'high',
          category: 'queue',
          suggestion: `Arm issue loop / attention dispatcher against ${snap.kind}; escalate only kill/enhance/outbound.`,
          relatedNodeIds: [snap.id, 'ws-needs_attention', 'agent-attention-dispatcher'],
        }),
      );
    }
  }

  const improvements = map.improvements;
  if (improvements && improvements.findings.some((f) => f.category === 'priority')) {
    findings.push(
      makeFinding(ID, {
        title: 'Priority improvements waiting',
        detail: 'Improvement Engine flagged priority items that belong on the Needs Attention tab.',
        severity: 'medium',
        category: 'queue',
        suggestion: 'Run attention-triage then dispatch auto-clearable priorities across coding workspaces.',
        relatedNodeIds: [improvements.id, 'ws-needs_attention', 'agent-attention-triage'],
      }),
    );
  }

  if (findings.length === 0) {
    findings.push(
      makeFinding(ID, {
        title: 'Needs Attention queue clear',
        detail: `All ${connected} coding workspace(s) connected; no high-severity cross-workspace items.`,
        severity: 'info',
        category: 'status',
        suggestion: 'Keep daily needs-attention sweep armed; re-check after agent cycles.',
      }),
    );
  }

  const metrics: Record<string, number | string | boolean> = {
    codingWorkspaceCount: coding.length,
    connectedWorkspaces: connected,
    emptyWorkspaces: empty,
    missingWorkspaces: missing,
    priorCount: prior.length,
    queueDepth: findings.filter((f) => f.severity !== 'info').length,
    teamPresent: Boolean(team?.id),
    crossWorkspace: Boolean(team?.cross_workspace),
  };

  return { findings, metrics };
}

export const needsAttentionScanner: WorkspaceScanner & {
  scanWithPrior(rootDir: string, prior?: WorkspaceSnapshot[]): Promise<WorkspaceSnapshot>;
} = {
  id: ID,
  kind: KIND,

  async scan(rootDir: string): Promise<WorkspaceSnapshot> {
    return needsAttentionScanner.scanWithPrior(rootDir, []);
  },

  async scanWithPrior(rootDir: string, prior: WorkspaceSnapshot[] = []): Promise<WorkspaceSnapshot> {
    console.log('[needs-attention] surveying attention queue + coding workspaces…');
    const { findings, metrics } = await synthesize(rootDir, prior);
    const score = scoreFromFindings(findings);
    const status = statusFromScore(score);
    console.log(
      `[needs-attention] score=${score} queue=${metrics.queueDepth} connected=${metrics.connectedWorkspaces}/${metrics.codingWorkspaceCount}`,
    );
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
