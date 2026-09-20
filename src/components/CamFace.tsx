/**
 * CamFace — original illustrated Cam. No photo.
 * One SVG character: brows, lids, gaze, cheeks, jaw, and viseme mouth.
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
  speakingText?: string;
  speechProgress?: number;
}

interface FacePose {
  mouthOpen: number;
  mouthSpread: number;
  smile: number;
  brow: number;
  lid: number;
  gazeX: number;
  gazeY: number;
  jaw: number;
  headTilt: number;
  headNod: number;
  cheek: number;
  viseme: VisemeId;
}

/** Mouth path set in face space (viewBox 0 0 100 120). */
const MOUTH: Record<VisemeId, string> = {
  rest: 'M 40 86 Q 50 88 60 86',
  closed: 'M 41 86.5 Q 50 87.2 59 86.5',
  smile: 'M 38 85.5 Q 50 91 62 85.5',
  wide: 'M 36 85 Q 50 89 64 85 Q 50 93 36 85',
  open: 'M 40 83 Q 50 82 60 83 Q 63 88 50 96 Q 37 88 40 83',
  round: 'M 44 83.5 Q 50 82.5 56 83.5 Q 58 89 50 95 Q 42 89 44 83.5',
  narrow: 'M 43 85.5 Q 50 86.5 57 85.5 Q 50 90 43 85.5',
  teeth: 'M 38 84 Q 50 85.5 62 84 L 62 88 Q 50 91 38 88 Z',
};

