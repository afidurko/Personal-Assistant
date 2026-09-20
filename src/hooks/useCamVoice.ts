import { useCallback, useEffect, useRef, useState } from 'react';
import {
  DEFAULT_VOICE_GATE,
  VoiceprintAccumulator,
  clearVoiceProfile,
  decideAaronVoiceGate,
  exportVoiceProfileJson,
  extractVoiceFrame,
  loadVoiceProfile,
  mergeVoiceGateConfig,
  multiSpeakerHint,
  parseImportedVoiceProfile,
  saveVoiceProfile,
  type AaronVoiceGateConfig,
  type GateDecision,
  type VoiceProfile,
} from '@/lib/aaronVoiceGate';
import { estimateSpeechMs } from '@/lib/visemes';

export type CamVoiceStatus =
  | 'idle'
  | 'requesting'
  | 'enrolling'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'ignored'
  | 'error';

export interface CamBubble {
  who: 'aaron' | 'cam' | 'system';
  text: string;
  at: string;
}

export interface VoiceGateClientStats {
  rejects: number;
  accepts: number;
  adaptiveRaised: boolean;
  multiSpeakerStreak: number;
}

export interface CamRouteSummary {
  behavior: string;
  pathway: string[];
  tracts: string[];
  hotspot_id: string | null;
  dual_stream?: { winner: string; tracts: string[] };
}

interface TurnResponse {
  cam: string;
  speak?: { rate?: number; pitch?: number; lang?: string };
  rejected?: boolean;
  gate?: { reason?: string; score?: number; threshold?: number; adaptive?: boolean };
  voice_stats?: {
    rejects?: number;
    accepts?: number;
    adaptive_raised?: boolean;
    multi_speaker_streak?: number;
  };
  bridge?: {
    route?: {
      behavior?: string;
      pathway?: string[];
      tracts?: string[];
      hotspot_id?: string | null;
      dual_stream?: { winner?: string; tracts?: string[] };
    };
  };
}

type SpeakOpts = { rate?: number; pitch?: number; lang?: string };

export interface SpeechFaceState {
  text: string;
  progress: number; // 0..1, -1 when not speaking
  active: boolean;
}

function speakCam(
  text: string,
  opts: SpeakOpts = {},
  handlers: {
    onEnd?: () => void;
    onStart?: () => void;
    onBoundary?: (charIndex: number) => void;
  } = {},
) {
  if (!window.speechSynthesis) {
    handlers.onEnd?.();
    return;
  }
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = opts.lang || 'en-US';
  u.rate = opts.rate ?? 0.95;
  u.pitch = opts.pitch ?? 1.05;
  const voices = window.speechSynthesis.getVoices();
  const prefer =
    voices.find((v) =>
      /female|samantha|karen|moira|tessa|fiona|victoria|zira/i.test(v.name),
    ) || voices.find((v) => v.lang?.startsWith('en'));
  if (prefer) u.voice = prefer;
  u.onstart = () => handlers.onStart?.();
  u.onboundary = (ev) => {
    if (typeof ev.charIndex === 'number') handlers.onBoundary?.(ev.charIndex);
  };
  u.onend = () => handlers.onEnd?.();
  u.onerror = () => handlers.onEnd?.();
  window.speechSynthesis.speak(u);
}

function summarizeRoute(route: TurnResponse['bridge']): CamRouteSummary | null {
  const r = route?.route;
  if (!r) return null;
  return {
    behavior: String(r.behavior || 'reply'),
    pathway: Array.isArray(r.pathway) ? r.pathway.map(String) : [],
    tracts: Array.isArray(r.tracts) ? r.tracts.map(String) : [],
    hotspot_id: r.hotspot_id ?? null,
    dual_stream: r.dual_stream
      ? {
          winner: String(r.dual_stream.winner || 'dorsal'),
          tracts: Array.isArray(r.dual_stream.tracts) ? r.dual_stream.tracts.map(String) : [],
        }
      : undefined,
  };
}

async function fetchVoiceGateConfig(): Promise<AaronVoiceGateConfig> {
  try {
    const res = await fetch('/config/identity/aaron-voice-gate.json');
    if (!res.ok) return DEFAULT_VOICE_GATE;
    return mergeVoiceGateConfig(await res.json());
  } catch {
    return DEFAULT_VOICE_GATE;
  }
}

