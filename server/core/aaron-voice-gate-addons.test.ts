import { describe, expect, it } from 'vitest';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { writeFile, mkdir } from 'node:fs/promises';
import { AaronVoiceGateAddons } from './aaron-voice-gate-addons.js';

describe('AaronVoiceGateAddons', () => {
  async function makeRoot(): Promise<string> {
    const root = mkdtempSync(path.join(tmpdir(), 'voice-addons-'));
    await mkdir(path.join(root, 'config/identity'), { recursive: true });
    await writeFile(
      path.join(root, 'config/identity/aaron-voice-gate.json'),
      JSON.stringify({
        aaron_only: true,
        noisy_environment_mode: true,
        reject_non_aaron_asr: true,
        require_enrollment_for_mic: true,
        text_bypass: true,
        match_threshold: 0.85,
        noisy_threshold: 0.88,
        addons: {
          adaptive_noise: {
            enabled: true,
            streak_to_raise: 2,
            raised_threshold: 0.91,
            cooldown_accepts: 3,
          },
        },
      }),
      'utf8',
    );
    return root;
  }

  it('raises adaptive threshold after multi-speaker reject streak', async () => {
    const root = await makeRoot();
    const addons = new AaronVoiceGateAddons(root);
    await addons.evaluateWithAddons({
      source: 'mic',
      aaron_voice_score: 0.5,
      enrolled: true,
      multi_speaker_hint: true,
    });
    await addons.evaluateWithAddons({
      source: 'mic',
      aaron_voice_score: 0.5,
      enrolled: true,
      multi_speaker_hint: true,
    });
    expect(addons.getStats().adaptive_raised).toBe(true);
    const mid = await addons.evaluateWithAddons({
      source: 'mic',
      aaron_voice_score: 0.89,
      enrolled: true,
      multi_speaker_hint: false,
    });
    expect(mid.accept).toBe(false);
    expect(mid.adaptive).toBe(true);
    expect(mid.threshold).toBe(0.91);
  });

  it('records reject events and saves profile', async () => {
    const root = await makeRoot();
    const addons = new AaronVoiceGateAddons(root);
    await addons.recordReject({
      at: new Date().toISOString(),
      source: 'mic',
      score: 0.4,
      threshold: 0.88,
      reason: 'below_threshold',
    });
    const out = await addons.saveProfile({
      version: 1,
      subject: 'Aaron',
      bands: new Array(32).fill(0.1),
      pitchHz: 120,
      enrolledAt: new Date().toISOString(),
      sampleSeconds: 10,
      frameCount: 40,
    });
    expect(out).toContain('voice-profile.json');
    const loaded = await addons.loadSavedProfile();
    expect(loaded).toBeTruthy();
    expect((loaded as { subject: string }).subject).toBe('Aaron');
  });

  it('skips stats when note=false', async () => {
    const root = await makeRoot();
    const addons = new AaronVoiceGateAddons(root);
    await addons.evaluateWithAddons(
      { source: 'mic', aaron_voice_score: 0.95, enrolled: true },
      { note: false },
    );
    expect(addons.getStats().accepts).toBe(0);
  });
});
