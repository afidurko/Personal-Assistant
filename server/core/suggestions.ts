import type {
  Finding,
  Severity,
  WorkspaceSnapshot,
  SuggestiveImplementation,
  SuggestionKind,
  LoopJob,
  AgentCycleResult,
} from '../../shared/types.js';
import { SWIFT_GUIDE_CONCEPTS } from '../../shared/swiftGuide.js';
import { AGENT_LAYERS, MESH_AGENTS } from '../../shared/agentLayers.js';

export type { SuggestiveImplementation, SuggestionKind };

const SEVERITY_PRIORITY: Record<Severity, number> = {
  critical: 95,
  high: 80,
  medium: 60,
  low: 35,
  info: 15,
};

export interface SuggestionContext {
  loopJobs?: LoopJob[];
  lastAgentCycle?: AgentCycleResult | null;
}

/**
 * Turn live workspace findings into actionable, suggestive implementations
 * that mesh with Swift Guide concepts and deep agent layers.
 */
export function buildSuggestiveImplementations(
  workspaces: WorkspaceSnapshot[],
  context: SuggestionContext = {},
): SuggestiveImplementation[] {
  const out: SuggestiveImplementation[] = [];

  for (const ws of workspaces) {
    for (const finding of ws.findings) {
      out.push(fromFinding(ws, finding));
    }

    if (ws.kind === 'vulnerability' && ws.score < 90) {
      out.push({
        id: `suggest-${ws.id}-harden`,
        kind: 'security',
        title: 'Schedule a hardening pass',
        rationale: `Vulnerability score is ${ws.score}; residual risk remains.`,
        implementation:
          'Run offline heuristics weekly, add CI `npm audit` on a schedule, and rotate any flagged secrets.',
        sketch: 'npm audit --omit=dev\n# + secret scan in CI',
        priority: 70,
        relatedWorkspaceIds: [ws.id],
        relatedConceptIds: ['error-handling', 'protocols-extensions'],
        sourceFindingIds: [],
      });
    }

    if (ws.kind === 'architecture' && Number(ws.metrics.deepImportHits ?? 0) > 0) {
      out.push({
        id: `suggest-${ws.id}-aliases`,
        kind: 'architecture',
        title: 'Flatten deep relative imports',
        rationale: `${ws.metrics.deepImportHits} deep import hit(s) increase coupling.`,
        implementation:
          'Prefer `@/` and `@shared/` path aliases for cross-layer imports instead of long `../../../` chains.',
        sketch: "import { STATUS_COLORS } from '@shared/types';",
        priority: 55,
        relatedWorkspaceIds: [ws.id],
        relatedConceptIds: ['objects-classes', 'protocols-extensions'],
        sourceFindingIds: [],
      });
    }

    if (ws.kind === 'health' && ws.score < 100) {
      out.push({
        id: `suggest-${ws.id}-vitals`,
        kind: 'ops',
        title: 'Stabilize system vitals',
        rationale: `Health score ${ws.score} — readiness or resource pressure detected.`,
        implementation:
          'Keep continuous scan enabled, watch MemoryRail for repeating critical breadcrumbs, and free disk/memory pressure first.',
        priority: 75,
        relatedWorkspaceIds: [ws.id],
        relatedConceptIds: ['concurrency', 'simple-values'],
        sourceFindingIds: [],
      });
    }
  }

  const weakest = [...workspaces].sort((a, b) => a.score - b.score)[0];
  if (weakest) {
    const concept =
      SWIFT_GUIDE_CONCEPTS.find((c) => c.relatedWorkspaceKinds.includes(weakest.kind)) ??
      SWIFT_GUIDE_CONCEPTS[0];
    out.push({
      id: `suggest-learn-${weakest.kind}`,
      kind: 'learning',
      title: `Swift Guide: study ${concept.title}`,
      rationale: `${weakest.name} is the weakest workspace (score ${weakest.score}); related language concepts speed diagnosis.`,
      implementation: `Open the Swift Guide tour at “${concept.title}”, then jump to the ${weakest.name} workspace chip.`,
      sketch: concept.sample,
      priority: 40 + Math.round((100 - weakest.score) / 5),
      relatedWorkspaceIds: [weakest.id],
      relatedConceptIds: [concept.id],
      sourceFindingIds: [],
    });

    const commuteAgent =
      MESH_AGENTS.find(
        (a) => a.layer === 'commute' && a.relatedWorkspaceKinds.includes(weakest.kind),
      ) ?? MESH_AGENTS.find((a) => a.id === 'commute-router')!;
    out.push({
      id: `suggest-commute-${weakest.kind}`,
      kind: 'agent-commute',
      title: `Commute via ${commuteAgent.name}`,
      rationale: `Weakest workspace ${weakest.name} should take the shortest high-confidence agent hop.`,
      implementation: `Focus hex node “${commuteAgent.name}”, then Run agent cycle so commute paths reinforce ${weakest.kind} → agent edges.`,
      sketch: `POST /api/agents/cycle\n# focus agent-${commuteAgent.id}`,
      priority: 50 + Math.round((100 - weakest.score) / 4),
      relatedWorkspaceIds: [weakest.id],
      relatedConceptIds: [],
      sourceFindingIds: [],
    });
  }

  out.push(...fromAgentContext(workspaces, context));

  const byId = new Map<string, SuggestiveImplementation>();
  for (const s of out) {
    const prev = byId.get(s.id);
    if (!prev || s.priority > prev.priority) byId.set(s.id, s);
  }

  return [...byId.values()].sort((a, b) => b.priority - a.priority);
}

