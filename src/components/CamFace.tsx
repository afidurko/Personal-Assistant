/**
 * CamFace — TalkingHead 3D presence (ARKit / Oculus visemes).
 * Browser path while RIVA+Audio2Face desk studio is offline.
 * Avatar GLB: public/avatars/cam.glb (TalkingHead brunette stand-in).
 *
 * LipsyncEn is imported statically — Vite pre-bundling breaks TalkingHead's
 * dynamic import('./lipsync-en.mjs') and leaves the mouth frozen.
 */
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { TalkingHead } from '@met4citizen/talkinghead';
import { LipsyncEn } from '@met4citizen/talkinghead/modules/lipsync-en.mjs';
import { estimateSpeechMs, expressionFromStatus, type FaceExpression } from '@/lib/visemes';
import type { CamVoiceStatus } from '@/hooks/useCamVoice';

interface CamFaceProps {
  status: CamVoiceStatus;
  listening: boolean;
  level: number;
  typing?: boolean;
  speakingText?: string;
  speechProgress?: number;
  /** Optional override; default /avatars/cam.glb */
  avatarUrl?: string;
}

const AVATAR_URL = '/avatars/cam.glb';

function moodFor(expr: FaceExpression): string {
  switch (expr) {
    case 'speak':
      return 'happy';
    case 'concern':
    case 'ignored':
      return 'sad';
    default:
      return 'neutral';
  }
}

