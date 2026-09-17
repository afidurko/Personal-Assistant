import { useCallback, useEffect, useRef, useState } from 'react';

export type CamVoiceStatus =
  | 'idle'
  | 'requesting'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'error';

export interface CamBubble {
  who: 'aaron' | 'cam';
  text: string;
  at: string;
}

interface TurnResponse {
  cam: string;
  speak?: { rate?: number; pitch?: number; lang?: string };
}

function speakCam(text: string, opts: { rate?: number; pitch?: number; lang?: string } = {}) {
  if (!window.speechSynthesis) return;
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
  window.speechSynthesis.speak(u);
}

async function postTurn(text: string, source: string): Promise<TurnResponse> {
  const res = await fetch('/api/turn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, transcript: text, source }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<TurnResponse>;
}

export function useCamVoice() {
  const [status, setStatus] = useState<CamVoiceStatus>('idle');
  const [partial, setPartial] = useState('');
  const [level, setLevel] = useState(0);
  const [bubbles, setBubbles] = useState<CamBubble[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [listening, setListening] = useState(false);

  const recognizingRef = useRef(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef(0);
  const busyRef = useRef(false);

  const meterLoop = useCallback(() => {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i]! - 128) / 128;
      sum += v * v;
    }
    setLevel(Math.min(1, Math.sqrt(sum / data.length) * 4));
    rafRef.current = requestAnimationFrame(meterLoop);
  }, []);

  const sendTurn = useCallback(async (text: string, source: string) => {
    const trimmed = text.trim();
    if (!trimmed || busyRef.current) return;
    busyRef.current = true;
    setBubbles((b) => [...b, { who: 'aaron', text: trimmed, at: new Date().toISOString() }]);
    setPartial('');
    setStatus('thinking');
    try {
      await fetch('/api/spike/mic', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ purpose: 'conversation', transcript: trimmed }),
      }).catch(() => undefined);
      const turn = await postTurn(trimmed, source);
      setBubbles((b) => [...b, { who: 'cam', text: turn.cam, at: new Date().toISOString() }]);
      setStatus('speaking');
      speakCam(turn.cam, turn.speak);
      setTimeout(() => {
        if (recognizingRef.current) setStatus('listening');
        else setStatus('idle');
      }, Math.min(8000, 600 + turn.cam.length * 45));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Turn failed');
      setStatus('error');
    } finally {
      busyRef.current = false;
    }
  }, []);

  const stop = useCallback(() => {
    recognizingRef.current = false;
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
    setLevel(0);
    setPartial('');
    setStatus('idle');
    window.speechSynthesis?.cancel();
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
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
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
      meterLoop();

      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) {
        setListening(true);
        setStatus('listening');
        setError('Speech recognition unsupported — type below to talk to Cam.');
        return;
      }
      const recognition = new SR();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      recognition.onresult = (ev: SpeechRecognitionEvent) => {
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
      setStatus('listening');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Mic permission denied');
      setStatus('error');
    }
  }, [meterLoop, sendTurn]);

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
    bubbles,
    error,
    listening,
    startListening,
    stop,
    sendTurn,
  };
}

declare global {
  interface Window {
    webkitAudioContext: typeof AudioContext;
    SpeechRecognition: typeof SpeechRecognition;
    webkitSpeechRecognition: typeof SpeechRecognition;
  }
}