function fromAgentContext(
  workspaces: WorkspaceSnapshot[],
  context: SuggestionContext,
): SuggestiveImplementation[] {
  const out: SuggestiveImplementation[] = [];
  const jobs = context.loopJobs ?? [];
  const cycle = context.lastAgentCycle;

  const escalated = jobs.filter((j) => j.status === 'escalated');
  if (escalated.length > 0) {
    const job = escalated[0];
    out.push({
      id: `suggest-loop-escalate-${job.id}`,
      kind: 'agent-repair',
      title: `Escalate issue-loop: ${shorten(job.title, 48)}`,
      rationale: `Issue-fix loop exhausted ${job.attempts}/${job.maxAttempts} attempts.`,
      implementation:
        job.fixSketch ??
        'Open the Issue-fix loop panel, review the escalated job, and apply the fix sketch manually or with a subagent.',
      sketch: job.fixSketch,
      priority: 92,
      relatedWorkspaceIds: job.sourceWorkspaceId ? [job.sourceWorkspaceId] : [],
      relatedConceptIds: ['error-handling'],
      sourceFindingIds: job.sourceFindingId ? [job.sourceFindingId] : [],
    });
  }

  const queued = jobs.filter((j) => j.status === 'queued' || j.status === 'running');
  if (queued.length >= 3) {
    out.push({
      id: 'suggest-persistence-batch',
      kind: 'agent-persistence',
      title: 'Batch sticky jobs through persistence layer',
      rationale: `${queued.length} open loop jobs — Completion Guardian should gate closes until fixed.`,
      implementation:
        'Keep issue loop armed; run agent cycle so Job Persistence re-queues stalled work before starting new scans.',
      sketch: 'POST /api/agents/issue-loop/start\nPOST /api/agents/cycle',
      priority: 68,
      relatedWorkspaceIds: [
        ...new Set(queued.map((j) => j.sourceWorkspaceId).filter(Boolean) as string[]),
      ],
      relatedConceptIds: ['concurrency'],
      sourceFindingIds: [],
    });
  }

  if (cycle && cycle.efficiencyGain < 0.25 && workspaces.some((w) => w.score < 85)) {
    const layer = AGENT_LAYERS.find((l) => l.id === 'commute')!;
    out.push({
      id: 'suggest-commute-efficiency',
      kind: 'agent-commute',
      title: 'Raise commute efficiency',
      rationale: `Last agent cycle efficiency was ${Math.round(cycle.efficiencyGain * 100)}% with weak workspace scores.`,
      implementation: `Focus layer hub “${layer.name}”, reinforce commute edges, then re-run agent cycle.`,
      sketch: 'POST /api/agents/cycle',
      priority: 58,
      relatedWorkspaceIds: workspaces.filter((w) => w.score < 85).map((w) => w.id),
      relatedConceptIds: [],
      sourceFindingIds: [],
    });
  }

  if (cycle && cycle.memoryWrites === 0) {
    out.push({
      id: 'suggest-memory-consolidate',
      kind: 'agent-memory',
      title: 'Trigger memory consolidation',
      rationale: 'Agent cycle wrote no memory promotions — recall will stay cold.',
      implementation:
        'Ensure workspaces have findings or open jobs, then run agent cycle so Memory Consolidator / Recall Amplifier fire.',
      sketch: 'POST /api/agents/cycle',
      priority: 45,
      relatedWorkspaceIds: workspaces.map((w) => w.id).slice(0, 3),
      relatedConceptIds: ['simple-values'],
      sourceFindingIds: [],
    });
  }

  if (cycle?.swarm && cycle.swarm.denials > 0) {
    out.push({
      id: 'suggest-swarm-privilege-ok',
      kind: 'swarm-privilege',
      title: 'Privilege broker blocked escalations',
      rationale: `Swarm cycle denied ${cycle.swarm.denials} illegal privilege grant(s) — inheritance is active across agents.`,
      implementation:
        'Keep config/swarm/privileges.json loaded; focus Privilege Broker hex and confirm aaron_only never lands on agents.',
      sketch: 'python3 scripts/swarm-check.py\nPOST /api/agents/cycle',
      priority: 42,
      relatedWorkspaceIds: workspaces.filter((w) => w.kind === 'swarm').map((w) => w.id),
      relatedConceptIds: [],
      sourceFindingIds: [],
    });
  }

  if (cycle?.swarm && cycle.swarm.activeAgents > 0) {
    out.push({
      id: 'suggest-swarm-lineage-memory',
      kind: 'swarm-lineage',
      title: 'Persist swarm lineage across workspaces',
      rationale: `${cycle.swarm.activeAgents} active swarm agents; namespaces ${cycle.swarm.namespacesTouched.slice(0, 3).join(', ')}…`,
      implementation:
        'Export persistence bundle so mesh/agent-lineage + mesh/swarm/* travel to future workspaces; run swarm-check after import.',
      sketch: 'python3 scripts/persist-export.py --out /tmp/cam.zip',
      priority: 48,
      relatedWorkspaceIds: workspaces.map((w) => w.id),
      relatedConceptIds: [],
      sourceFindingIds: [],
    });
  }

  const swarmWs = workspaces.find((w) => w.kind === 'swarm');
  if (swarmWs && swarmWs.score < 90) {
    out.push({
      id: 'suggest-swarm-tooling',
      kind: 'swarm-tooling',
      title: 'Harden tooling team + tool registry',
      rationale: `Swarm Mesh score ${swarmWs.score} — privilege/bus/tooling wiring needs attention.`,
      implementation:
        'Restore team.tooling, config/tools/registry.json, and center.tooling; re-run swarm scanner.',
      sketch: 'python3 scripts/swarm-check.py\nnpm run scan',
      priority: 72,
      relatedWorkspaceIds: [swarmWs.id],
      relatedConceptIds: [],
      sourceFindingIds: swarmWs.findings.map((f) => f.id).slice(0, 5),
    });
  }

  const agiWs = workspaces.find((w) => w.kind === 'agi_research');
  if (agiWs) {
    out.push({
      id: 'suggest-cam-hmo-mmp',
      kind: 'research-memory',
      title: 'Keep HMO tiers + MMP claims hot during research scans',
      rationale:
        'AGI / Cam-function research writes must stay lean in primary memory and remix via claim schema.',
      implementation:
        'Pack distillates with scripts/pack-mesh-claim.py; verify tiers via scripts/memory-tier-check.py before promoting to mesh/facts.',
      sketch:
        'python3 scripts/pack-mesh-claim.py --claim "…" --role agi-scout --source "title|url"\npython3 scripts/memory-tier-check.py',
      priority: agiWs.score < 85 ? 74 : 52,
      relatedWorkspaceIds: [agiWs.id],
      relatedConceptIds: ['simple-values'],
      sourceFindingIds: agiWs.findings.map((f) => f.id).slice(0, 3),
    });
    out.push({
      id: 'suggest-cam-trajectory-gate',
      kind: 'cam-enhance',
      title: 'Re-verify OCL/CPV trajectory gates after enhance batches',
      rationale:
        'Enhancement applies must not leak motor.enhance without Aaron or compose with jobs.',
      implementation:
        'Run trajectory-policy-check and trajectory-billion-fuzz before merge; keep switch.cam_enhance default hold.',
      sketch:
        'python3 scripts/trajectory-policy-check.py\npython3 scripts/trajectory-billion-fuzz.py --n 1000000000',
      priority: 70,
      relatedWorkspaceIds: [agiWs.id],
      relatedConceptIds: ['error-handling', 'protocols-extensions'],
      sourceFindingIds: [],
    });
  }

  out.push({
    id: 'suggest-aaron-voice-only-gate',
    kind: 'identity',
    title: 'Keep Aaron-only voice gate enrolled before live mic',
    rationale:
      'Surrounding speakers must not create Cam turns — enroll FunASR CAM++ templates and fail closed until ready.',
    implementation:
      'Record Aaron-only WAVs, run aaron-voice-enroll.py, verify with aaron-voice-verify.py and aaron-voice-billion-fuzz before merging presence changes.',
    sketch:
      'python3 scripts/aaron-voice-enroll.py identity/aaron/local/voice/samples/*.wav\npython3 scripts/aaron-voice-billion-fuzz.py --n 1000000000\npython3 scripts/cam-converse-server.py',
    priority: 82,
    relatedWorkspaceIds: workspaces.map((w) => w.id).slice(0, 3),
    relatedConceptIds: ['error-handling', 'protocols-extensions'],
    sourceFindingIds: [],
  });

  const critical = workspaces.flatMap((w) => w.findings.filter((f) => f.severity === 'critical'));
  if (critical.length > 0) {
    const fixer = MESH_AGENTS.find((a) => a.id === 'issue-fix-loop')!;
    out.push({
      id: 'suggest-arm-issue-loop',
      kind: 'agent-repair',
      title: 'Arm automated issue-fix loop',
      rationale: `${critical.length} critical finding(s) — ${fixer.name} should loop detect→fix→verify.`,
      implementation: `Arm the issue loop, focus hex “${fixer.name}”, and let scan cycles drive autonomous attempts.`,
      sketch: 'POST /api/agents/issue-loop/start\nPOST /api/scan',
      priority: 88,
      relatedWorkspaceIds: [...new Set(critical.map((f) => f.workspaceId))],
      relatedConceptIds: ['error-handling'],
      sourceFindingIds: critical.map((f) => f.id).slice(0, 5),
    });
  }

  return out;
}

