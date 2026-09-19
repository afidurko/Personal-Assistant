import path from 'node:path';
import { WORKSPACE_META, STATUS_COLORS } from '../../shared/types.js';
import type { Finding, WorkspaceSnapshot } from '../../shared/types.js';
import type { WorkspaceScanner } from './types.js';
import {
  makeFinding,
  now,
  pulseFromScore,
  readJsonSafe,
  readTextSafe,
  scoreFromFindings,
  statusFromScore,
} from './utils.js';

const KIND = 'swarm' as const;
const ID = 'workspace-swarm';
const META = WORKSPACE_META[KIND];

interface PrivilegeDoc {
  privilege_catalog?: { aaron_only?: string[]; agent_grantable?: string[] };
  inheritance_rules?: {
    unlimited_count?: boolean;
    unlimited_depth?: boolean;
    spawn_one_level_below_only?: boolean;
    cannot_escalate?: boolean;
  };
  role_defaults?: Record<string, { privileges?: string[] }>;
}

interface CentersDoc {
  recursion?: {
    privilege_inheritance?: boolean;
    lineage_terminate?: boolean;
    unlimited?: boolean;
  };
  teams?: string[];
  centers?: Array<{ id?: string }>;
}

interface MeshNamespaces {
  'mesh/agent-lineage'?: { activeAgents?: number; privilegeInheritance?: boolean };
  'mesh/swarm/privileges'?: { aaronOnlyNeverGranted?: boolean; crossWorkspace?: boolean };
  'mesh/tools'?: { registry?: string };
}

/**
 * Swarm Mesh workspace — privilege inheritance, lineage, and boss/worker bus
 * shared across every agent and scan workspace.
 */
