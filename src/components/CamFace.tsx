/**
 * CamFace — photo presence with speech-synced mouth + expressive brows/eyes.
 */
import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import {
  buildVisemeSchedule,
  estimateSpeechMs,
  expressionFromStatus,
  sampleViseme,
  type FaceExpression,
  type VisemeId,
} from '@/lib/visemes';
import type { CamVoiceStatus } from '@/hooks/useCamVoice';

interface CamFaceProps {
  status: CamVoiceStatus;
  listening: boolean;
  level: number;
  typing?: boolean;
  /** Text currently being spoken (drives visemes). */
  speakingText?: string;
  /** 0..1 progress through utterance from voice hook; -1 = drive locally. */
  speechProgress?: number;
  src?: string;
}

interface FacePose {
  mouthOpen: number;
  mouthWidth: number;
  smile: number;
  brow: number; // -1 knit … +1 raised
  lid: number; // 0 open … 1 closed
  gazeX: number;
  gazeY: number;
  cheek: number;
  headTilt: number;
  headNod: number;
  viseme: VisemeId;
}

const MOUTH_PATHS: Record<VisemeId, string> = {
  rest: 'M 38 62 Q 50 64 62 62',
  closed: 'M 40 62 Q 50 63 60 62',
  smile: 'M 36 61 Q 50 68 64 61',
  wide: 'M 34 61 Q 50 66 66 61 Q 50 70 34 61',
  open: 'M 38 58 Q 50 57 62 58 Q 64 64 50 72 Q 36 64 38 58',
  round: 'M 44 58 Q 50 57 56 58 Q 58 64 50 70 Q 42 64 44 58',
  narrow: 'M 42 61 Q 50 62 58 61 Q 50 66 42 61',
  teeth: 'M 36 60 Q 50 62 64 60 L 64 64 Q 50 67 36 64 Z',
};

function basePose(expr: FaceExpression): FacePose {
  switch (expr) {
    case 'listen':
      return {
        mouthOpen: 0.05,
        mouthWidth: 1,
        smile: 0.35,
        brow: 0.45,
        lid: 0.05,
        gazeX: 0,
        gazeY: 0.05,
        cheek: 0.15,
        headTilt: -1.5,
        headNod: 1,
        viseme: 'smile',
      };
    case 'think':
      return {
        mouthOpen: 0.02,
        mouthWidth: 0.9,
        smile: 0.05,
        brow: -0.55,
        lid: 0.18,
        gazeX: 0.35,
        gazeY: -0.15,
        cheek: 0,
        headTilt: 3,
        headNod: -1,
        viseme: 'rest',
      };
    case 'type':
      return {
        mouthOpen: 0.04,
        mouthWidth: 1,
        smile: 0.4,
        brow: 0.15,
        lid: 0.08,
        gazeX: 0.2,
        gazeY: 0.1,
        cheek: 0.2,
        headTilt: 1,
        headNod: 0,
        viseme: 'smile',
      };
    case 'speak':
      return {
        mouthOpen: 0.3,
        mouthWidth: 1.05,
        smile: 0.25,
        brow: 0.2,
        lid: 0.06,
        gazeX: 0,
        gazeY: 0,
        cheek: 0.25,
        headTilt: 0,
        headNod: 0,
        viseme: 'open',
      };
    case 'smile':
      return {
        mouthOpen: 0.08,
        mouthWidth: 1.1,
        smile: 0.85,
        brow: 0.2,
        lid: 0.12,
        gazeX: 0,
        gazeY: 0,
        cheek: 0.45,
        headTilt: -2,
        headNod: 0,
        viseme: 'smile',
      };
    case 'concern':
      return {
        mouthOpen: 0.06,
        mouthWidth: 0.85,
        smile: -0.2,
        brow: -0.4,
        lid: 0.15,
        gazeX: 0,
        gazeY: 0.1,
        cheek: 0,
        headTilt: 2,
        headNod: -1,
        viseme: 'narrow',
      };
    case 'ignored':
      return {
        mouthOpen: 0.03,
        mouthWidth: 0.9,
        smile: 0.1,
        brow: -0.2,
        lid: 0.2,
        gazeX: -0.2,
        gazeY: 0.05,
        cheek: 0,
        headTilt: -2,
        headNod: 0,
        viseme: 'rest',
      };
    default:
      return {
        mouthOpen: 0.04,
        mouthWidth: 1,
        smile: 0.3,
        brow: 0.05,
        lid: 0.08,
        gazeX: 0,
        gazeY: 0,
        cheek: 0.1,
        headTilt: 0,
        headNod: 0,
        viseme: 'smile',
      };
  }
}

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

