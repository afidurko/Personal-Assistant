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

const KIND = 'updates' as const;
const ID = 'workspace-updates';
const META = WORKSPACE_META[KIND];

interface PackageJsonShape {
  engines?: Record<string, string>;
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
  peerDependencies?: Record<string, string>;
}

function allDeps(pkg: PackageJsonShape): Record<string, string> {
  return {
    ...(pkg.dependencies ?? {}),
    ...(pkg.devDependencies ?? {}),
    ...(pkg.peerDependencies ?? {}),
  };
}

/** Extract leading major.minor from a semver-ish range. */
function parseLooseVersion(range: string): { major: number; minor: number } | null {
  const m = range.match(/(\d+)\.(\d+)/);
  if (!m) return null;
  return { major: Number(m[1]), minor: Number(m[2]) };
}

export const updatesScanner: WorkspaceScanner = {
  id: ID,
  kind: KIND,

  async scan(rootDir: string): Promise<WorkspaceSnapshot> {
    console.log('[updates] checking dependency freshness patterns…');
    const findings: Finding[] = [];
    const pkg = await readJsonSafe<PackageJsonShape>(path.join(rootDir, 'package.json'));

    if (!pkg) {
      findings.push(
        makeFinding(ID, {
          title: 'Cannot assess package freshness',
          detail: 'package.json missing or invalid.',
          severity: 'critical',
          category: 'manifest',
          suggestion: 'Restore package.json to enable update drift detection.',
        }),
      );
    } else {
      const deps = allDeps(pkg);
      let starRanges = 0;
      const starNames: string[] = [];

      for (const [name, version] of Object.entries(deps)) {
        if (version === '*' || version === 'x' || version === 'latest') {
          starRanges += 1;
          if (starNames.length < 8) starNames.push(`${name}@${version}`);
        }
      }

      if (starRanges > 0) {
        findings.push(
          makeFinding(ID, {
            title: 'Unpinned wildcard dependency ranges',
            detail: `${starRanges} package(s) use * / latest: ${starNames.join(', ')}.`,
            severity: 'high',
            category: 'drift',
            suggestion: 'Pin semver ranges (^ or ~) and refresh the lockfile.',
          }),
        );
      }

      if (!pkg.engines || !pkg.engines.node) {
        findings.push(
          makeFinding(ID, {
            title: 'Missing engines.node field',
            detail: 'package.json does not declare a Node engine constraint.',
            severity: 'medium',
            category: 'runtime',
            suggestion: 'Add an "engines": { "node": ">=20" } (or your target) field.',
          }),
        );
      }

      const react = deps['react'];
      const reactDom = deps['react-dom'];
      if (react && !reactDom) {
        findings.push(
          makeFinding(ID, {
            title: 'react without react-dom',
            detail: `react is declared (${react}) but react-dom is missing.`,
            severity: 'high',
            category: 'consistency',
            suggestion: 'Install a matching react-dom version alongside react.',
          }),
        );
      } else if (react && reactDom) {
        const a = parseLooseVersion(react);
        const b = parseLooseVersion(reactDom);
        if (a && b && a.major !== b.major) {
          findings.push(
            makeFinding(ID, {
              title: 'react / react-dom major mismatch',
              detail: `react@${react} vs react-dom@${reactDom}.`,
              severity: 'high',
              category: 'consistency',
              suggestion: 'Align react and react-dom to the same major version.',
            }),
          );
        }
      }

      const ts = deps['typescript'];
      if (ts) {
        const v = parseLooseVersion(ts);
        if (v && (v.major < 5 || (v.major === 4 && v.minor < 9))) {
          findings.push(
            makeFinding(ID, {
              title: 'TypeScript looks outdated',
              detail: `typescript range is ${ts}.`,
              severity: 'medium',
              category: 'tooling',
              suggestion: 'Upgrade TypeScript to 5.x for modern NodeNext / React tooling.',
            }),
          );
        }
      }

      const vite = deps['vite'];
      if (vite) {
        const v = parseLooseVersion(vite);
        if (v && v.major < 5) {
          findings.push(
            makeFinding(ID, {
              title: 'Vite major is behind',
              detail: `vite range is ${vite}.`,
              severity: 'medium',
              category: 'tooling',
              suggestion: 'Consider upgrading Vite to 5.x or 6.x for current plugin support.',
            }),
          );
        }
      } else if (deps['react']) {
        findings.push(
          makeFinding(ID, {
            title: 'Vite not declared',
            detail: 'React is present but vite is not listed as a dependency.',
            severity: 'low',
            category: 'tooling',
            suggestion: 'Confirm the frontend bundler is declared for reproducible installs.',
          }),
        );
      }

      // Very old react 16/17 patterns
      if (react) {
        const v = parseLooseVersion(react);
        if (v && v.major < 18) {
          findings.push(
            makeFinding(ID, {
              title: 'React major is stale',
              detail: `react range is ${react}.`,
              severity: 'medium',
              category: 'framework',
              suggestion: 'Plan an upgrade path to React 18+ / 19.',
            }),
          );
        }
      }
    }

    const readme = await readTextSafe(path.join(rootDir, 'README.md'));
    if (!readme || readme.trim().length < 80) {
      findings.push(
        makeFinding(ID, {
          title: 'README is stubby',
          detail: readme
            ? `README is only ${readme.trim().length} characters.`
            : 'README.md is missing.',
          severity: 'low',
          category: 'docs',
          suggestion: 'Expand the README with setup, architecture, and operational notes.',
        }),
      );
    }

    const score = scoreFromFindings(findings);
    const status = statusFromScore(score);
    const depCount = pkg ? Object.keys(allDeps(pkg)).length : 0;

    const metrics: Record<string, number | string | boolean> = {
      dependencyCount: depCount,
      hasEngines: Boolean(pkg?.engines?.node),
      readmeLength: readme?.trim().length ?? 0,
      findingCount: findings.length,
    };

    console.log(`[updates] score=${score} findings=${findings.length}`);

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