export const swarmScanner: WorkspaceScanner = {
  id: ID,
  kind: KIND,

  async scan(rootDir: string): Promise<WorkspaceSnapshot> {
    console.log('[swarm] checking privilege/lineage/bus wiring across agents…');
    const findings: Finding[] = [];

    const privPath = path.join(rootDir, 'config/swarm/privileges.json');
    const primPath = path.join(rootDir, 'config/swarm/primitives.json');
    const triadPath = path.join(rootDir, 'config/swarm/autonomy-triad.json');
    const toolingPath = path.join(rootDir, 'config/teams/tooling.json');
    const toolsPath = path.join(rootDir, 'config/tools/registry.json');
    const grantPath = path.join(rootDir, 'identity/persistence/HAAS_CAM_PATTERNS.md');
    const scriptPath = path.join(rootDir, 'scripts/swarm-check.py');
    const centersPath = path.join(rootDir, 'config/connectome/centers.json');
    const seedPath = path.join(rootDir, 'identity/persistence/mesh-seed.json');
    const mirrorPath = path.join(rootDir, 'data/mesh-namespaces.json');
    const lineagePath = path.join(rootDir, 'data/swarm-lineage.json');

    const privileges = await readJsonSafe<PrivilegeDoc>(privPath);
    if (!privileges) {
      findings.push(
        makeFinding(ID, {
          title: 'Swarm privilege catalog missing',
          detail: 'config/swarm/privileges.json missing or invalid.',
          severity: 'critical',
          category: 'wiring',
          suggestion: 'Restore config/swarm/privileges.json from HAAS→Cam patterns.',
        }),
      );
    } else {
      const rules = privileges.inheritance_rules ?? {};
      if (!rules.unlimited_count || !rules.unlimited_depth) {
        findings.push(
          makeFinding(ID, {
            title: 'Unlimited spawn flags missing',
            detail: 'Privilege catalog must keep unlimited_count and unlimited_depth true.',
            severity: 'high',
            category: 'authority',
            suggestion: 'Set inheritance_rules.unlimited_* true (privilege inheritance ≠ count cap).',
          }),
        );
      }
      if (!rules.cannot_escalate || !rules.spawn_one_level_below_only) {
        findings.push(
          makeFinding(ID, {
            title: 'Privilege inheritance incomplete',
            detail: 'cannot_escalate / spawn_one_level_below_only must be true.',
            severity: 'high',
            category: 'security',
            suggestion: 'Restore HAAS→Cam inheritance rules in privileges.json.',
          }),
        );
      }
      const aaronOnly = new Set(privileges.privilege_catalog?.aaron_only ?? []);
      for (const [role, spec] of Object.entries(privileges.role_defaults ?? {})) {
        const overlap = (spec.privileges ?? []).filter((p) => aaronOnly.has(p));
        if (overlap.length) {
          findings.push(
            makeFinding(ID, {
              title: `Role ${role} has aaron_only privileges`,
              detail: overlap.join(', '),
              severity: 'critical',
              category: 'security',
              suggestion: 'Strip aaron_only privileges from all agent role_defaults.',
            }),
          );
        }
      }
    }

    if (!(await readJsonSafe(primPath))) {
      findings.push(
        makeFinding(ID, {
          title: 'Boss/worker primitives missing',
          detail: 'config/swarm/primitives.json missing.',
          severity: 'critical',
          category: 'wiring',
          suggestion: 'Restore synapse assign/broadcast/resolve/spawn/terminate contracts.',
        }),
      );
    }

    if (!(await readJsonSafe(triadPath))) {
      findings.push(
        makeFinding(ID, {
          title: 'Autonomy triad config missing',
          detail: 'config/swarm/autonomy-triad.json missing.',
          severity: 'medium',
          category: 'wiring',
          suggestion: 'Restore autonomy triad under Aaron governance.',
        }),
      );
    }

    if (!(await readJsonSafe(toolingPath))) {
      findings.push(
        makeFinding(ID, {
          title: 'Tooling team missing',
          detail: 'config/teams/tooling.json missing.',
          severity: 'high',
          category: 'wiring',
          suggestion: 'Restore team.tooling for tool-creator → tool-user.',
        }),
      );
    }

    if (!(await readJsonSafe(toolsPath))) {
      findings.push(
        makeFinding(ID, {
          title: 'Tool registry missing',
          detail: 'config/tools/registry.json missing.',
          severity: 'medium',
          category: 'wiring',
          suggestion: 'Restore config/tools/registry.json.',
        }),
      );
    }

    if (!(await readTextSafe(grantPath))) {
      findings.push(
        makeFinding(ID, {
          title: 'HAAS→Cam persistence grant missing',
          detail: 'identity/persistence/HAAS_CAM_PATTERNS.md not found.',
          severity: 'high',
          category: 'authority',
          suggestion: 'Restore standing grant so future workspaces inherit swarm contracts.',
        }),
      );
    }

    if (!(await readTextSafe(scriptPath))) {
      findings.push(
        makeFinding(ID, {
          title: 'swarm-check.py missing',
          detail: 'scripts/swarm-check.py not found.',
          severity: 'high',
          category: 'wiring',
          suggestion: 'Restore scripts/swarm-check.py validator.',
        }),
      );
    }

    const centers = await readJsonSafe<CentersDoc>(centersPath);
    if (!centers?.recursion?.privilege_inheritance || !centers.recursion.lineage_terminate) {
      findings.push(
        makeFinding(ID, {
          title: 'Connectome recursion missing swarm flags',
          detail: 'centers.recursion must set privilege_inheritance and lineage_terminate.',
          severity: 'high',
          category: 'wiring',
          suggestion: 'Update config/connectome/centers.json recursion block.',
        }),
      );
    }
    if (!centers?.teams?.includes('team.tooling')) {
      findings.push(
        makeFinding(ID, {
          title: 'team.tooling not registered in centers',
          detail: 'centers.teams should include team.tooling.',
          severity: 'medium',
          category: 'wiring',
          suggestion: 'Add team.tooling to centers.json teams list.',
        }),
      );
    }
    if (!centers?.centers?.some((c) => c.id === 'center.tooling')) {
      findings.push(
        makeFinding(ID, {
          title: 'center.tooling missing',
          detail: 'Connectome lacks center.tooling.',
          severity: 'high',
          category: 'wiring',
          suggestion: 'Add center.tooling to centers.json.',
        }),
      );
    }

    const seed = await readJsonSafe<Record<string, Record<string, unknown>>>(seedPath);
    const prefs = seed?.['mesh/prefs'] ?? {};
    const facts = seed?.['mesh/facts'] ?? {};
    if (!prefs.privilege_inheritance && !facts.privilege_inheritance) {
      findings.push(
        makeFinding(ID, {
          title: 'Mesh seed missing privilege_inheritance',
          detail: 'identity/persistence/mesh-seed.json should flag privilege_inheritance for all workspaces.',
          severity: 'medium',
          category: 'persistence',
          suggestion: 'Seed mesh/prefs + mesh/facts with HAAS→Cam flags.',
        }),
      );
    }

    const mirror = await readJsonSafe<MeshNamespaces>(mirrorPath);
    const lineage = await readJsonSafe<{ agents?: unknown[] }>(lineagePath);
    const activeAgents = mirror?.['mesh/agent-lineage']?.activeAgents ?? lineage?.agents?.length ?? 0;

    if (mirror && mirror['mesh/swarm/privileges']?.aaronOnlyNeverGranted === false) {
      findings.push(
        makeFinding(ID, {
          title: 'Namespace mirror allows aaron_only grants',
          detail: 'mesh/swarm/privileges.aaronOnlyNeverGranted is false.',
          severity: 'critical',
          category: 'security',
          suggestion: 'Rebuild mesh-namespaces.json via a swarm agent cycle.',
        }),
      );
    }

    const score = scoreFromFindings(findings);
    const status = statusFromScore(score);

    return {
      id: ID,
      kind: KIND,
      name: META.name,
      description: META.description,
      status,
      score,
      lastScanAt: now(),
      findings,
      metrics: {
        privilegeCatalog: Boolean(privileges),
        toolingTeam: Boolean(await readJsonSafe(toolingPath)),
        centerTooling: Boolean(centers?.centers?.some((c) => c.id === 'center.tooling')),
        privilegeInheritance: Boolean(centers?.recursion?.privilege_inheritance),
        lineageTerminate: Boolean(centers?.recursion?.lineage_terminate),
        meshMirrorPresent: Boolean(mirror),
        activeAgents,
        crossWorkspace: Boolean(mirror?.['mesh/swarm/privileges']?.crossWorkspace ?? prefs.haas_cam_patterns),
      },
      color: STATUS_COLORS[status] ?? META.defaultColor,
      pulse: pulseFromScore(score),
    };
  },
};
