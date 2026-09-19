/** HAAS→Cam privilege inheritance + lineage contracts (TypeScript runtime). */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

export const AARON_ONLY_PRIVILEGES = [
  'task_giver',
  'kill_master',
  'cam_enhance_apply',
  'revoke_standing_autonomy',
  'enroll_identity',
] as const;

export type AaronOnlyPrivilege = (typeof AARON_ONLY_PRIVILEGES)[number];

export const AGENT_GRANTABLE_PRIVILEGES = [
  'spawn_subagents',
  'assign_task',
  'broadcast',
  'resolve_task',
  'send_message',
  'terminate_lineage',
  'read_mesh',
  'write_mesh',
  'read_vault',
  'write_vault',
  'use_jarvis',
  'use_slm',
  'use_dl',
  'use_vision',
  'create_tool',
  'use_tool',
  'web_fetch',
  'cam_enhance_propose',
  'outbound_draft',
  'outbound_send',
  'careers_draft',
  'careers_submit',
] as const;

export type AgentPrivilege = (typeof AGENT_GRANTABLE_PRIVILEGES)[number];

export interface SwarmAgentNode {
  id: string;
  role: string;
  level: number;
  parentId: string | null;
  privileges: AgentPrivilege[];
  lineage: string[];
  status: 'active' | 'terminated';
  createdAt: string;
  terminatedAt?: string;
  terminateReason?: string;
  workspaceIds: string[];
}

export interface SwarmLineageState {
  version: 1;
  soleOperator: 'Aaron';
  agents: SwarmAgentNode[];
  events: SwarmBusEvent[];
  updatedAt: string;
}

export type SwarmPrimitiveOp =
  | 'synapse.spawn'
  | 'synapse.assign_task'
  | 'synapse.broadcast'
  | 'synapse.resolve_task'
  | 'synapse.send_message'
  | 'synapse.terminate_lineage'
  | 'denied';

export interface SwarmBusEvent {
  id: string;
  op: SwarmPrimitiveOp;
  from: string;
  to?: string;
  channel?: string;
  detail: string;
  at: string;
  workspaceIds: string[];
  ok: boolean;
}

export interface PrivilegeCatalog {
  privilege_catalog: {
    aaron_only: string[];
    agent_grantable: string[];
  };
  role_defaults: Record<string, { level: number | null; privileges: string[] }>;
  inheritance_rules: {
    spawn_one_level_below_only: boolean;
    unlimited_count: boolean;
    unlimited_depth: boolean;
    human_gate_to_spawn: boolean;
    cannot_escalate: boolean;
    cannot_grant_aaron_only: boolean;
  };
}

let cachedCatalog: PrivilegeCatalog | null = null;

const BUILTIN_CATALOG: PrivilegeCatalog = {
  privilege_catalog: {
    aaron_only: [...AARON_ONLY_PRIVILEGES],
    agent_grantable: [...AGENT_GRANTABLE_PRIVILEGES],
  },
  role_defaults: {
    chief: {
      level: 1,
      privileges: [
        'spawn_subagents',
        'assign_task',
        'broadcast',
        'resolve_task',
        'send_message',
        'terminate_lineage',
        'read_mesh',
        'write_mesh',
        'read_vault',
        'write_vault',
        'use_jarvis',
        'use_slm',
        'use_dl',
        'use_vision',
        'create_tool',
        'use_tool',
        'web_fetch',
        'cam_enhance_propose',
        'outbound_draft',
        'outbound_send',
        'careers_draft',
        'careers_submit',
      ],
    },
    'capability-broker': {
      level: 2,
      privileges: [
        'spawn_subagents',
        'assign_task',
        'broadcast',
        'resolve_task',
        'send_message',
        'terminate_lineage',
        'read_mesh',
        'write_mesh',
        'read_vault',
        'write_vault',
        'use_jarvis',
        'use_slm',
        'use_dl',
        'create_tool',
        'use_tool',
        'web_fetch',
        'cam_enhance_propose',
      ],
    },
    'task-executor': {
      level: 2,
      privileges: [
        'spawn_subagents',
        'assign_task',
        'send_message',
        'resolve_task',
        'read_mesh',
        'write_mesh',
        'read_vault',
        'write_vault',
        'use_jarvis',
        'use_slm',
        'use_dl',
        'use_tool',
      ],
    },
    'tool-creator': {
      level: 2,
      privileges: [
        'spawn_subagents',
        'assign_task',
        'send_message',
        'resolve_task',
        'read_mesh',
        'write_mesh',
        'read_vault',
        'write_vault',
        'create_tool',
        'use_tool',
        'use_jarvis',
        'use_slm',
        'cam_enhance_propose',
      ],
    },
    qa: {
      level: 2,
      privileges: [
        'spawn_subagents',
        'send_message',
        'resolve_task',
        'terminate_lineage',
        'read_mesh',
        'write_mesh',
        'read_vault',
      ],
    },
    default_subagent: {
      level: null,
      privileges: [
        'spawn_subagents',
        'send_message',
        'resolve_task',
        'read_mesh',
        'write_mesh',
        'use_tool',
      ],
    },
  },
  inheritance_rules: {
    spawn_one_level_below_only: true,
    unlimited_count: true,
    unlimited_depth: true,
    human_gate_to_spawn: false,
    cannot_escalate: true,
    cannot_grant_aaron_only: true,
  },
};

