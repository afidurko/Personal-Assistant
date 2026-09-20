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

  const improvementsWs = workspaces.find((w) => w.kind === 'improvements');
  const toolingRelated = swarmWs ?? improvementsWs;
  if (toolingRelated) {
    out.push({
      id: 'suggest-public-apis-catalog',
      kind: 'api-catalog',
      title: 'Discover free APIs via public-apis before inventing endpoints',
      rationale:
        'All Cam agents share motor.public_apis — catalog hits beat ad-hoc URL invention for thin wrappers.',
      implementation:
        'Search scripts/public-apis-search.py (or MCP public_apis_search), pack into mesh/tools, then register a thin tool if reuse is likely.',
      sketch:
        'python3 scripts/public-apis-search.py --query weather --num 8\npython3 scripts/public-apis-addon.py call weather.open_meteo --latitude 40.7 --longitude -74.0 --offline',
      priority: toolingRelated.score < 85 ? 66 : 48,
      relatedWorkspaceIds: [toolingRelated.id],
      relatedConceptIds: ['protocols-extensions'],
      sourceFindingIds: toolingRelated.findings.map((f) => f.id).slice(0, 3),
    });
    out.push({
      id: 'suggest-card-embodiment-ip-safe',
      kind: 'card-embodiment',
      title: 'Spawn IP-safe procedural 3D champions after card detect',
      rationale:
        'Joshinator embodiment must stay original/procedural — never ship franchise character meshes or logos.',
      implementation:
        'Resolve via integrations/joshinator-analyzer embodiment_service; fuzz with scripts/embodiment-billion-fuzz.py before merge.',
      sketch:
        'PYTHONPATH=integrations/joshinator-analyzer/backend python3 -m unittest backend.test_embodiment -v\npython3 scripts/embodiment-billion-fuzz.py --n 1000000',
      priority: toolingRelated.score < 85 ? 64 : 50,
      relatedWorkspaceIds: [toolingRelated.id],
      relatedConceptIds: ['error-handling'],
      sourceFindingIds: toolingRelated.findings.map((f) => f.id).slice(0, 2),
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
    out.push({
      id: 'suggest-cam-reason-dry-run',
      kind: 'cam-reason',
      title: 'Keep Phase B cam-reason dry-run + billion fuzz green before Phase C',
      rationale:
        'SGR slow-path must stay bar-gated; every-mic SGR and LitServe farms are cut until dry-run proofs hold.',
      implementation:
        'Run test_cam_reason + cam-reason-billion-fuzz; converse only above intent/length bar; LitServe thin proxy later.',
      sketch:
        'python3 scripts/test_cam_reason.py\npython3 scripts/cam-reason-billion-fuzz.py --n 1000000000\nbash scripts/ci-connectome.sh',
      priority: 73,
      relatedWorkspaceIds: [agiWs.id],
      relatedConceptIds: ['error-handling', 'protocols-extensions'],
      sourceFindingIds: [],
    });
    out.push({
      id: 'suggest-cam-infinitemind',
      kind: 'cam-reason',
      title: 'Keep InfiniteMind logic stage green on slow path',
      rationale:
        'InfiniteMind (logic/meta/epistemic/abductive) enriches SGR; torch RL, qiskit override, and OpenAI idea spam stay cut.',
      implementation:
        'Run test_cam_infinitemind + cam-reason slow-path; submodule integrations/infinitemind must stay present.',
      sketch:
        'python3 scripts/test_cam_infinitemind.py\npython3 scripts/cam-infinitemind.py --goal "make a plan"\npython3 scripts/cam-reason.py --goal "think carefully" --no-write',
      priority: 74,
      relatedWorkspaceIds: [agiWs.id],
      relatedConceptIds: ['error-handling', 'protocols-extensions'],
      sourceFindingIds: [],
    });
    out.push({
      id: 'suggest-cam-fast-path',
      kind: 'cam-reason',
      title: 'Keep System-1 fast path under latency budget',
      rationale:
        'Cam day-to-day speed is the fast gate (cam_fast): LRU + stage skips. InfiniteMind/SGR must stay off greetings.',
      implementation:
        'Run test_cam_fast; bench classify throughput; wire LitServe sLM classify later behind switch.slm_local.',
      sketch:
        'python3 scripts/test_cam_fast.py\npython3 scripts/cam-fast.py --bench 5000\npython3 scripts/cam-reason.py --goal "hi cam" --no-write',
      priority: 75,
      relatedWorkspaceIds: [agiWs.id],
      relatedConceptIds: ['error-handling', 'protocols-extensions'],
      sourceFindingIds: [],
    });
  }

  // Aaron-only voice gate — always suggest when identity / converse surfaces are present
  out.push({
    id: 'suggest-aaron-voice-enroll',
    kind: 'identity-voice',
    title: 'Keep Aaron voice enrolled for noisy-room filtering',
    rationale:
      'Cam must accept only Aaron on the mic. Without enrollment, surrounding conversation leaks into turns.',
    implementation:
      'Open Cam presence → Enroll my voice (~10s quiet). Verify config/identity/aaron-voice-gate.json and hotspot.aaron_voice_noise.',
    sketch:
      'python3 scripts/aaron-voice-gate-check.py\n# UI: Enroll my voice → Enable mic & talk',
    priority: 78,
    relatedWorkspaceIds: workspaces.map((w) => w.id).slice(0, 3),
    relatedConceptIds: ['error-handling'],
    sourceFindingIds: [],
  });
  out.push({
    id: 'suggest-aaron-voice-noisy-gate',
    kind: 'identity-voice',
    title: 'Re-run Aaron-only gate after converse changes',
    rationale:
      'Mic ASR hears the room; voiceprint + server /api/turn must keep rejecting non-Aaron speech.',
    implementation:
      'Exercise enrollment, then speak with background noise / a second talker; confirm Gate ignores. Keep match_threshold 0.85 / noisy_threshold 0.88.',
    sketch:
      'npx vitest run server/core/aaron-voice-gate.test.ts server/core/aaron-voice-gate-addons.test.ts src/lib/aaronVoiceGate.test.ts\npython3 scripts/aaron-voice-gate-check.py',
    priority: 74,
    relatedWorkspaceIds: workspaces.map((w) => w.id).slice(0, 3),
    relatedConceptIds: ['protocols-extensions'],
    sourceFindingIds: [],
  });
  out.push({
    id: 'suggest-aaron-voice-addons',
    kind: 'identity-voice',
    title: 'Use voice-gate add-ons (adaptive / export / reject stats)',
    rationale:
      'Adaptive noise raises threshold after multi-speaker streaks; export/import keeps the Aaron print across devices; reject stats feed health.',
    implementation:
      'Enable mic → trigger surrounding rejects → confirm adaptive↑ badge. Export profile, import on another device. Check /api/health voice_gate_stats and neuron.aaron_voice_gate.',
    sketch:
      'python3 scripts/pack-aaron-voice-profile.py --help\npython3 scripts/aaron-voice-gate-check.py\nnpx vitest run server/core/aaron-voice-gate-addons.test.ts\n# curl -s localhost:8787/api/health | jq .voice_gate_stats',
    priority: 72,
    relatedWorkspaceIds: workspaces.map((w) => w.id).slice(0, 3),
    relatedConceptIds: ['error-handling'],
    sourceFindingIds: [],
  });

  // VoiceStudio local speech — always suggest when health/comms workspaces are present
  const healthWs = workspaces.find((w) => w.kind === 'health');
  const voiceRelatedIds = [healthWs?.id].filter(Boolean) as string[];
  out.push({
    id: 'suggest-voicestudio-local-speech',
    kind: 'presence-voice',
    title: 'Keep VoiceStudio local TTS/ASR wired for Cam',
    rationale:
      'Local-first speech fallback when RIVA/Audio2Face is offline; brain stays nullclaw.',
    implementation:
      'Init submodule, start VoiceStudio backend, bind soft-airy Cam profile, verify /health + MCP /mcp, pack results via pack-voicestudio-result.py.',
    sketch:
      'git submodule update --init integrations/voicestudio\npython3 scripts/voicestudio-health.py\npython3 scripts/voicestudio-speak.py --text "Hello Aaron" --dry-run',
    priority: 58,
    relatedWorkspaceIds: voiceRelatedIds,
    relatedConceptIds: ['concurrency', 'error-handling'],
    sourceFindingIds: [],
  });
  out.push({
    id: 'suggest-voicestudio-mcp-files-mode',
    kind: 'presence-voice',
    title: 'Prefer VoiceStudio MCP files mode for agents',
    rationale:
      'Base64 WAV blows LLM context; files mode keeps renders on disk under OMNIVOICE_MCP_BASE_PATH.',
    implementation:
      'Set OMNIVOICE_MCP_OUTPUT_MODE=files on the backend; point Cam/Cline MCP at http://localhost:3900/mcp with X-VoiceStudio-Client-Id: cam (config/mcp/voicestudio.json).',
    sketch:
      'export OMNIVOICE_MCP_OUTPUT_MODE=files\n# MCP URL: http://localhost:3900/mcp',
    priority: 54,
    relatedWorkspaceIds: voiceRelatedIds,
    relatedConceptIds: ['protocols-extensions'],
    sourceFindingIds: [],
  });

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
