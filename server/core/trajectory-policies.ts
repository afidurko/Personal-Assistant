/**
 * Live OCL/CPV trajectory policies — constitutional physics for motor plans.
 * Mirrors scripts/trajectory_policies.py for in-process enforcement.
 */
import { readFile } from 'node:fs/promises';
import path from 'node:path';

export interface TrajectoryViolation {
  id: string;
  action: string;
  stripped?: string[];
  revise_to?: string;
}

export interface TrajectoryPolicy {
  id: string;
  if_any_motors?: string[];
  if_all_motors?: string[];
  if_any_motors_extra?: string[];
  require_switch_act?: string[];
  if_switch_act?: string[];
  on_violate?: string;
  strip_motors?: string[];
  revise_to?: string;
}

let cached: TrajectoryPolicy[] | null = null;

export async function loadTrajectoryPolicies(rootDir: string): Promise<TrajectoryPolicy[]> {
  if (cached) return cached;
  const raw = await readFile(
    path.join(rootDir, 'config/connectome/trajectory-policies.json'),
    'utf8',
  );
  const doc = JSON.parse(raw) as { policies?: TrajectoryPolicy[] };
  cached = doc.policies || [];
  return cached;
}

export function applyTrajectoryPolicies(
  motorPlan: string[],
  switchState: Record<string, string>,
  policies?: TrajectoryPolicy[],
): { plan: string[]; violations: TrajectoryViolation[] } {
  const pols = policies || cached || [];
  let plan = [...motorPlan];
  const violations: TrajectoryViolation[] = [];

  if (switchState['switch.kill'] === 'act') {
    if (plan.length) violations.push({ id: 'kill_silences_all', action: 'clear_all_motors' });
    return { plan: [], violations };
  }

  for (const pol of pols) {
    const pid = pol.id || '';
    const ifSwitch = pol.if_switch_act || [];
    if (ifSwitch.length && ifSwitch.some((s) => switchState[s] === 'act')) {
      if (pol.on_violate === 'clear_all_motors') {
        if (plan.length) {
          violations.push({ id: pid, action: 'clear_all_motors' });
          plan = [];
        }
      }
      continue;
    }

    const ifAny = new Set(pol.if_any_motors || []);
    const ifAll = new Set(pol.if_all_motors || []);
    const extra = new Set(pol.if_any_motors_extra || []);
    const req = pol.require_switch_act || [];

    if (ifAll.size && [...ifAll].every((m) => plan.includes(m))) {
      const strip = (pol.strip_motors || []).filter((m) => plan.includes(m));
      plan = plan.filter((m) => !strip.includes(m));
      violations.push({
        id: pid,
        action: 'strip',
        stripped: strip,
        revise_to: pol.revise_to,
      });
      continue;
    }

    if (ifAny.size && [...ifAny].some((m) => plan.includes(m))) {
      if (extra.size && ![...extra].some((m) => plan.includes(m))) continue;
      if (req.length) {
        if (req.every((s) => switchState[s] === 'act')) continue;
      } else if (!extra.size) {
        continue;
      }
      const strip = (pol.strip_motors || []).filter((m) => plan.includes(m));
      plan = plan.filter((m) => !strip.includes(m));
      if (strip.length) {
        violations.push({
          id: pid,
          action: 'strip',
          stripped: strip,
          revise_to: pol.revise_to,
        });
      }
      continue;
    }

    if (ifAny.size && req.length && [...ifAny].some((m) => plan.includes(m))) {
      if (!req.every((s) => switchState[s] === 'act')) {
        const strip = (pol.strip_motors || [...ifAny]).filter((m) => plan.includes(m));
        plan = plan.filter((m) => !strip.includes(m));
        violations.push({
          id: pid,
          action: 'strip',
          stripped: strip,
          revise_to: pol.revise_to,
        });
      }
    }
  }

  return { plan, violations };
}

/** Clear module cache (tests). */
export function resetTrajectoryCache(): void {
  cached = null;
}