export function loadPrivilegeCatalog(rootDir: string = ROOT): PrivilegeCatalog {
  if (cachedCatalog && rootDir === ROOT) return cachedCatalog;
  const file = path.join(rootDir, 'config/swarm/privileges.json');
  try {
    const raw = JSON.parse(readFileSync(file, 'utf8')) as PrivilegeCatalog;
    if (rootDir === ROOT) cachedCatalog = raw;
    return raw;
  } catch {
    // Temp scan roots / partial checkouts — fall back to repo catalog, then builtin.
    try {
      const repoFile = path.join(ROOT, 'config/swarm/privileges.json');
      const raw = JSON.parse(readFileSync(repoFile, 'utf8')) as PrivilegeCatalog;
      return raw;
    } catch {
      return BUILTIN_CATALOG;
    }
  }
}

export function chiefPrivileges(catalog?: PrivilegeCatalog): AgentPrivilege[] {
  const cat = catalog ?? loadPrivilegeCatalog();
  return filterGrantable(cat.role_defaults.chief?.privileges ?? []);
}

export function filterGrantable(privs: string[]): AgentPrivilege[] {
  const grantable = new Set<string>(AGENT_GRANTABLE_PRIVILEGES);
  return privs.filter((p): p is AgentPrivilege => grantable.has(p));
}

export class PrivilegeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PrivilegeError';
  }
}

export function spawnChild(input: {
  parent: SwarmAgentNode;
  role: string;
  requested?: string[] | null;
  catalog?: PrivilegeCatalog;
  workspaceIds?: string[];
  now?: string;
}): SwarmAgentNode {
  const catalog = input.catalog ?? loadPrivilegeCatalog();
  const aaronOnly = new Set(catalog.privilege_catalog.aaron_only);
  const grantable = new Set(catalog.privilege_catalog.agent_grantable);
  const parentPrivs = new Set(input.parent.privileges);
  const defaults =
    catalog.role_defaults[input.role] ?? catalog.role_defaults.default_subagent;
  const base = new Set(
    input.requested != null ? input.requested : (defaults?.privileges ?? []),
  );

  const illegal = [...base].filter((p) => aaronOnly.has(p));
  if (illegal.length) {
    throw new PrivilegeError(`cannot grant aaron_only privileges: ${illegal.sort().join(', ')}`);
  }
  const unknown = [...base].filter((p) => !grantable.has(p) && !aaronOnly.has(p));
  if (unknown.length) {
    throw new PrivilegeError(`unknown privileges: ${unknown.sort().join(', ')}`);
  }
  const escalation = [...base].filter((p) => !parentPrivs.has(p as AgentPrivilege));
  if (escalation.length) {
    throw new PrivilegeError(
      `privilege escalation blocked: child wants ${escalation.sort().join(', ')}`,
    );
  }
  if (!catalog.inheritance_rules.spawn_one_level_below_only) {
    throw new PrivilegeError('misconfigured: spawn_one_level_below_only must be true');
  }
  if (!input.parent.privileges.includes('spawn_subagents')) {
    throw new PrivilegeError('parent lacks spawn_subagents privilege');
  }
  if (input.parent.status !== 'active') {
    throw new PrivilegeError('cannot spawn from terminated parent');
  }

  const now = input.now ?? new Date().toISOString();
  const level = input.parent.level + 1;
  return {
    id: `${input.parent.id}/${input.role}@${level}`,
    role: input.role,
    level,
    parentId: input.parent.id,
    privileges: filterGrantable([...base]),
    lineage: [...input.parent.lineage, input.parent.id],
    status: 'active',
    createdAt: now,
    workspaceIds: unique([...(input.workspaceIds ?? []), ...input.parent.workspaceIds]),
  };
}

export function mayTerminate(
  caller: SwarmAgentNode | { id: 'Aaron'; isAaron: true },
  target: SwarmAgentNode,
): boolean {
  if ('isAaron' in caller && caller.isAaron) return true;
  const agent = caller as SwarmAgentNode;
  if (agent.status !== 'active') return false;
  if (!agent.privileges.includes('terminate_lineage')) return false;
  if (target.parentId === agent.id) return true;
  return target.lineage.includes(agent.id);
}

export function createChiefNode(catalog?: PrivilegeCatalog, now?: string): SwarmAgentNode {
  const cat = catalog ?? loadPrivilegeCatalog();
  return {
    id: 'agent.chief',
    role: 'chief',
    level: 1,
    parentId: null,
    privileges: chiefPrivileges(cat),
    lineage: [],
    status: 'active',
    createdAt: now ?? new Date().toISOString(),
    workspaceIds: ['workspace-all'],
  };
}

export function emptyLineageState(now?: string): SwarmLineageState {
  const at = now ?? new Date().toISOString();
  return {
    version: 1,
    soleOperator: 'Aaron',
    agents: [createChiefNode(undefined, at)],
    events: [],
    updatedAt: at,
  };
}

/** Mesh namespace keys shared across all agents and workspaces. */
export const SWARM_MESH_NAMESPACES = [
  'mesh/agent-lineage',
  'mesh/tools',
  'mesh/agent-commute',
  'mesh/agent-memory',
  'mesh/agent-persistence',
  'mesh/agent-issue-loop',
  'mesh/swarm/bus',
  'mesh/swarm/privileges',
] as const;

export type SwarmMeshNamespace = (typeof SWARM_MESH_NAMESPACES)[number];

function unique(values: string[]): string[] {
  return [...new Set(values)];
}
