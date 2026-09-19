/**
 * Aaron-only voice gate — spectral voiceprint match for noisy rooms.
 * Used by the React companion (Vite) and mirrored in companions/web/voice-gate.js.
 */

export interface AaronVoiceGateConfig {
  aaron_only: boolean;
  noisy_environment_mode: boolean;
  reject_non_aaron_asr: boolean;
  require_enrollment_for_mic: boolean;
  text_bypass: boolean;
  match_threshold: number;
  noisy_threshold: number;
  enroll_seconds: number;
  min_voiced_frames: number;
  voiced_rms_min: number;
  bands: number;
  f_low_hz: number;
  f_high_hz: number;
  storage_key: string;
}

export interface VoiceProfile {
  version: 1;
  subject: 'Aaron';
  bands: number[];
  pitchHz: number;
  enrolledAt: string;
  sampleSeconds: number;
  frameCount: number;
}

export interface GateDecision {
  accept: boolean;
  score: number;
  threshold: number;
  reason: string;
  multiSpeakerHint: boolean;
}

export const DEFAULT_VOICE_GATE: AaronVoiceGateConfig = {
  aaron_only: true,
  noisy_environment_mode: true,
  reject_non_aaron_asr: true,
  require_enrollment_for_mic: true,
  text_bypass: true,
  match_threshold: 0.85,
  noisy_threshold: 0.88,
  enroll_seconds: 10,
  min_voiced_frames: 10,
  voiced_rms_min: 0.02,
  bands: 32,
  f_low_hz: 80,
  f_high_hz: 4000,
  storage_key: 'cam.aaron.voice.profile.v1',
};

export function mergeVoiceGateConfig(
  partial?: Partial<AaronVoiceGateConfig> | null,
): AaronVoiceGateConfig {
  return { ...DEFAULT_VOICE_GATE, ...(partial || {}) };
}

function bandIndex(freqHz: number, cfg: AaronVoiceGateConfig): number | null {
  if (freqHz < cfg.f_low_hz || freqHz > cfg.f_high_hz) return null;
  const t = (freqHz - cfg.f_low_hz) / (cfg.f_high_hz - cfg.f_low_hz);
  const i = Math.min(cfg.bands - 1, Math.max(0, Math.floor(t * cfg.bands)));
  return i;
}

/** Extract one voiced spectral frame from an AnalyserNode. */
export function extractVoiceFrame(
  analyser: AnalyserNode,
  sampleRate: number,
  cfg: AaronVoiceGateConfig = DEFAULT_VOICE_GATE,
): { voiced: boolean; bands: number[]; pitchHz: number; rms: number } {
  const time = new Uint8Array(analyser.fftSize);
  analyser.getByteTimeDomainData(time);
  let sum = 0;
  for (let i = 0; i < time.length; i++) {
    const v = (time[i]! - 128) / 128;
    sum += v * v;
  }
  const rms = Math.sqrt(sum / time.length);

  const freq = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(freq);
  const bands = new Array(cfg.bands).fill(0);
  const counts = new Array(cfg.bands).fill(0);
  let peakBin = 0;
  let peakVal = 0;
  const binHz = sampleRate / analyser.fftSize;

  for (let i = 0; i < freq.length; i++) {
    const hz = i * binHz;
    const bi = bandIndex(hz, cfg);
    if (bi == null) continue;
    const mag = freq[i]! / 255;
    bands[bi] += mag;
    counts[bi] += 1;
    if (hz >= 80 && hz <= 400 && mag > peakVal) {
      peakVal = mag;
      peakBin = i;
    }
  }
  for (let i = 0; i < bands.length; i++) {
    bands[i] = counts[i] ? bands[i]! / counts[i]! : 0;
  }
  normalizeInPlace(bands);
  return {
    voiced: rms >= cfg.voiced_rms_min,
    bands,
    pitchHz: peakBin * binHz,
    rms,
  };
}

export function normalizeInPlace(v: number[]): void {
  let n = 0;
  for (const x of v) n += x * x;
  n = Math.sqrt(n) || 1;
  for (let i = 0; i < v.length; i++) v[i] = v[i]! / n;
}

export function cosineSimilarity(a: number[], b: number[]): number {
  const n = Math.min(a.length, b.length);
  if (!n) return 0;
  let dot = 0;
  let na = 0;
  let nb = 0;
  for (let i = 0; i < n; i++) {
    dot += a[i]! * b[i]!;
    na += a[i]! * a[i]!;
    nb += b[i]! * b[i]!;
  }
  const d = Math.sqrt(na) * Math.sqrt(nb);
  return d ? Math.max(0, Math.min(1, dot / d)) : 0;
}

export class VoiceprintAccumulator {
  private bandSum: number[];
  private pitchSum = 0;
  private frames = 0;
  private startedAt = Date.now();