/** Word timings for TalkingHead speakAudio (drives real viseme blendshapes). */
function wordsTiming(text: string, durationMs: number) {
  const words = text
    .replace(/[^\w\s'’-]/g, ' ')
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) {
    return { words: ['.'], wtimes: [0], wdurations: [durationMs] };
  }
  const totalChars = words.reduce((n, w) => n + w.length, 0) || 1;
  const wtimes: number[] = [];
  const wdurations: number[] = [];
  let t = 60;
  const usable = Math.max(400, durationMs - 160);
  for (const w of words) {
    const dur = Math.max(90, (w.length / totalChars) * usable);
    wtimes.push(t);
    wdurations.push(dur);
    t += dur + 25;
  }
  return { words, wtimes, wdurations };
}

function makeSilentBuffer(ctx: AudioContext, durationMs: number): AudioBuffer {
  const sampleRate = ctx.sampleRate || 22050;
  const len = Math.max(1, Math.floor((durationMs / 1000) * sampleRate));
  const buffer = ctx.createBuffer(1, len, sampleRate);
  // Near-silent — browser speechSynthesis carries the audible voice;
  // TalkingHead uses this timeline for blendshape lip-sync.
  const data = buffer.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = 0;
  return buffer;
}

export function CamFace({
  status,
  listening,
  level,
  typing = false,
  speakingText = '',
  avatarUrl = AVATAR_URL,
}: CamFaceProps) {
  const mountRef = useRef<HTMLDivElement>(null);
  const headRef = useRef<TalkingHead | null>(null);
  const lastSpokenRef = useRef('');
  const [ready, setReady] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadPct, setLoadPct] = useState(0);
  const expr = expressionFromStatus(status, typing);

  // Boot TalkingHead
  useEffect(() => {
    const node = mountRef.current;
    if (!node) return;
    let cancelled = false;
    let head: TalkingHead | null = null;

    (async () => {
      try {
        head = new TalkingHead(node, {
          lipsyncModules: ['en'],
          lipsyncLang: 'en',
          cameraView: 'head',
          cameraDistance: 0,
          cameraZoomEnable: false,
          cameraRotateEnable: false,
          cameraPanEnable: false,
          modelFPS: 30,
          avatarIdleEyeContact: 0.4,
          avatarSpeakingEyeContact: 0.65,
          avatarIdleHeadMove: 0.45,
          avatarSpeakingHeadMove: 0.6,
          lightAmbientIntensity: 2.2,
          lightDirectIntensity: 18,
          lightSpotIntensity: 8,
        });
        // Force English lipsync even if Vite breaks the dynamic module path.
        head.lipsync = head.lipsync || {};
        head.lipsync.en = new LipsyncEn();

        if (cancelled) {
          head.stopSpeaking?.();
          head.stop?.();
          return;
        }
        headRef.current = head;

        // Unlock AudioContext on first user gesture (required for speakAudio).
        const unlock = () => {
          try {
            void head?.audioCtx?.resume?.();
          } catch {
            /* ignore */
          }
        };
        window.addEventListener('pointerdown', unlock, { once: true });
        window.addEventListener('keydown', unlock, { once: true });

        await head.showAvatar(
          {
            url: avatarUrl,
            body: 'F',
            avatarMood: 'neutral',
            lipsyncLang: 'en',
            lipsyncHeadMovement: true,
          },
          (ev) => {
            if (ev?.lengthComputable && ev.total) {
              setLoadPct(Math.min(100, Math.round((ev.loaded / ev.total) * 100)));
            }
          },
        );
        if (cancelled) return;
        try {
          void head.audioCtx?.resume?.();
        } catch {
          /* ignore */
        }
        setReady(true);
        setLoadError(null);
      } catch (e) {
        console.error('Cam TalkingHead boot failed', e);
        if (!cancelled) {
          setLoadError(e instanceof Error ? e.message : 'Avatar failed to load');
          setReady(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      try {
        headRef.current?.stopSpeaking?.();
        headRef.current?.stop?.();
      } catch {
        /* ignore */
      }
      headRef.current = null;
      if (node) node.replaceChildren();
    };
  }, [avatarUrl]);

  // Mood from Cam status
  useEffect(() => {
    const head = headRef.current;
    if (!head || !ready) return;
    try {
      head.setMood?.(moodFor(expr));
    } catch {
      /* mood optional */
    }
  }, [expr, ready]);

  // Speak → real viseme lip-sync (timed silent buffer + word visemes)
  useEffect(() => {
    const head = headRef.current;
    if (!head || !ready || !speakingText) return;
    if (speakingText === lastSpokenRef.current) return;
    lastSpokenRef.current = speakingText;

    const durationMs = estimateSpeechMs(speakingText);
    const timing = wordsTiming(speakingText, durationMs);

    (async () => {
      try {
        await head.audioCtx?.resume?.();
        // Re-assert lipsync in case dynamic import raced and failed
        if (!head.lipsync?.en) {
          head.lipsync = head.lipsync || {};
          head.lipsync.en = new LipsyncEn();
        }
        const audio = makeSilentBuffer(head.audioCtx, durationMs);
        head.stopSpeaking?.();
        head.speakAudio(
          {
            audio,
            words: timing.words,
            wtimes: timing.wtimes,
            wdurations: timing.wdurations,
          },
          { lipsyncLang: 'en' },
        );
      } catch (e) {
        console.warn('Cam TalkingHead speakAudio failed', e);
      }
    })();
  }, [speakingText, ready]);

  // Reset spoken ref when utterance ends
  useEffect(() => {
    if (!speakingText) {
      lastSpokenRef.current = '';
      try {
        headRef.current?.stopSpeaking?.();
      } catch {
        /* ignore */
      }
    }
  }, [speakingText]);

  return (
    <div
      className={`cam-face-live expr-${expr}${listening ? ' live' : ''}${
        speakingText ? ' mouth-open' : ''
      }${ready ? ' ready' : ''}`}
      style={{ ['--level' as string]: String(level) } as CSSProperties}
      role="img"
      aria-label={`Cam, ${expr}`}
    >
      <div className="cam-face-live-inner cam-face-talkinghead">
        <div ref={mountRef} className="cam-face-th-mount" />
        {!ready && !loadError ? (
          <p className="cam-face-loading">Loading Cam… {loadPct ? `${loadPct}%` : ''}</p>
        ) : null}
        {loadError ? (
          <div className="cam-face-fallback">
            <img src="/identity/persona/cam-face.jpg" alt="Cam" />
            <p>3D presence unavailable — still portrait</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