function mixPose(a: FacePose, b: FacePose, t: number): FacePose {
  return {
    mouthOpen: lerp(a.mouthOpen, b.mouthOpen, t),
    mouthWidth: lerp(a.mouthWidth, b.mouthWidth, t),
    smile: lerp(a.smile, b.smile, t),
    brow: lerp(a.brow, b.brow, t),
    lid: lerp(a.lid, b.lid, t),
    gazeX: lerp(a.gazeX, b.gazeX, t),
    gazeY: lerp(a.gazeY, b.gazeY, t),
    cheek: lerp(a.cheek, b.cheek, t),
    headTilt: lerp(a.headTilt, b.headTilt, t),
    headNod: lerp(a.headNod, b.headNod, t),
    viseme: t > 0.5 ? b.viseme : a.viseme,
  };
}

export function CamFace({
  status,
  listening,
  level,
  typing = false,
  speakingText = '',
  speechProgress = -1,
  src = '/identity/persona/cam-face.jpg',
}: CamFaceProps) {
  const expr = expressionFromStatus(status, typing);
  const schedule = useMemo(
    () => (speakingText ? buildVisemeSchedule(speakingText) : []),
    [speakingText],
  );
  const [pose, setPose] = useState<FacePose>(() => basePose('idle'));
  const [blink, setBlink] = useState(0);
  const rafRef = useRef(0);
  const speakStartedRef = useRef(0);
  const speakDurRef = useRef(2500);
  const prevExprRef = useRef<FaceExpression>('idle');
  const blendRef = useRef({ from: basePose('idle'), t: 1 });
  const poseRef = useRef(pose);
  poseRef.current = pose;

  // Blink loop
  useEffect(() => {
    let timeout = 0;
    const tick = () => {
      setBlink(1);
      window.setTimeout(() => setBlink(0), 120);
      timeout = window.setTimeout(tick, 2200 + Math.random() * 3200);
    };
    timeout = window.setTimeout(tick, 1600);
    return () => window.clearTimeout(timeout);
  }, []);

  // Expression blend when status changes
  useEffect(() => {
    if (prevExprRef.current === expr) return;
    blendRef.current = { from: poseRef.current, t: 0 };
    prevExprRef.current = expr;
  }, [expr]);

  // Speech duration estimate when speaking text arrives
  useEffect(() => {
    if (status !== 'speaking' || !speakingText) return;
    speakStartedRef.current = performance.now();
    speakDurRef.current = estimateSpeechMs(speakingText);
  }, [status, speakingText]);

  // Animation frame: blend expression + visemes + mic level + blink
  useEffect(() => {
    const loop = (now: number) => {
      const target = basePose(expr);
      const blend = blendRef.current;
      if (blend.t < 1) {
        blend.t = Math.min(1, blend.t + 0.08);
      }
      let next = mixPose(blend.from, target, blend.t);

      // Mic level while listening — subtle jaw / brow
      if (expr === 'listen' || expr === 'idle') {
        next = {
          ...next,
          brow: next.brow + level * 0.25,
          mouthOpen: next.mouthOpen + level * 0.08,
          headNod: next.headNod + level * 2,
        };
      }

      if (expr === 'speak' && speakingText) {
        const timed = Math.min(
          1,
          (now - speakStartedRef.current) / Math.max(1, speakDurRef.current),
        );
        // Boundary events resync when available; timed keeps the mouth moving otherwise
        const localP =
          speechProgress > 0.02 ? Math.max(speechProgress, timed * 0.85) : timed;
        const sample = sampleViseme(schedule, localP);
        // Natural jaw flutter on top of viseme
        const flutter = 0.08 * Math.sin(now / 45) + 0.05 * Math.sin(now / 27);
        next = {
          ...next,
          viseme: sample.id,
          mouthOpen: Math.min(1, sample.open + Math.max(0, flutter)),
          mouthWidth: sample.id === 'round' || sample.id === 'narrow' ? 0.85 : 1.08,
          smile: sample.id === 'smile' || sample.id === 'wide' ? 0.55 : 0.2,
          brow: 0.15 + sample.open * 0.35 + 0.08 * Math.sin(now / 180),
          cheek: 0.2 + sample.open * 0.25,
          headNod: Math.sin(now / 140) * 1.8,
          headTilt: Math.sin(now / 320) * 2.2,
          gazeY: 0.02 * Math.sin(now / 400),
        };
      } else if (expr === 'think') {
        next = {
          ...next,
          gazeX: 0.25 + 0.15 * Math.sin(now / 900),
          brow: -0.45 + 0.08 * Math.sin(now / 700),
          headTilt: 2.5 + Math.sin(now / 1100),
        };
      } else if (expr === 'type') {
        next = {
          ...next,
          mouthOpen: 0.04 + 0.03 * Math.abs(Math.sin(now / 90)),
          headNod: Math.sin(now / 200) * 0.8,
          gazeY: 0.08,
        };
      } else if (expr === 'idle' || expr === 'listen') {
        next = {
          ...next,
          headTilt: next.headTilt + Math.sin(now / 2400) * 1.5,
          headNod: next.headNod + Math.sin(now / 2800) * 1.2,
          smile: next.smile + 0.05 * Math.sin(now / 1800),
        };
      }

      next = { ...next, lid: Math.max(next.lid, blink) };
      setPose(next);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [expr, level, speakingText, speechProgress, schedule, blink]);

  const mouthD = MOUTH_PATHS[pose.viseme] || MOUTH_PATHS.rest;
  const eyeScaleY = 1 - pose.lid * 0.92;
  const browY = -pose.brow * 3.2;

  return (
    <div
      className={`cam-face-live expr-${expr}${listening ? ' live' : ''}`}
      style={
        {
          ['--mouth-open' as string]: String(pose.mouthOpen),
          ['--level' as string]: String(level),
          ['--head-tilt' as string]: `${pose.headTilt}deg`,
          ['--head-nod' as string]: `${pose.headNod}px`,
        } as CSSProperties
      }
    >
      <div className="cam-face-live-inner">
        <img
          className="cam-face-photo"
          src={src}
          alt="Cam"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.opacity = '0.3';
          }}
        />
        <svg
          className="cam-face-overlay"
          viewBox="0 0 100 100"
          aria-hidden
          focusable="false"
        >
          <defs>
            <radialGradient id="camCheek" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(227, 120, 120, 0.35)" />
              <stop offset="100%" stopColor="rgba(227, 120, 120, 0)" />
            </radialGradient>
            <clipPath id="camFaceClip">
              <circle cx="50" cy="50" r="48" />
            </clipPath>
          </defs>

          {/* Soft cheeks when smiling / speaking */}
          <ellipse
            className="cam-cheek left"
            cx="28"
            cy="58"
            rx={6 + pose.cheek * 3}
            ry={4 + pose.cheek * 2}
            fill="url(#camCheek)"
            opacity={0.25 + pose.cheek * 0.45}
          />
          <ellipse
            className="cam-cheek right"
            cx="72"
            cy="58"
            rx={6 + pose.cheek * 3}
            ry={4 + pose.cheek * 2}
            fill="url(#camCheek)"
            opacity={0.25 + pose.cheek * 0.45}
          />

          {/* Brows */}
          <path
            className="cam-brow left"
            d="M 28 38 Q 35 36 42 38"
            transform={`translate(0 ${browY}) rotate(${pose.brow * -6} 35 37)`}
          />
          <path
            className="cam-brow right"
            d="M 58 38 Q 65 36 72 38"
            transform={`translate(0 ${browY}) rotate(${pose.brow * 6} 65 37)`}
          />

          {/* Eye lids / gaze — soft overlays so photo eyes still read */}
          <g
            className="cam-eye left"
            transform={`translate(${pose.gazeX * 2} ${pose.gazeY * 2}) scale(1 ${eyeScaleY})`}
            style={{ transformOrigin: '34px 46px' }}
          >
            <ellipse cx="34" cy="46" rx="5.5" ry="3.2" className="cam-lid" />
          </g>
          <g
            className="cam-eye right"
            transform={`translate(${pose.gazeX * 2} ${pose.gazeY * 2}) scale(1 ${eyeScaleY})`}
            style={{ transformOrigin: '66px 46px' }}
          >
            <ellipse cx="66" cy="46" rx="5.5" ry="3.2" className="cam-lid" />
          </g>

          {/* Mouth — scales with jaw open */}
          <g
            className="cam-mouth-group"
            transform={`translate(50 62) scale(${pose.mouthWidth} ${0.55 + pose.mouthOpen * 1.35}) translate(-50 -62)`}
          >
            <path className="cam-mouth-fill" d={mouthD} />
            {pose.mouthOpen > 0.28 ? (
              <ellipse
                className="cam-mouth-inner"
                cx="50"
                cy={64 + pose.mouthOpen * 4}
                rx={4 + pose.mouthOpen * 5}
                ry={2 + pose.mouthOpen * 5}
              />
            ) : null}
          </g>
        </svg>
      </div>
    </div>
  );
}