function fromFinding(ws: WorkspaceSnapshot, finding: Finding): SuggestiveImplementation {
  const kind = mapKind(ws.kind, finding.category);
  const conceptIds = SWIFT_GUIDE_CONCEPTS.filter((c) =>
    c.relatedWorkspaceKinds.includes(ws.kind),
  ).map((c) => c.id);

  return {
    id: `suggest-finding-${finding.id}`,
    kind,
    title: finding.suggestion ? shorten(finding.suggestion, 72) : finding.title,
    rationale: `${finding.title}: ${finding.detail}`,
    implementation:
      finding.suggestion ??
      `Inspect ${ws.name} finding “${finding.title}” and apply the recommended remediation in that workspace panel.`,
    sketch: sketchFor(finding),
    priority: SEVERITY_PRIORITY[finding.severity] ?? 20,
    relatedWorkspaceIds: [ws.id],
    relatedConceptIds: conceptIds.slice(0, 2),
    sourceFindingIds: [finding.id],
  };
}

function mapKind(wsKind: WorkspaceSnapshot['kind'], category: string): SuggestionKind {
  if (wsKind === 'vulnerability' || category.includes('secret') || category.includes('cors')) {
    return 'security';
  }
  if (wsKind === 'architecture' || category.includes('structure')) return 'architecture';
  if (wsKind === 'updates' || category.includes('supply')) return 'dependency';
  if (wsKind === 'health') return 'ops';
  if (category.includes('priority') || category.includes('action')) return 'dx';
  return 'dx';
}

function shorten(text: string, max: number): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function sketchFor(finding: Finding): string | undefined {
  const t = `${finding.title} ${finding.detail}`.toLowerCase();
  if (t.includes('lockfile')) return 'npm install --package-lock-only && git add package-lock.json';
  if (t.includes('engines')) return '"engines": { "node": ">=20" }';
  if (t.includes('cors')) return "app.use(cors({ origin: process.env.APP_ORIGIN }))";
  if (t.includes('secret') || t.includes('api_key')) {
    return 'export API_KEY=…  # never commit literals';
  }
  if (t.includes('test')) return 'npm test -- --run';
  if (t.includes('loop') || t.includes('regress')) {
    return 'POST /api/agents/issue-loop/start && POST /api/agents/cycle';
  }
  return undefined;
}