  constructor(private readonly cfg: AaronVoiceGateConfig = DEFAULT_VOICE_GATE) {
    this.bandSum = new Array(cfg.bands).fill(0);
  }

  push(frame: { voiced: boolean; bands: number[]; pitchHz: number }): void {
    if (!frame.voiced) return;
    for (let i = 0; i < this.cfg.bands; i++) {
      this.bandSum[i]! += frame.bands[i] ?? 0;
    }
    this.pitchSum += frame.pitchHz;
    this.frames += 1;
  }

  get frameCount(): number {
    return this.frames;
  }

  get elapsedSeconds(): number {
    return (Date.now() - this.startedAt) / 1000;
  }

  ready(minFrames?: number): boolean {
    return this.frames >= (minFrames ?? this.cfg.min_voiced_frames);
  }

  toProfile(sampleSeconds?: number): VoiceProfile | null {
    if (!this.ready()) return null;
    const bands = this.bandSum.map((x) => x / this.frames);
    normalizeInPlace(bands);
    return {
      version: 1,
      subject: 'Aaron',
      bands,
      pitchHz: this.pitchSum / this.frames,
      enrolledAt: new Date().toISOString(),
      sampleSeconds: sampleSeconds ?? this.elapsedSeconds,
      frameCount: this.frames,
    };
  }

  scoreAgainst(profile: VoiceProfile): number {
    if (!this.ready()) return 0;
    const bands = this.bandSum.map((x) => x / this.frames);
    normalizeInPlace(bands);
    const spectral = cosineSimilarity(bands, profile.bands);
    const pitchDelta = Math.abs((this.pitchSum / this.frames) - profile.pitchHz);
    const pitchScore = Math.max(0, 1 - pitchDelta / 180);
    return Math.max(0, Math.min(1, spectral * 0.85 + pitchScore * 0.15));
  }

  reset(): void {
    this.bandSum = new Array(this.cfg.bands).fill(0);
    this.pitchSum = 0;
    this.frames = 0;
    this.startedAt = Date.now();
  }
}

/** Crude multi-speaker hint: live spectrum far from enrolled + high mid-band energy. */
export function multiSpeakerHint(
  liveBands: number[],
  profile: VoiceProfile,
  score: number,
): boolean {
  if (score >= 0.9) return false;
  const mid = liveBands.slice(8, 20);
  const midEnergy = mid.reduce((a, b) => a + b, 0) / (mid.length || 1);
  const enrolledMid =
    profile.bands.slice(8, 20).reduce((a, b) => a + b, 0) / (profile.bands.slice(8, 20).length || 1);
  return score < 0.8 && midEnergy > enrolledMid * 1.35;
}

export function decideAaronVoiceGate(
  score: number,
  cfg: AaronVoiceGateConfig,
  opts: { enrolled: boolean; multiSpeakerHint?: boolean; source?: string } = {
    enrolled: true,
  },
): GateDecision {
  const source = opts.source || 'mic';
  if (source === 'text' && cfg.text_bypass) {
    return {
      accept: true,
      score: 1,
      threshold: 0,
      reason: 'text_bypass',
      multiSpeakerHint: false,
    };
  }
  if (!cfg.aaron_only) {
    return {
      accept: true,
      score,
      threshold: 0,
      reason: 'aaron_only_disabled',
      multiSpeakerHint: Boolean(opts.multiSpeakerHint),
    };
  }
  if (!opts.enrolled && cfg.require_enrollment_for_mic) {
    return {
      accept: false,
      score: 0,
      threshold: cfg.match_threshold,
      reason: 'enrollment_required',
      multiSpeakerHint: false,
    };
  }
  const threshold =
    cfg.noisy_environment_mode || opts.multiSpeakerHint
      ? cfg.noisy_threshold
      : cfg.match_threshold;
  const accept = score >= threshold;
  return {
    accept,
    score,
    threshold,
    reason: accept
      ? 'aaron_voice_match'
      : opts.multiSpeakerHint
        ? 'rejected_surrounding_speech'
        : 'below_threshold',
    multiSpeakerHint: Boolean(opts.multiSpeakerHint),
  };
}

export function loadVoiceProfile(
  storage: Pick<Storage, 'getItem'> = localStorage,
  key = DEFAULT_VOICE_GATE.storage_key,
): VoiceProfile | null {
  try {
    const raw = storage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as VoiceProfile;
    if (parsed?.version !== 1 || !Array.isArray(parsed.bands) || parsed.subject !== 'Aaron') {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveVoiceProfile(
  profile: VoiceProfile,
  storage: Pick<Storage, 'setItem'> = localStorage,
  key = DEFAULT_VOICE_GATE.storage_key,
): void {
  storage.setItem(key, JSON.stringify(profile));
}

export function clearVoiceProfile(
  storage: Pick<Storage, 'removeItem'> = localStorage,
  key = DEFAULT_VOICE_GATE.storage_key,
): void {
  storage.removeItem(key);
}
