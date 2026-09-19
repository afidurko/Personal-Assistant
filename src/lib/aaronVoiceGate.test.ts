import { describe, expect, it } from 'vitest';
import {
  cosineSimilarity,
  decideAaronVoiceGate,
  DEFAULT_VOICE_GATE,
  exportVoiceProfileJson,
  multiSpeakerHint,
  normalizeInPlace,
  parseImportedVoiceProfile,
} from '@/lib/aaronVoiceGate';

describe('aaronVoiceGate client', () => {
  it('scores identical spectra as 1', () => {
    const a = [0.1, 0.2, 0.3, 0.4];
    const b = [...a];
    normalizeInPlace(a);
    normalizeInPlace(b);
    expect(cosineSimilarity(a, b)).toBeCloseTo(1, 5);
  });

  it('rejects below noisy threshold', () => {
    const d = decideAaronVoiceGate(0.7, DEFAULT_VOICE_GATE, {
      enrolled: true,
      source: 'mic',
    });
    expect(d.accept).toBe(false);
  });

  it('accepts high Aaron scores in noisy mode', () => {
    const d = decideAaronVoiceGate(0.9, DEFAULT_VOICE_GATE, {
      enrolled: true,
      source: 'mic',
    });
    expect(d.accept).toBe(true);
    expect(d.reason).toBe('aaron_voice_match');
  });

  it('raises threshold when adaptive noise is active', () => {
    const d = decideAaronVoiceGate(0.89, DEFAULT_VOICE_GATE, {
      enrolled: true,
      source: 'mic',
      adaptiveRaised: true,
    });
    expect(d.accept).toBe(false);
    expect(d.threshold).toBe(0.91);
  });

  it('exports and re-imports Aaron voice profile JSON', () => {
    const profile = {
      version: 1 as const,
      subject: 'Aaron' as const,
      bands: new Array(32).fill(0.1),
      pitchHz: 130,
      enrolledAt: new Date().toISOString(),
      sampleSeconds: 10,
      frameCount: 30,
    };
    const raw = exportVoiceProfileJson(profile);
    const back = parseImportedVoiceProfile(raw);
    expect(back?.subject).toBe('Aaron');
    expect(back?.bands).toHaveLength(32);
  });

  it('flags multi-speaker when mid energy spikes and score is weak', () => {
    const profile = {
      version: 1 as const,
      subject: 'Aaron' as const,
      bands: new Array(32).fill(0.05),
      pitchHz: 140,
      enrolledAt: new Date().toISOString(),
      sampleSeconds: 10,
      frameCount: 20,
    };
    normalizeInPlace(profile.bands);
    const live = new Array(32).fill(0.02);
    for (let i = 8; i < 20; i++) live[i] = 0.4;
    normalizeInPlace(live);
    expect(multiSpeakerHint(live, profile, 0.55)).toBe(true);
  });
});
