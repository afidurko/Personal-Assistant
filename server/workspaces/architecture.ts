import path from 'node:path';
import { WORKSPACE_META, STATUS_COLORS } from '../../shared/types.js';
import type { Finding, WorkspaceSnapshot } from '../../shared/types.js';
import type { WorkspaceScanner } from './types.js';
import {
  makeFinding,
  now,
  pathExists,
  pulseFromScore,
  readTextSafe,
  scoreFromFindings,
  statusFromScore,
  walkDir,
} from './utils.js';

const KIND = 'architecture' as const;
const ID = 'workspace-architecture';
const META = WORKSPACE_META[KIND];

const CODE_EXTS = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.css', '.json', '.md'];

function countByExtension(files: string[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const f of files) {
    const ext = path.extname(f).toLowerCase() || '(none)';
    counts[ext] = (counts[ext] ?? 0) + 1;
  }
  return counts;
}

function layerOf(rel: string): 'frontend' | 'server' | 'shared' | 'other' {
  const n = rel.replace(/\\/g, '/');
  if (n.startsWith('src/') || n === 'src') return 'frontend';
  if (n.startsWith('server/') || n === 'server') return 'server';
  if (n.startsWith('shared/') || n === 'shared') return 'shared';
  return 'other';
}

/** Heuristic: deep relative imports (../../../..) signal coupling risk. */
function detectDeepRelativeImports(content: string): number {
  const re = /from\s+['"]((?:\.\.\/){3,}[^'"]+)['"]/g;
  let count = 0;
  while (re.exec(content)) count += 1;
  return count;
}

async function checkReadmeSections(rootDir: string): Promise<string[]> {
  const readmePath = path.join(rootDir, 'README.md');
  const text = await readTextSafe(readmePath);
  if (!text) return ['entire README'];
  const lower = text.toLowerCase();
  const expected = ['install', 'usage', 'architecture', 'development', 'script'];
  return expected.filter((section) => {
    // Accept heading or plain mention
    return !lower.includes(section);
  });
}

