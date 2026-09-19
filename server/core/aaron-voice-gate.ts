/**
 * Server-side Aaron voice gate — validates companion-reported scores.
 * Does not run spectral matching (that stays on-device); enforces policy.
 */
import { readFile } from 'node:fs/promises';
import path from 'node:path';

export interface AaronVoiceGatePolicy {
  aaron_only: boolean;
  noisy_environment_mode: boolean;
  reject_non_aaron_asr: boolean;
  require_enrollment_for_mic: boolean;
  text_bypass: boolean;
  match_threshold: number;
  noisy_threshold: number;
}

export const DEFAULT_POLICY: AaronVoiceGatePolicy = {
  aaron_only: true,
  noisy_environment_mode: true,
  reject_non_aaron_asr: true,
  require_enrollment_for_mic: true,
  text_bypass: true,
  match_threshold: 0.85,
  noisy_threshold: 0.88,
};

export interface VoiceGateRequest {
  source?: string;
  aaron_voice_score?: number | null;
  enrolled?: boolean;
  multi_speaker_hint?: boolean;
}

export interface VoiceGateResult {
  accept: boolean;
  reason: string;
  threshold: number;
  score: number;
  sense?: string;
}

export async function loadAaronVoiceGatePolicy(rootDir: string): Promise<AaronVoiceGatePolicy> {
  try {
    const raw = await readFile(path.join(rootDir, 'config/identity/aaron-voice-gate.json'), 'utf8');
    const parsed = JSON.parse(raw) as Partial<AaronVoiceGatePolicy>;
    return { ...DEFAULT_POLICY, ...parsed };
  } catch {
    return { ...DEFAULT_POLICY };
  }
}

export function evaluateAaronVoiceGate(
  req: VoiceGateRequest,
  policy: AaronVoiceGatePolicy = DEFAULT_POLICY,
): VoiceGateResult {
  const source = req.source || 'text';
  const score = typeof req.aaron_voice_score === 'number' ? req.aaron_voice_score : 0;

  if (source === 'text' && policy.text_bypass) {
    return { accept: true, reason: 'text_bypass', threshold: 0, score: 1 };
  }

  if (!policy.aaron_only || !policy.reject_non_aaron_asr) {
    return { accept: true, reason: 'aaron_only_disabled', threshold: 0, score };
  }

  if (source !== 'mic' && source !== 'speech') {
    return { accept: true, reason: 'non_mic_source', threshold: 0, score };
  }

  if (policy.require_enrollment_for_mic && req.enrolled === false) {
    return {
      accept: false,
      reason: 'enrollment_required',
      threshold: policy.match_threshold,
      score: 0,
      sense: 'sense.aaron.voice',
    };
  }

  const threshold =
    policy.noisy_environment_mode || req.multi_speaker_hint
      ? policy.noisy_threshold
      : policy.match_threshold;

  if (score >= threshold) {
    return {
      accept: true,
      reason: 'aaron_voice_match',
      threshold,
      score,
      sense: 'sense.aaron.voice',
    };
  }

  return {
    accept: false,
    reason: req.multi_speaker_hint ? 'rejected_surrounding_speech' : 'below_threshold',
    threshold,
    score,
    sense: 'sense.aaron.voice',
  };
}
