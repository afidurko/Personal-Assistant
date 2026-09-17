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

const KIND = 'agi_research' as const;
const ID = 'workspace-agi-research';
const META = WORKSPACE_META[KIND];

interface AgiScanPayload {
  day?: string;
  count?: number;
  propose_count?: number;
  fetch_error?: string | null;
  ok?: boolean;
}

interface SwitchDoc {
  switches?: Array<{ id?: string; default?: string }>;
}

/**
 * AGI Research Scan workspace — confirms daily Cam-enhancement research wiring
 * and surfaces the latest vault distillate without applying functionality changes.
 */
export const agiResearchScanner: WorkspaceScanner = {
  id: ID,
  kind: KIND,

  async scan(rootDir: string): Promise<WorkspaceSnapshot> {
    console.log('[agi_research] checking daily AGI scan team wiring…');
    const findings: Finding[] = [];

    const teamPath = path.join(rootDir, 'config/teams/agi-research-scan.json');
    const scriptPath = path.join(rootDir, 'scripts/agi-research-scan.py');
    const enhancePath = path.join(rootDir, 'config/enhancement/slm-dl.json');
    const switchesPath = path.join(rootDir, 'config/connectome/switches.json');
    const grantPath = path.join(rootDir, 'identity/persistence/DAILY_AGI_SCAN.md');

    const team = await readJsonSafe<Record<string, unknown>>(teamPath);
    if (!team) {
      findings.push(
        makeFinding(ID, {
          title: 'AGI research team config missing',
          detail: 'config/teams/agi-research-scan.json is missing or invalid.',
          severity: 'critical',
          category: 'wiring',
          suggestion: 'Restore team config from PR #4 / persistence bundle.',
        }),
      );
    }

    const script = await readTextSafe(scriptPath);
    if (!script) {
      findings.push(
        makeFinding(ID, {
          title: 'AGI research scan script missing',
          detail: 'scripts/agi-research-scan.py not found.',
          severity: 'critical',
          category: 'wiring',
          suggestion: 'Restore scripts/agi-research-scan.py.',
        }),
      );
    }

    if (!(await readTextSafe(grantPath))) {
      findings.push(
        makeFinding(ID, {
          title: 'Daily AGI scan grant missing',
          detail: 'identity/persistence/DAILY_AGI_SCAN.md not found.',
          severity: 'high',
          category: 'authority',
          suggestion: 'Restore Aaron standing-grant note for daily scan.',
        }),
      );
    }

    if (!(await readJsonSafe(enhancePath))) {
      findings.push(
        makeFinding(ID, {
          title: 'sLM/DL enhancement cortex config missing',
          detail: 'config/enhancement/slm-dl.json missing or invalid.',
          severity: 'medium',
          category: 'wiring',
          suggestion: 'Restore config/enhancement/slm-dl.json.',
        }),
      );
    }

    const switches = await readJsonSafe<SwitchDoc>(switchesPath);
    const camEnhance = switches?.switches?.find((s) => s.id === 'switch.cam_enhance');
    if (!camEnhance) {
      findings.push(
        makeFinding(ID, {
          title: 'switch.cam_enhance missing',
          detail: 'Connectome switches lack Aaron functionality-apply gate.',
          severity: 'critical',
          category: 'safety',
          suggestion: 'Add switch.cam_enhance default hold in config/connectome/switches.json.',
        }),
      );
    } else if ((camEnhance.default || '').toLowerCase() !== 'hold') {
      findings.push(
        makeFinding(ID, {
          title: 'cam_enhance gate not hold-by-default',
          detail: `switch.cam_enhance default is "${camEnhance.default}" (expected hold).`,
          severity: 'high',
          category: 'safety',
          suggestion: 'Keep functionality apply propose-only until Aaron approves.',
        }),
      );
    }

    const distillDir = path.join(rootDir, 'vault/10-Mesh-Distillates/agi-scan');
    const today = new Date().toISOString().slice(0, 10);
    let latest = await readJsonSafe<AgiScanPayload>(path.join(distillDir, `${today}.json`));
    let latestDay = today;
    if (!latest) {
      // fall back: any note that team outputs exist
      const index = await readTextSafe(path.join(rootDir, 'vault/04-Research/AGI-Daily-Scan.md'));
      if (!index) {
        findings.push(
          makeFinding(ID, {
            title: 'No AGI daily scan distillates yet',
            detail: 'Run python3 scripts/agi-research-scan.py to seed vault/mesh notes.',
            severity: 'info',
            category: 'freshness',
            suggestion: 'Schedule daily scan or run on demand.',
          }),
        );
      } else {
        findings.push(
          makeFinding(ID, {
            title: 'AGI scan index present; today file missing',
            detail: `No vault/10-Mesh-Distillates/agi-scan/${today}.json yet.`,
            severity: 'low',
            category: 'freshness',
            suggestion: 'Run today’s agi-research-scan.py.',
          }),
        );
      }
    } else if (latest.fetch_error) {
      findings.push(
        makeFinding(ID, {
          title: 'Latest AGI scan had fetch errors',
          detail: String(latest.fetch_error),
          severity: 'medium',
          category: 'runtime',
          suggestion: 'Retry scan; confirm arXiv egress and query shape.',
        }),
      );
    } else {
      findings.push(
        makeFinding(ID, {
          title: `AGI scan ${latest.day ?? latestDay}: ${latest.count ?? 0} papers`,
          detail: `Propose threshold crossed: ${latest.propose_count ?? 0}. Apply still Aaron-gated.`,
          severity: 'info',
          category: 'status',
        }),
      );
    }

    const score = scoreFromFindings(findings);
    const status = statusFromScore(score, findings);
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
        teamConfigured: Boolean(team),
        scriptPresent: Boolean(script),
        camEnhanceDefault: camEnhance?.default ?? 'missing',
        latestProposeCount: latest?.propose_count ?? 0,
        latestPaperCount: latest?.count ?? 0,
      },
      color: STATUS_COLORS[status] ?? META.defaultColor,
      pulse: pulseFromScore(score),
    };
  },
};