export const architectureScanner: WorkspaceScanner = {
  id: ID,
  kind: KIND,

  async scan(rootDir: string): Promise<WorkspaceSnapshot> {
    console.log('[architecture] walking project tree…');
    const findings: Finding[] = [];

    const hasSrc = await pathExists(path.join(rootDir, 'src'));
    const hasServer = await pathExists(path.join(rootDir, 'server'));
    const hasShared = await pathExists(path.join(rootDir, 'shared'));

    const files = await walkDir(rootDir, { extensions: CODE_EXTS, maxDepth: 14 });
    const relFiles = files.map((f) => path.relative(rootDir, f));
    const byExt = countByExtension(relFiles);

    let frontendFiles = 0;
    let serverFiles = 0;
    let sharedFiles = 0;
    let otherFiles = 0;
    for (const rel of relFiles) {
      const layer = layerOf(rel);
      if (layer === 'frontend') frontendFiles += 1;
      else if (layer === 'server') serverFiles += 1;
      else if (layer === 'shared') sharedFiles += 1;
      else otherFiles += 1;
    }

    if (!hasSrc) {
      findings.push(
        makeFinding(ID, {
          title: 'Frontend layer missing',
          detail: 'No src/ directory — UI layer not detected.',
          severity: 'high',
          category: 'layering',
          suggestion: 'Add a src/ frontend package (or document an alternate UI root).',
        }),
      );
    }
    if (!hasServer) {
      findings.push(
        makeFinding(ID, {
          title: 'Server layer missing',
          detail: 'No server/ directory — backend layer not detected.',
          severity: 'high',
          category: 'layering',
          suggestion: 'Create server/ for API, scanners, and WebSocket mesh.',
        }),
      );
    }
    if (!hasShared) {
      findings.push(
        makeFinding(ID, {
          title: 'Shared types layer missing',
          detail: 'No shared/ directory — cross-cutting contracts may drift.',
          severity: 'medium',
          category: 'layering',
          suggestion: 'Introduce shared/ for domain types used by both client and server.',
        }),
      );
    }

    // Sample source files for deep relative imports
    const sourceCandidates = files.filter((f) => /\.(tsx?|jsx?|mjs|cjs)$/.test(f)).slice(0, 200);
    let deepImportHits = 0;
    let filesWithDeepImports = 0;
    for (const file of sourceCandidates) {
      const content = await readTextSafe(file, 64_000);
      if (!content) continue;
      const hits = detectDeepRelativeImports(content);
      if (hits > 0) {
        deepImportHits += hits;
        filesWithDeepImports += 1;
      }
    }

    if (deepImportHits > 0) {
      findings.push(
        makeFinding(ID, {
          title: 'Deep relative imports detected',
          detail: `${deepImportHits} import(s) spanning 3+ parent segments across ${filesWithDeepImports} file(s) — circular-risk / coupling signal.`,
          severity: deepImportHits >= 5 ? 'medium' : 'low',
          category: 'coupling',
          suggestion: 'Prefer path aliases or shared modules instead of deep ../../../ imports.',
        }),
      );
    }

    const missingReadme = await checkReadmeSections(rootDir);
    if (missingReadme.includes('entire README')) {
      findings.push(
        makeFinding(ID, {
          title: 'README missing',
          detail: 'No README.md found at project root.',
          severity: 'medium',
          category: 'docs',
          suggestion: 'Add a README covering install, architecture, and development scripts.',
        }),
      );
    } else if (missingReadme.length >= 3) {
      findings.push(
        makeFinding(ID, {
          title: 'README sections incomplete',
          detail: `Missing coverage for: ${missingReadme.join(', ')}.`,
          severity: 'low',
          category: 'docs',
          suggestion: 'Expand the README with install, usage, architecture, and development notes.',
        }),
      );
    }

    const testFiles = relFiles.filter(
      (f) =>
        /(^|\/)(tests?|__tests__)(\/|$)/.test(f) ||
        /\.(test|spec)\.(tsx?|jsx?)$/.test(f),
    );
    if (testFiles.length === 0) {
      findings.push(
        makeFinding(ID, {
          title: 'No tests detected',
          detail: 'No *.test.* / *.spec.* files or test directories found.',
          severity: 'high',
          category: 'testing',
          suggestion: 'Add vitest (or similar) coverage for scanners and critical UI paths.',
        }),
      );
    } else if (testFiles.length < 3) {
      findings.push(
        makeFinding(ID, {
          title: 'Sparse test coverage',
          detail: `Only ${testFiles.length} test file(s) found.`,
          severity: 'medium',
          category: 'testing',
          suggestion: 'Grow tests around workspace scanners and neural mesh state transitions.',
        }),
      );
    }

    // Coupling: frontend importing server (anti-layering)
    let crossLayerViolations = 0;
    for (const file of sourceCandidates) {
      const rel = path.relative(rootDir, file).replace(/\\/g, '/');
      if (!rel.startsWith('src/')) continue;
      const content = await readTextSafe(file, 64_000);
      if (!content) continue;
      if (/from\s+['"][^'"]*server\//.test(content) || /from\s+['"]\.\.\/server\//.test(content)) {
        crossLayerViolations += 1;
      }
    }
    if (crossLayerViolations > 0) {
      findings.push(
        makeFinding(ID, {
          title: 'Frontend→server import coupling',
          detail: `${crossLayerViolations} frontend file(s) appear to import server/ modules.`,
          severity: 'high',
          category: 'coupling',
          suggestion: 'Keep server code out of the client bundle; share only via shared/ contracts.',
        }),
      );
    }

    const score = scoreFromFindings(findings);
    const status = statusFromScore(score);

    const metrics: Record<string, number | string | boolean> = {
      totalFiles: files.length,
      frontendFiles,
      serverFiles,
      sharedFiles,
      otherFiles,
      deepImportHits,
      filesWithDeepImports,
      testFileCount: testFiles.length,
      crossLayerViolations,
      hasSrc,
      hasServer,
      hasShared,
      extTs: byExt['.ts'] ?? 0,
      extTsx: byExt['.tsx'] ?? 0,
      extJs: (byExt['.js'] ?? 0) + (byExt['.mjs'] ?? 0) + (byExt['.cjs'] ?? 0),
      extCss: byExt['.css'] ?? 0,
      extMd: byExt['.md'] ?? 0,
      findingCount: findings.length,
    };

    console.log(`[architecture] score=${score} files=${files.length} findings=${findings.length}`);

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