function basePose(expr: FaceExpression): FacePose {
  switch (expr) {
    case 'listen':
      return {
        mouthOpen: 0.06,
        mouthSpread: 1.05,
        smile: 0.45,
        brow: 0.55,
        lid: 0.04,
        gazeX: 0,
        gazeY: 0.04,
        jaw: 0.03,
        headTilt: -2.5,
        headNod: 1.2,
        cheek: 0.25,
        viseme: 'smile',
      };
    case 'think':
      return {
        mouthOpen: 0.03,
        mouthSpread: 0.9,
        smile: 0.05,
        brow: -0.7,
        lid: 0.2,
        gazeX: 0.45,
        gazeY: -0.12,
        jaw: 0.02,
        headTilt: 5,
        headNod: -1.5,
        cheek: 0.05,
        viseme: 'rest',
      };
    case 'type':
      return {
        mouthOpen: 0.05,
        mouthSpread: 1,
        smile: 0.35,
        brow: 0.2,
        lid: 0.1,
        gazeX: 0.18,
        gazeY: 0.1,
        jaw: 0.03,
        headTilt: 1.5,
        headNod: 0.5,
        cheek: 0.2,
        viseme: 'smile',
      };
    case 'speak':
      return {
        mouthOpen: 0.4,
        mouthSpread: 1.08,
        smile: 0.2,
        brow: 0.25,
        lid: 0.06,
        gazeX: 0,
        gazeY: 0,
        jaw: 0.35,
        headTilt: 0,
        headNod: 0,
        cheek: 0.3,
        viseme: 'open',
      };
    case 'concern':
      return {
        mouthOpen: 0.07,
        mouthSpread: 0.85,
        smile: -0.2,
        brow: -0.45,
        lid: 0.16,
        gazeX: 0,
        gazeY: 0.08,
        jaw: 0.04,
        headTilt: 2,
        headNod: -1,
        cheek: 0,
        viseme: 'narrow',
      };
    case 'ignored':
      return {
        mouthOpen: 0.04,
        mouthSpread: 0.92,
        smile: 0.08,
        brow: -0.25,
        lid: 0.18,
        gazeX: -0.25,
        gazeY: 0.05,
        jaw: 0.02,
        headTilt: -2,
        headNod: 0,
        cheek: 0.05,
        viseme: 'rest',
      };
    case 'smile':
      return {
        mouthOpen: 0.1,
        mouthSpread: 1.15,
        smile: 0.85,
        brow: 0.25,
        lid: 0.14,
        gazeX: 0,
        gazeY: 0,
        jaw: 0.06,
        headTilt: -2,
        headNod: 0,
        cheek: 0.5,
        viseme: 'smile',
      };
    default:
      return {
        mouthOpen: 0.05,
        mouthSpread: 1,
        smile: 0.32,
        brow: 0.08,
        lid: 0.08,
        gazeX: 0,
        gazeY: 0,
        jaw: 0.02,
        headTilt: 0,
        headNod: 0,
        cheek: 0.15,
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
    mouthSpread: lerp(a.mouthSpread, b.mouthSpread, t),
    smile: lerp(a.smile, b.smile, t),
    brow: lerp(a.brow, b.brow, t),
    lid: lerp(a.lid, b.lid, t),
    gazeX: lerp(a.gazeX, b.gazeX, t),
    gazeY: lerp(a.gazeY, b.gazeY, t),
    jaw: lerp(a.jaw, b.jaw, t),
    headTilt: lerp(a.headTilt, b.headTilt, t),
    headNod: lerp(a.headNod, b.headNod, t),
    cheek: lerp(a.cheek, b.cheek, t),
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

  useEffect(() => {
    let timeout = 0;
    const tick = () => {
      setBlink(1);
      window.setTimeout(() => setBlink(0), 130);
      timeout = window.setTimeout(tick, 2400 + Math.random() * 3000);
    };
    timeout = window.setTimeout(tick, 1400);
    return () => window.clearTimeout(timeout);
  }, []);

  useEffect(() => {
    if (prevExprRef.current === expr) return;
    blendRef.current = { from: poseRef.current, t: 0 };
    prevExprRef.current = expr;
  }, [expr]);

  useEffect(() => {
    if (!speakingText) return;
    speakStartedRef.current = performance.now();
    speakDurRef.current = estimateSpeechMs(speakingText);
  }, [speakingText]);

  useEffect(() => {
    const loop = (now: number) => {
      const target = basePose(expr);
      const blend = blendRef.current;
      if (blend.t < 1) blend.t = Math.min(1, blend.t + 0.1);
      let next = mixPose(blend.from, target, blend.t);

      if (expr === 'listen' || expr === 'idle') {
        next = {
          ...next,
          brow: next.brow + level * 0.28,
          mouthOpen: next.mouthOpen + level * 0.1,
          jaw: next.jaw + level * 0.08,
          headNod: next.headNod + level * 2.2,
        };
      }

      const speaking = Boolean(speakingText) || expr === 'speak';
      if (speaking && speakingText) {
        const timed = Math.min(
          1,
          (now - speakStartedRef.current) / Math.max(1, speakDurRef.current),
        );
        const localP =
          speechProgress > 0.02 ? Math.max(speechProgress, timed * 0.85) : timed;
        const sample = sampleViseme(schedule, localP);
        const flutter = 0.1 * Math.sin(now / 38) + 0.07 * Math.sin(now / 22);
        const open = Math.min(1, Math.max(0.18, sample.open + Math.max(0, flutter)));
        next = {
          ...next,
          viseme: sample.id,
          mouthOpen: open,
          mouthSpread:
            sample.id === 'round' || sample.id === 'narrow'
              ? 0.82
              : sample.id === 'wide' || sample.id === 'smile'
                ? 1.22
                : 1.08,
          smile: sample.id === 'smile' || sample.id === 'wide' ? 0.5 : 0.18,
          jaw: open * 0.95,
          cheek: 0.25 + open * 0.3,
          brow: 0.22 + open * 0.4 + 0.08 * Math.sin(now / 150),
          headNod: Math.sin(now / 100) * 4.5,
          headTilt: Math.sin(now / 210) * 5.5,
          gazeY: 0.03 * Math.sin(now / 380),
          lid: 0.05,
        };
      } else if (expr === 'think') {
        next = {
          ...next,
          gazeX: 0.35 + 0.2 * Math.sin(now / 820),
          brow: -0.6 + 0.12 * Math.sin(now / 640),
          headTilt: 4 + Math.sin(now / 980) * 1.8,
        };
      } else if (expr === 'type') {
        next = {
          ...next,
          mouthOpen: 0.05 + 0.035 * Math.abs(Math.sin(now / 80)),
          jaw: 0.03 + 0.02 * Math.abs(Math.sin(now / 80)),
          headNod: Math.sin(now / 180) * 1.2,
          gazeY: 0.1,
        };
      } else {
        next = {
          ...next,
          headTilt: next.headTilt + Math.sin(now / 2200) * 2,
          headNod: next.headNod + Math.sin(now / 2600) * 1.6,
          smile: next.smile + 0.05 * Math.sin(now / 1600),
          gazeX: 0.08 * Math.sin(now / 3200),
        };
      }

      next = { ...next, lid: Math.max(next.lid, blink) };
      setPose(next);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [expr, level, speakingText, speechProgress, schedule, blink]);

  const mouthD = MOUTH[pose.viseme] || MOUTH.rest;
  const eyeOpen = 1 - pose.lid * 0.92;
  const browLift = pose.brow * 2.8;
  const jawY = pose.jaw * 3.2;
  const showTeeth = pose.viseme === 'teeth' || pose.mouthOpen > 0.32;
  const showTongue = pose.mouthOpen > 0.45 && pose.viseme === 'open';

  return (
    <div
      className={`cam-face-live expr-${expr}${listening ? ' live' : ''}${
        pose.mouthOpen > 0.22 ? ' mouth-open' : ''
      }`}
      style={
        {
          ['--head-tilt' as string]: `${pose.headTilt}deg`,
          ['--head-nod' as string]: `${pose.headNod}px`,
          ['--level' as string]: String(Math.min(1, Math.max(0, level))),
        } as CSSProperties
      }
      role="img"
      aria-label={`Cam, ${expr}`}
    >
      <div className="cam-face-live-inner">
        <svg className="cam-face-svg" viewBox="0 0 100 120" aria-hidden>
          <defs>
            <linearGradient id="camSkin" x1="0%" y1="0%" x2="30%" y2="100%">
              <stop offset="0%" stopColor="#f3d4c2" />
              <stop offset="55%" stopColor="#e8bda8" />
              <stop offset="100%" stopColor="#d9a690" />
            </linearGradient>
            <linearGradient id="camHair" x1="20%" y1="0%" x2="80%" y2="100%">
              <stop offset="0%" stopColor="#3a2a24" />
              <stop offset="45%" stopColor="#5c4036" />
              <stop offset="100%" stopColor="#2a1c18" />
            </linearGradient>
            <linearGradient id="camHairShine" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(255,220,190,0)" />
              <stop offset="45%" stopColor="rgba(255,220,190,0.18)" />
              <stop offset="100%" stopColor="rgba(255,220,190,0)" />
            </linearGradient>
            <radialGradient id="camCheekGrad" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(220,110,110,0.45)" />
              <stop offset="100%" stopColor="rgba(220,110,110,0)" />
            </radialGradient>
            <radialGradient id="camEyeWhite" cx="40%" cy="35%" r="65%">
              <stop offset="0%" stopColor="#ffffff" />
              <stop offset="100%" stopColor="#e8eef0" />
            </radialGradient>
          </defs>

          {/* Soft shoulder / neck */}
          <path
            d="M 28 108 Q 50 100 72 108 L 78 120 L 22 120 Z"
            fill="#2a3a40"
            opacity="0.9"
          />
          <ellipse cx="50" cy="104" rx="12" ry="8" fill="url(#camSkin)" />

          {/* Hair back */}
          <path
            d="M 18 48 Q 12 20 32 12 Q 50 4 68 12 Q 88 20 82 48 Q 90 78 78 102 Q 70 88 68 70 Q 50 78 32 70 Q 30 88 22 102 Q 10 78 18 48 Z"
            fill="url(#camHair)"
          />

          {/* Head group — tilts as one */}
          <g transform={`rotate(${pose.headTilt.toFixed(2)} 50 70) translate(0 ${pose.headNod.toFixed(2)})`}>
            {/* Face */}
            <ellipse cx="50" cy="58" rx="32" ry="38" fill="url(#camSkin)" />

            {/* Soft face shade */}
            <ellipse
              cx="50"
              cy="68"
              rx="26"
              ry="28"
              fill="rgba(180,110,90,0.12)"
            />

            {/* Cheeks */}
            <ellipse
              cx="30"
              cy="68"
              rx={7 + pose.cheek * 2}
              ry={5 + pose.cheek}
              fill="url(#camCheekGrad)"
              opacity={0.35 + pose.cheek * 0.5}
            />
            <ellipse
              cx="70"
              cy="68"
              rx={7 + pose.cheek * 2}
              ry={5 + pose.cheek}
              fill="url(#camCheekGrad)"
              opacity={0.35 + pose.cheek * 0.5}
            />

            {/* Nose */}
            <path
              d="M 50 58 Q 52 66 54 70"
              fill="none"
              stroke="rgba(160,100,80,0.45)"
              strokeWidth="1.2"
              strokeLinecap="round"
            />
            <ellipse cx="48.5" cy="70" rx="1.4" ry="1" fill="rgba(160,100,80,0.25)" />
            <ellipse cx="51.5" cy="70" rx="1.4" ry="1" fill="rgba(160,100,80,0.25)" />

            {/* Brows */}
            <path
              d="M 28 44 Q 36 40 44 43"
              fill="none"
              stroke="#3a2a24"
              strokeWidth="2.2"
              strokeLinecap="round"
              transform={`translate(0 ${(-browLift).toFixed(2)}) rotate(${(pose.brow * -8).toFixed(2)} 36 42)`}
            />
            <path
              d="M 56 43 Q 64 40 72 44"
              fill="none"
              stroke="#3a2a24"
              strokeWidth="2.2"
              strokeLinecap="round"
              transform={`translate(0 ${(-browLift).toFixed(2)}) rotate(${(pose.brow * 8).toFixed(2)} 64 42)`}
            />

            {/* Eyes */}
            <g transform={`translate(${(pose.gazeX * 2.5).toFixed(2)} ${(pose.gazeY * 2).toFixed(2)})`}>
              <g transform={`translate(36 52) scale(1 ${eyeOpen.toFixed(3)}) translate(-36 -52)`}>
                <ellipse cx="36" cy="52" rx="8.2" ry="4.6" fill="url(#camEyeWhite)" />
                <circle cx={36 + pose.gazeX * 1.5} cy={52.2 + pose.gazeY} r="3.4" fill="#1f7a78" />
                <circle cx={36 + pose.gazeX * 1.5} cy={52.2 + pose.gazeY} r="1.7" fill="#0a1418" />
                <circle
                  cx={35.2 + pose.gazeX * 1.5}
                  cy={51 + pose.gazeY}
                  r="0.75"
                  fill="#fff"
                  opacity="0.95"
                />
              </g>
              <g transform={`translate(64 52) scale(1 ${eyeOpen.toFixed(3)}) translate(-64 -52)`}>
                <ellipse cx="64" cy="52" rx="8.2" ry="4.6" fill="url(#camEyeWhite)" />
                <circle cx={64 + pose.gazeX * 1.5} cy={52.2 + pose.gazeY} r="3.4" fill="#1f7a78" />
                <circle cx={64 + pose.gazeX * 1.5} cy={52.2 + pose.gazeY} r="1.7" fill="#0a1418" />
                <circle
                  cx={63.2 + pose.gazeX * 1.5}
                  cy={51 + pose.gazeY}
                  r="0.75"
                  fill="#fff"
                  opacity="0.95"
                />
              </g>
            </g>

            {/* Upper lids when blinking / squinting */}
            <path
              d="M 28 48 Q 36 46 44 48"
              fill="none"
              stroke="rgba(210,160,140,0.85)"
              strokeWidth={1 + pose.lid * 4}
              strokeLinecap="round"
              opacity={0.2 + pose.lid * 0.8}
            />
            <path
              d="M 56 48 Q 64 46 72 48"
              fill="none"
              stroke="rgba(210,160,140,0.85)"
              strokeWidth={1 + pose.lid * 4}
              strokeLinecap="round"
              opacity={0.2 + pose.lid * 0.8}
            />

            {/* Jaw / mouth group */}
            <g transform={`translate(0 ${jawY.toFixed(2)})`}>
              {showTeeth ? (
                <rect
                  x={50 - 8 * pose.mouthSpread}
                  y="84.5"
                  width={16 * pose.mouthSpread}
                  height={Math.max(2, pose.mouthOpen * 4)}
                  rx="1"
                  fill="#f5efe8"
                  opacity="0.95"
                />
              ) : null}
              {showTongue ? (
                <ellipse
                  cx="50"
                  cy={90 + pose.mouthOpen * 2}
                  rx="4"
                  ry="2.5"
                  fill="#c45a6a"
                  opacity="0.85"
                />
              ) : null}
              <path
                d={mouthD}
                fill={pose.mouthOpen > 0.22 ? '#5a2030' : 'none'}
                stroke="#8a4050"
                strokeWidth={pose.mouthOpen > 0.15 ? 1.8 : 2.4}
                strokeLinecap="round"
                strokeLinejoin="round"
                transform={`translate(50 86) scale(${pose.mouthSpread.toFixed(3)} ${(0.7 + pose.mouthOpen * 0.9).toFixed(3)}) translate(-50 -86)`}
              />
              <path
                d={pose.smile > 0.25 ? 'M 40 85.8 Q 50 88.5 60 85.8' : 'M 42 86 Q 50 87 58 86'}
                fill="none"
                stroke="rgba(200,120,130,0.45)"
                strokeWidth="1"
                strokeLinecap="round"
                opacity={pose.mouthOpen < 0.2 ? 0.8 : 0.25}
              />
            </g>

            {/* Bangs / front hair */}
            <path
              d="M 22 42 Q 28 18 50 16 Q 72 18 78 42 Q 70 28 50 26 Q 30 28 22 42 Z"
              fill="url(#camHair)"
            />
            <path
              d="M 26 36 Q 40 22 55 28 Q 48 34 40 38 Q 32 40 26 36 Z"
              fill="url(#camHairShine)"
            />
            <path
              d="M 58 28 Q 70 24 76 38 Q 68 36 60 34 Z"
              fill="url(#camHairShine)"
              opacity="0.7"
            />
          </g>
        </svg>
      </div>
    </div>
  );
}
