/**
 * Aaron-only voice gate (browser companion mirror of src/lib/aaronVoiceGate.ts).
 * Spectral voiceprint — enroll Aaron, then reject surrounding speakers.
 */
(function (global) {
  const DEFAULTS = {
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
    storage_key: "cam.aaron.voice.profile.v1",
  };

  function mergeConfig(partial) {
    return Object.assign({}, DEFAULTS, partial || {});
  }

  function normalizeInPlace(v) {
    let n = 0;
    for (let i = 0; i < v.length; i++) n += v[i] * v[i];
    n = Math.sqrt(n) || 1;
    for (let i = 0; i < v.length; i++) v[i] = v[i] / n;
  }

  function cosineSimilarity(a, b) {
    const n = Math.min(a.length, b.length);
    if (!n) return 0;
    let dot = 0,
      na = 0,
      nb = 0;
    for (let i = 0; i < n; i++) {
      dot += a[i] * b[i];
      na += a[i] * a[i];
      nb += b[i] * b[i];
    }
    const d = Math.sqrt(na) * Math.sqrt(nb);
    return d ? Math.max(0, Math.min(1, dot / d)) : 0;
  }

  function bandIndex(freqHz, cfg) {
    if (freqHz < cfg.f_low_hz || freqHz > cfg.f_high_hz) return null;
    const t = (freqHz - cfg.f_low_hz) / (cfg.f_high_hz - cfg.f_low_hz);
    return Math.min(cfg.bands - 1, Math.max(0, Math.floor(t * cfg.bands)));
  }

  function extractVoiceFrame(analyser, sampleRate, cfg) {
    cfg = mergeConfig(cfg);
    const time = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(time);
    let sum = 0;
    for (let i = 0; i < time.length; i++) {
      const v = (time[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / time.length);
    const freq = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(freq);
    const bands = new Array(cfg.bands).fill(0);
    const counts = new Array(cfg.bands).fill(0);
    let peakBin = 0,
      peakVal = 0;
    const binHz = sampleRate / analyser.fftSize;
    for (let i = 0; i < freq.length; i++) {
      const hz = i * binHz;
      const bi = bandIndex(hz, cfg);
      if (bi == null) continue;
      const mag = freq[i] / 255;
      bands[bi] += mag;
      counts[bi] += 1;
      if (hz >= 80 && hz <= 400 && mag > peakVal) {
        peakVal = mag;
        peakBin = i;
      }
    }
    for (let i = 0; i < bands.length; i++) bands[i] = counts[i] ? bands[i] / counts[i] : 0;
    normalizeInPlace(bands);
    return { voiced: rms >= cfg.voiced_rms_min, bands, pitchHz: peakBin * binHz, rms };
  }

  function Accumulator(cfg) {
    this.cfg = mergeConfig(cfg);
    this.bandSum = new Array(this.cfg.bands).fill(0);
    this.pitchSum = 0;
    this.frames = 0;
    this.startedAt = Date.now();
  }
  Accumulator.prototype.push = function (frame) {
    if (!frame.voiced) return;
    for (let i = 0; i < this.cfg.bands; i++) this.bandSum[i] += frame.bands[i] || 0;
    this.pitchSum += frame.pitchHz;
    this.frames += 1;
  };
  Accumulator.prototype.ready = function () {
    return this.frames >= this.cfg.min_voiced_frames;
  };
  Accumulator.prototype.elapsedSeconds = function () {
    return (Date.now() - this.startedAt) / 1000;
  };
  Accumulator.prototype.toProfile = function () {
    if (!this.ready()) return null;
    const bands = this.bandSum.map((x) => x / this.frames);
    normalizeInPlace(bands);
    return {
      version: 1,
      subject: "Aaron",
      bands,
      pitchHz: this.pitchSum / this.frames,
      enrolledAt: new Date().toISOString(),
      sampleSeconds: this.elapsedSeconds(),
      frameCount: this.frames,
    };
  };
  Accumulator.prototype.scoreAgainst = function (profile) {
    if (!this.ready()) return 0;
    const bands = this.bandSum.map((x) => x / this.frames);
    normalizeInPlace(bands);
    const spectral = cosineSimilarity(bands, profile.bands);
    const pitchDelta = Math.abs(this.pitchSum / this.frames - profile.pitchHz);
    const pitchScore = Math.max(0, 1 - pitchDelta / 180);
    return Math.max(0, Math.min(1, spectral * 0.85 + pitchScore * 0.15));
  };
  Accumulator.prototype.reset = function () {
    this.bandSum = new Array(this.cfg.bands).fill(0);
    this.pitchSum = 0;
    this.frames = 0;
    this.startedAt = Date.now();
  };

  function multiSpeakerHint(liveBands, profile, score) {
    if (score >= 0.9) return false;
    const mid = liveBands.slice(8, 20);
    const midEnergy = mid.reduce((a, b) => a + b, 0) / (mid.length || 1);
    const enrolledMid =
      profile.bands.slice(8, 20).reduce((a, b) => a + b, 0) /
      (profile.bands.slice(8, 20).length || 1);
    return score < 0.8 && midEnergy > enrolledMid * 1.35;
  }

  function decide(score, cfg, opts) {
    cfg = mergeConfig(cfg);
    opts = opts || { enrolled: true };
    const source = opts.source || "mic";
    if (source === "text" && cfg.text_bypass) {
      return { accept: true, score: 1, threshold: 0, reason: "text_bypass", multiSpeakerHint: false };
    }
    if (!cfg.aaron_only) {
      return {
        accept: true,
        score: score,
        threshold: 0,
        reason: "aaron_only_disabled",
        multiSpeakerHint: !!opts.multiSpeakerHint,
      };
    }
    if (!opts.enrolled && cfg.require_enrollment_for_mic) {
      return {
        accept: false,
        score: 0,
        threshold: cfg.match_threshold,
        reason: "enrollment_required",
        multiSpeakerHint: false,
      };
    }
    const threshold =
      cfg.noisy_environment_mode || opts.multiSpeakerHint
        ? cfg.noisy_threshold
        : cfg.match_threshold;
    const accept = score >= threshold;
    return {
      accept: accept,
      score: score,
      threshold: threshold,
      reason: accept
        ? "aaron_voice_match"
        : opts.multiSpeakerHint
          ? "rejected_surrounding_speech"
          : "below_threshold",
      multiSpeakerHint: !!opts.multiSpeakerHint,
    };
  }

  function loadProfile(key) {
    try {
      const raw = localStorage.getItem(key || DEFAULTS.storage_key);
      if (!raw) return null;
      const p = JSON.parse(raw);
      if (!p || p.version !== 1 || p.subject !== "Aaron" || !Array.isArray(p.bands)) return null;
      return p;
    } catch (_) {
      return null;
    }
  }

  function saveProfile(profile, key) {
    localStorage.setItem(key || DEFAULTS.storage_key, JSON.stringify(profile));
  }

  function clearProfile(key) {
    localStorage.removeItem(key || DEFAULTS.storage_key);
  }

  global.CamAaronVoiceGate = {
    DEFAULTS: DEFAULTS,
    mergeConfig: mergeConfig,
    extractVoiceFrame: extractVoiceFrame,
    Accumulator: Accumulator,
    multiSpeakerHint: multiSpeakerHint,
    decide: decide,
    loadProfile: loadProfile,
    saveProfile: saveProfile,
    clearProfile: clearProfile,
    cosineSimilarity: cosineSimilarity,
  };
})(typeof window !== "undefined" ? window : globalThis);
