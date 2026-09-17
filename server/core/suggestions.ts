import type { Finding, Severity, WorkspaceSnapshot, SuggestiveImplementation, SuggestionKind } from '../../shared/types.js';
import { SWIFT_GUIDE_CONCEPTS } from '../../shared/swiftGuide.js';

export type { SuggestiveImplementation, SuggestionKind };

const SEVERITY_PRIORITY: Record<Severity, number> = {
  critical: 95,
  high: 80,
  medium: 60,
  low: 35,
  info: 15,
};

/**
 * Turn live workspace findings into actionable, suggestive implementations
 * that mesh with Swift Guide concepts when relevant.
 */
export function buildSuggestiveImplementations(
  workspaces: WorkspaceSnapshot[],
): SuggestiveImplementation[] {
  const out: SuggestiveImplementation[] = [];

  for (const ws of workspaces) {
    for (const finding of ws.findings) {
      out.push(fromFinding(ws, finding));
    }

    // Workspace-level heuristics even when findings are sparse
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
        sketch: 'import { STATUS_COLORS } from \'@shared/types\';',
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

  // Always offer a learning path tied to the weakest workspace
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
  }

  // Deduplicate by id, keep highest priority
  const byId = new Map<string, SuggestiveImplementation>();
  for (const s of out) {
    const prev = byId.get(s.id);
    if (!prev || s.priority > prev.priority) byId.set(s.id, s);
  }

  return [...byId.values()].sort((a, b) => b.priority - a.priority);
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
  return undefined;
}