async function postTurn(
  text: string,
  source: string,
  gate: { score: number; enrolled: boolean; multiSpeakerHint: boolean },
): Promise<TurnResponse> {
  const res = await fetch('/api/turn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      transcript: text,
      source,
      aaron_voice_score: gate.score,
      enrolled: gate.enrolled,
      multi_speaker_hint: gate.multiSpeakerHint,
      device_id: 'web-home',
    }),
  });
  if (res.status === 403) {
    const body = (await res.json().catch(() => ({}))) as TurnResponse;
    return { ...body, rejected: true, cam: body.cam || '' };
  }
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<TurnResponse>;
}

export function useCamVoice() {
  const [status, setStatus] = useState<CamVoiceStatus>('idle');
  const [partial, setPartial] = useState('');
  const [level, setLevel] = useState(0);
  const [voiceScore, setVoiceScore] = useState(0);
  const [bubbles, setBubbles] = useState<CamBubble[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const [enrolled, setEnrolled] = useState(false);
  const [enrollProgress, setEnrollProgress] = useState(0);
  const [gateCfg, setGateCfg] = useState<AaronVoiceGateConfig>(DEFAULT_VOICE_GATE);
  const [lastGate, setLastGate] = useState<GateDecision | null>(null);
  const [adaptiveRaised, setAdaptiveRaised] = useState(false);
  const [gateStats, setGateStats] = useState<VoiceGateClientStats>({
    rejects: 0,
    accepts: 0,
    adaptiveRaised: false,
    multiSpeakerStreak: 0,
  });
  const [lastRoute, setLastRoute] = useState<CamRouteSummary | null>(null);
  const [bridgeBusy, setBridgeBusy] = useState(false);
  const [speechFace, setSpeechFace] = useState<SpeechFaceState>({
    text: '',
    progress: -1,
    active: false,
  });

  const recognizingRef = useRef(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef(0);
  const busyRef = useRef(false);
  const profileRef = useRef<VoiceProfile | null>(null);
  const utterRef = useRef<VoiceprintAccumulator | null>(null);
  const enrollRef = useRef<VoiceprintAccumulator | null>(null);
  const enrollingRef = useRef(false);
  const cfgRef = useRef(gateCfg);
  const adaptiveRef = useRef(false);
  const streakRef = useRef(0);
  const acceptsSinceRaiseRef = useRef(0);
  const pendingSpeakRef = useRef<{ text: string; opts: SpeakOpts } | null>(null);
  const speechTimerRef = useRef(0);
  const speechTickRef = useRef(0);

  useEffect(() => {
    cfgRef.current = gateCfg;
  }, [gateCfg]);

  useEffect(() => {
    void fetchVoiceGateConfig().then(setGateCfg);
    const p = loadVoiceProfile();
    profileRef.current = p;
    setEnrolled(Boolean(p));
  }, []);

  const applyServerStats = useCallback((stats?: TurnResponse['voice_stats']) => {
    if (!stats) return;
    const raised = Boolean(stats.adaptive_raised);
    adaptiveRef.current = raised;
    setAdaptiveRaised(raised);
    streakRef.current = Number(stats.multi_speaker_streak ?? streakRef.current);
    setGateStats({
      rejects: Number(stats.rejects ?? 0),
      accepts: Number(stats.accepts ?? 0),
      adaptiveRaised: raised,
      multiSpeakerStreak: streakRef.current,
    });
  }, []);

  const noteClientReject = useCallback(
    async (decision: GateDecision, score: number, multi: boolean) => {
      streakRef.current += multi || decision.reason === 'rejected_surrounding_speech' ? 1 : 0;
      const need = cfgRef.current.adaptive_streak_to_raise ?? 2;
      if (streakRef.current >= need) {
        adaptiveRef.current = true;
        setAdaptiveRaised(true);
      }
      acceptsSinceRaiseRef.current = 0;
      setGateStats((s) => ({
        ...s,
        rejects: s.rejects + 1,
        adaptiveRaised: adaptiveRef.current,
        multiSpeakerStreak: streakRef.current,
      }));
      await fetch('/api/voice/gate/reject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          score,
          threshold: decision.threshold,
          reason: decision.reason,
          source: 'mic',
          multi_speaker_hint: multi,
          device_id: 'web-home',
        }),
      }).catch(() => undefined);
    },
    [],
  );

  const meterLoop = useCallback(() => {
    const analyser = analyserRef.current;
    const ctx = audioCtxRef.current;
    if (!analyser || !ctx) return;
    const frame = extractVoiceFrame(analyser, ctx.sampleRate, cfgRef.current);
    setLevel(Math.min(1, frame.rms * 4));

    if (enrollingRef.current && enrollRef.current) {
      enrollRef.current.push(frame);
      const need = cfgRef.current.enroll_seconds;
      setEnrollProgress(Math.min(1, enrollRef.current.elapsedSeconds / need));
      if (enrollRef.current.elapsedSeconds >= need && enrollRef.current.ready()) {
        const profile = enrollRef.current.toProfile(need);
        if (profile) {
          saveVoiceProfile(profile, localStorage, cfgRef.current.storage_key);
          profileRef.current = profile;
          setEnrolled(true);
          enrollingRef.current = false;
          enrollRef.current = null;
          setEnrollProgress(1);
          setStatus('listening');
          setBubbles((b) => [
            ...b,
            {
              who: 'system',
              text: 'Aaron voice enrolled. Cam will only accept your voice in noisy rooms.',
              at: new Date().toISOString(),
            },
          ]);
        }
      }
    } else if (utterRef.current && frame.voiced) {
      utterRef.current.push(frame);
      const profile = profileRef.current;
      if (profile && utterRef.current.ready()) {
        setVoiceScore(utterRef.current.scoreAgainst(profile));
      }
    }

    rafRef.current = requestAnimationFrame(meterLoop);
  }, []);

  const sendTurn = useCallback(
    async (text: string, source: string) => {
      const trimmed = text.trim();
      if (!trimmed || busyRef.current) return;
      const cfg = cfgRef.current;
      const profile = profileRef.current;

      let score = source === 'text' ? 1 : 0;
      let multi = false;
      if (source !== 'text' && profile && utterRef.current?.ready()) {
        score = utterRef.current.scoreAgainst(profile);
        const bands = utterRef.current.toProfile()?.bands || profile.bands;
        multi = multiSpeakerHint(bands, profile, score);
      }
      utterRef.current?.reset();

      const decision = decideAaronVoiceGate(score, cfg, {
        enrolled: Boolean(profile),
        multiSpeakerHint: multi,
        source,
        adaptiveRaised: adaptiveRef.current,
      });
      setLastGate(decision);
      setVoiceScore(score);

      if (!decision.accept) {
        setStatus('ignored');
        const msg =
          decision.reason === 'enrollment_required'
            ? 'Enroll your voice first (quiet 10s) so Cam can ignore other people.'
            : decision.reason === 'rejected_surrounding_speech'
              ? 'Heard other voices nearby — ignored. Speak again when it’s you.'
              : `Not matched as Aaron (score ${(score * 100).toFixed(0)}% < ${(decision.threshold * 100).toFixed(0)}%). Ignored.`;
        setBubbles((b) => [...b, { who: 'system', text: msg, at: new Date().toISOString() }]);
        void noteClientReject(decision, score, multi);
        setTimeout(() => {
          if (recognizingRef.current) setStatus('listening');
        }, 1200);
        return;
      }

      if (source !== 'text') {
        acceptsSinceRaiseRef.current += 1;
        if (
          adaptiveRef.current &&
          acceptsSinceRaiseRef.current >= (cfg.adaptive_cooldown_accepts ?? 3)
        ) {
          adaptiveRef.current = false;
          streakRef.current = 0;
          acceptsSinceRaiseRef.current = 0;
          setAdaptiveRaised(false);
        }
        if (!multi) streakRef.current = 0;
      }

      busyRef.current = true;
      setBridgeBusy(true);
      setBubbles((b) => [...b, { who: 'aaron', text: trimmed, at: new Date().toISOString() }]);
      setPartial('');
      setStatus('thinking');
      try {
        await fetch('/api/spike/aaron.voice', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            score,
            enrolled: Boolean(profile),
            multi_speaker_hint: multi,
            device_id: 'web-home',
          }),
        }).catch(() => undefined);
        await fetch('/api/spike/mic', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            purpose: 'conversation',
            transcript: trimmed,
            aaron_voice_score: score,
          }),
        }).catch(() => undefined);
        const turn = await postTurn(trimmed, source, {
          score,
          enrolled: Boolean(profile),
          multiSpeakerHint: multi,
        });
        applyServerStats(turn.voice_stats);
        const route = summarizeRoute(turn.bridge);
        if (route) setLastRoute(route);
        if (turn.rejected) {
          setStatus('ignored');
          setBubbles((b) => [
            ...b,
            {
              who: 'system',
              text: turn.cam || 'Server rejected non-Aaron speech.',
              at: new Date().toISOString(),
            },
          ]);
          return;
        }
        // Queue speech — CamStage types first, then flushSpeak()
        pendingSpeakRef.current = { text: turn.cam, opts: turn.speak || {} };
        setBubbles((b) => [...b, { who: 'cam', text: turn.cam, at: new Date().toISOString() }]);
        setStatus('speaking');
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Turn failed');
        setStatus('error');
        pendingSpeakRef.current = null;
      } finally {
        busyRef.current = false;
        setBridgeBusy(false);
      }
    },
    [applyServerStats, noteClientReject],
  );

  /** Called by CamStage after typewriter finishes — Cam speaks the typed reply. */
  const flushSpeak = useCallback(() => {
    const pending = pendingSpeakRef.current;
    if (!pending) return;
    pendingSpeakRef.current = null;
    setStatus('speaking');

    if (speechTimerRef.current) window.clearTimeout(speechTimerRef.current);
    if (speechTickRef.current) window.clearInterval(speechTickRef.current);

    const dur = estimateSpeechMs(pending.text, pending.opts.rate ?? 0.95);
    const started = performance.now();
    setSpeechFace({ text: pending.text, progress: 0, active: true });

    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      if (speechTimerRef.current) window.clearTimeout(speechTimerRef.current);
      if (speechTickRef.current) window.clearInterval(speechTickRef.current);
      speechTimerRef.current = 0;
      speechTickRef.current = 0;
      setSpeechFace({ text: '', progress: -1, active: false });
      if (recognizingRef.current) setStatus('listening');
      else setStatus('idle');
    };

    // Keep visemes moving even when the browser skips boundary events
    speechTickRef.current = window.setInterval(() => {
      const p = Math.min(0.995, (performance.now() - started) / dur);
      setSpeechFace((s) => (s.active ? { ...s, progress: Math.max(s.progress, p) } : s));
    }, 40);

    speakCam(pending.text, pending.opts, {
      onStart: () => setSpeechFace((s) => ({ ...s, active: true })),
      onBoundary: (charIndex) => {
        const len = Math.max(1, pending.text.length);
        const p = Math.min(0.99, charIndex / len);
        setSpeechFace((s) => ({
          ...s,
          active: true,
          progress: Math.max(s.progress, p),
        }));
      },
      onEnd: () => {
        const remain = dur - (performance.now() - started);
        if (speechTimerRef.current) window.clearTimeout(speechTimerRef.current);
        speechTimerRef.current = window.setTimeout(finish, Math.max(80, remain));
      },
    });
    // Hard stop if TTS never fires onend
    speechTimerRef.current = window.setTimeout(finish, dur + 1200);
  }, []);

  const stop = useCallback(() => {
    recognizingRef.current = false;
    enrollingRef.current = false;
    setListening(false);
    try {
      recognitionRef.current?.stop();
    } catch {
      /* ignore */
    }
    recognitionRef.current = null;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = 0;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void audioCtxRef.current?.close();
    audioCtxRef.current = null;
    analyserRef.current = null;
    utterRef.current = null;
    enrollRef.current = null;
    setLevel(0);
    setPartial('');
    setStatus('idle');
    pendingSpeakRef.current = null;
    setBridgeBusy(false);
    if (speechTimerRef.current) window.clearTimeout(speechTimerRef.current);
    if (speechTickRef.current) window.clearInterval(speechTickRef.current);
    speechTimerRef.current = 0;
    speechTickRef.current = 0;
    setSpeechFace({ text: '', progress: -1, active: false });
    window.speechSynthesis?.cancel();
    void fetch('/api/spike/mic/stop', { method: 'POST' }).catch(() => undefined);
  }, []);

  const ensureAudio = useCallback(async () => {
    if (streamRef.current && analyserRef.current && audioCtxRef.current) return;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
      video: false,
    });
    streamRef.current = stream;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new Ctx();
    if (audioCtx.state === 'suspended') await audioCtx.resume();
    audioCtxRef.current = audioCtx;
    const src = audioCtx.createMediaStreamSource(stream);
    const analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    src.connect(analyser);
    analyserRef.current = analyser;
    if (!rafRef.current) meterLoop();
  }, [meterLoop]);

  const startEnroll = useCallback(async () => {
    setError(null);
    setStatus('requesting');
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Microphone API missing in this browser.');
      setStatus('error');
      return;
    }
    try {
      await ensureAudio();
      enrollRef.current = new VoiceprintAccumulator(cfgRef.current);
      enrollingRef.current = true;
      setEnrollProgress(0);
      setStatus('enrolling');
      setListening(true);
      setBubbles((b) => [
        ...b,
        {
          who: 'system',
          text: `Speak alone for ~${cfgRef.current.enroll_seconds}s so Cam learns only your voice.`,
          at: new Date().toISOString(),
        },
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Mic permission denied');
      setStatus('error');
    }
  }, [ensureAudio]);

  const clearEnrollment = useCallback(() => {
    clearVoiceProfile(localStorage, cfgRef.current.storage_key);
    profileRef.current = null;
    setEnrolled(false);
    setVoiceScore(0);
    setBubbles((b) => [
      ...b,
      { who: 'system', text: 'Aaron voice enrollment cleared.', at: new Date().toISOString() },
    ]);
  }, []);

  const exportProfile = useCallback(() => {
    const profile = profileRef.current;
    if (!profile) return false;
    const blob = new Blob([exportVoiceProfileJson(profile)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'aaron-voice-profile.json';
    a.click();
    URL.revokeObjectURL(url);
    void fetch('/api/voice/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile }),
    }).catch(() => undefined);
    setBubbles((b) => [
      ...b,
      { who: 'system', text: 'Aaron voice profile exported.', at: new Date().toISOString() },
    ]);
    return true;
  }, []);

  const importProfile = useCallback(async (raw: string) => {
    const profile = parseImportedVoiceProfile(raw);
    if (!profile) {
      setError('Invalid Aaron voice profile JSON');
      return false;
    }
    saveVoiceProfile(profile, localStorage, cfgRef.current.storage_key);
    profileRef.current = profile;
    setEnrolled(true);
    await fetch('/api/voice/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile }),
    }).catch(() => undefined);
    setBubbles((b) => [
      ...b,
      { who: 'system', text: 'Aaron voice profile imported.', at: new Date().toISOString() },
    ]);
    return true;
  }, []);

  const startListening = useCallback(async () => {
    setError(null);
    setStatus('requesting');
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Microphone API missing in this browser.');
      setStatus('error');
      return;
    }
    try {
      await ensureAudio();
      utterRef.current = new VoiceprintAccumulator(cfgRef.current);

      if (!profileRef.current && cfgRef.current.require_enrollment_for_mic) {
        enrollRef.current = new VoiceprintAccumulator(cfgRef.current);
        enrollingRef.current = true;
        setEnrollProgress(0);
        setStatus('enrolling');
        setBubbles((b) => [
          ...b,
          {
            who: 'system',
            text: `Speak alone for ~${cfgRef.current.enroll_seconds}s so Cam learns only your voice.`,
            at: new Date().toISOString(),
          },
        ]);
      }

      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) {
        setListening(true);
        setStatus(profileRef.current ? 'listening' : 'enrolling');
        setError('Speech recognition unsupported — type below to talk to Cam.');
        return;
      }
      const recognition = new SR();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      recognition.onresult = (ev: SpeechRecognitionEvent) => {
        if (enrollingRef.current) {
          setPartial('Enrolling your voice… keep talking alone');
          return;
        }
        let interim = '';
        let finalText = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const r = ev.results[i];
          if (!r) continue;
          if (r.isFinal) finalText += r[0]?.transcript ?? '';
          else interim += r[0]?.transcript ?? '';
        }
        setPartial(interim || '…');
        if (finalText.trim()) void sendTurn(finalText.trim(), 'mic');
      };
      recognition.onerror = (ev: SpeechRecognitionErrorEvent) => {
        if (ev.error !== 'no-speech') setError(`Speech: ${ev.error}`);
      };
      recognition.onend = () => {
        if (recognizingRef.current) {
          try {
            recognition.start();
          } catch {
            /* restart race */
          }
        }
      };
      recognitionRef.current = recognition;
      recognizingRef.current = true;
      recognition.start();
      setListening(true);
      if (!enrollingRef.current) {
        setStatus(profileRef.current ? 'listening' : 'enrolling');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Mic permission denied');
      setStatus('error');
    }
  }, [ensureAudio, sendTurn]);

  useEffect(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.getVoices();
      window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
    }
    return () => stop();
  }, [stop]);

  return {
    status,
    partial,
    level,
    voiceScore,
    bubbles,
    error,
    listening,
    enrolled,
    enrollProgress,
    lastGate,
    adaptiveRaised,
    gateStats,
    lastRoute,
    bridgeBusy,
    speechFace,
    aaronOnly: gateCfg.aaron_only,
    startListening,
    startEnroll,
    clearEnrollment,
    exportProfile,
    importProfile,
    stop,
    sendTurn,
    flushSpeak,
  };
}

declare global {
  interface Window {
    webkitAudioContext: typeof AudioContext;
    SpeechRecognition: typeof SpeechRecognition;
    webkitSpeechRecognition: typeof SpeechRecognition;
  }
}
