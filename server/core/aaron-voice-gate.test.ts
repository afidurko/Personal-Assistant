import { describe, expect, it } from 'vitest';
import {
  evaluateAaronVoiceGate,
  DEFAULT_POLICY,
} from './aaron-voice-gate.js';

describe('evaluateAaronVoiceGate', () => {
  it('allows typed turns without a voice score', () => {
    const r = evaluateAaronVoiceGate({ source: 'text' }, DEFAULT_POLICY);
    expect(r.accept).toBe(true);
    expect(r.reason).toBe('text_bypass');
  });

  it('rejects mic turns below noisy threshold', () => {
    const r = evaluateAaronVoiceGate(
      { source: 'mic', aaron_voice_score: 0.5, enrolled: true },
      DEFAULT_POLICY,
    );
    expect(r.accept).toBe(false);
    expect(r.reason).toBe('below_threshold');
  });

  it('rejects surrounding speech hint even near threshold', () => {
    const r = evaluateAaronVoiceGate(
      {
        source: 'mic',
        aaron_voice_score: 0.86,
        enrolled: true,
        multi_speaker_hint: true,
      },
      DEFAULT_POLICY,
    );
    expect(r.accept).toBe(false);
    expect(r.reason).toBe('rejected_surrounding_speech');
  });

  it('accepts strong Aaron voice matches', () => {
    const r = evaluateAaronVoiceGate(
      { source: 'mic', aaron_voice_score: 0.92, enrolled: true },
      DEFAULT_POLICY,
    );
    expect(r.accept).toBe(true);
    expect(r.reason).toBe('aaron_voice_match');
  });

  it('requires enrollment for mic when configured', () => {
    const r = evaluateAaronVoiceGate(
      { source: 'mic', aaron_voice_score: 0.99, enrolled: false },
      DEFAULT_POLICY,
    );
    expect(r.accept).toBe(false);
    expect(r.reason).toBe('enrollment_required');
  });
});
