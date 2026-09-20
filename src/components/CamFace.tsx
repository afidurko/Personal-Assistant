/**
 * CamFace — photo presence with clearly visible speech mouth + expressions.
 * Lower-face jaw warp + bold mouth shapes so motion reads on a still photo.
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
  src?: string;
}

interface FacePose {
  mouthOpen: number;
  mouthSpread: number;
  smile: number;
  brow: number;
  lid: number;
  gazeX: number;
  jaw: number;
  headTilt: number;
  headNod: number;
  viseme: VisemeId;
}

function basePose(expr: FaceExpression): FacePose {
  switch (expr) {
    case 'listen':
      return {
        mouthOpen: 0.06,
        mouthSpread: 1.05,
        smile: 0.4,
        brow: 0.55,
        lid: 0.04,
        gazeX: 0,
        jaw: 0.04,
        headTilt: -2,
        headNod: 1.5,
        viseme: 'smile',
      };
    case 'think':
      return {
        mouthOpen: 0.03,
        mouthSpread: 0.88,
        smile: 0.05,
        brow: -0.65,
        lid: 0.22,
        gazeX: 0.4,
        jaw: 0.02,
        headTilt: 4,
        headNod: -1,
        viseme: 'rest',
      };
    case 'type':
      return {
        mouthOpen: 0.05,
        mouthSpread: 1,
        smile: 0.35,
        brow: 0.2,
        lid: 0.1,
        gazeX: 0.15,
        jaw: 0.03,
        headTilt: 1.5,
        headNod: 0,
        viseme: 'smile',
      };
    case 'speak':
      return {
        mouthOpen: 0.45,
        mouthSpread: 1.1,
        smile: 0.2,
        brow: 0.25,
        lid: 0.06,
        gazeX: 0,
        jaw: 0.35,
        headTilt: 0,
        headNod: 0,
        viseme: 'open',
      };
    case 'concern':
      return {
        mouthOpen: 0.08,
        mouthSpread: 0.82,
        smile: -0.15,
        brow: -0.5,
        lid: 0.18,
        gazeX: 0,
        jaw: 0.05,
        headTilt: 2,
        headNod: -1,
        viseme: 'narrow',
      };
    case 'ignored':
      return {
        mouthOpen: 0.04,
        mouthSpread: 0.9,
        smile: 0.1,
        brow: -0.25,
        lid: 0.2,
        gazeX: -0.2,
        jaw: 0.02,
        headTilt: -2,
        headNod: 0,
        viseme: 'rest',
      };
    default:
      return {
        mouthOpen: 0.04,
        mouthSpread: 1,
        smile: 0.28,
        brow: 0.08,
        lid: 0.08,
        gazeX: 0,
        jaw: 0.02,
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
    mouthSpread: lerp(a.mouthSpread, b.mouthSpread, t),
    smile: lerp(a.smile, b.smile, t),
    brow: lerp(a.brow, b.brow, t),
    lid: lerp(a.lid, b.lid, t),
    gazeX: lerp(a.gazeX, b.gazeX, t),
    jaw: lerp(a.jaw, b.jaw, t),
    headTilt: lerp(a.headTilt, b.headTilt, t),
    headNod: lerp(a.headNod, b.headNod, t),
    viseme: t > 0.5 ? b.viseme : a.viseme,
  };
}

/** Viseme → mouth ellipse geometry (percent of face). */
function mouthGeom(v: VisemeId, open: number, spread: number, smile: number) {
  const baseW = 14 * spread;
  const baseH = 2.2 + open * 14;
  switch (v) {
    case 'closed':
      return { w: baseW * 0.85, h: 1.2, round: 50, y: 68 };
    case 'smile':
      return { w: baseW * 1.15, h: 2.4 + smile * 2, round: 60, y: 67.5 };
    case 'wide':
      return { w: baseW * 1.25, h: Math.max(4, baseH * 0.75), round: 45, y: 67 };
    case 'round':
      return { w: baseW * 0.7, h: Math.max(6, baseH), round: 50, y: 67 };
    case 'narrow':
      return { w: baseW * 0.65, h: Math.max(3, baseH * 0.55), round: 50, y: 67.5 };
    case 'teeth':
      return { w: baseW * 1.05, h: Math.max(3.5, baseH * 0.55), round: 30, y: 67 };
    case 'open':
      return { w: baseW, h: Math.max(7, baseH), round: 48, y: 66.5 };
    default:
      return { w: baseW * 0.95, h: Math.max(2, baseH * 0.4), round: 50, y: 68 };
  }
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

  useEffect(() => {
    let timeout = 0;
    const tick = () => {
      setBlink(1);
      window.setTimeout(() => setBlink(0), 140);
      timeout = window.setTimeout(tick, 2000 + Math.random() * 2800);
    };
    timeout = window.setTimeout(tick, 1200);
    return () => window.clearTimeout(timeout);
  }, []);

  useEffect(() => {
    if (prevExprRef.current === expr) return;
    blendRef.current = { from: poseRef.current, t: 0 };
    prevExprRef.current = expr;
  }, [expr]);

  useEffect(() => {
    if (status !== 'speaking' || !speakingText) return;
    speakStartedRef.current = performance.now();
    speakDurRef.current = estimateSpeechMs(speakingText);
  }, [status, speakingText]);

  useEffect(() => {
    const loop = (now: number) => {
      const target = basePose(expr);
      const blend = blendRef.current;
      if (blend.t < 1) blend.t = Math.min(1, blend.t + 0.1);
      let next = mixPose(blend.from, target, blend.t);

      if (expr === 'listen' || expr === 'idle') {
        next = {
          ...next,
          brow: next.brow + level * 0.3,
          mouthOpen: next.mouthOpen + level * 0.12,
          jaw: next.jaw + level * 0.1,
          headNod: next.headNod + level * 2.5,
        };
      }

      if (expr === 'speak' && speakingText) {
        const timed = Math.min(
          1,
          (now - speakStartedRef.current) / Math.max(1, speakDurRef.current),
        );
        const localP =
          speechProgress > 0.02 ? Math.max(speechProgress, timed * 0.85) : timed;
        const sample = sampleViseme(schedule, localP);
        const flutter = 0.1 * Math.sin(now / 42) + 0.06 * Math.sin(now / 23);
        const open = Math.min(1, Math.max(0.12, sample.open + Math.max(0, flutter)));
        next = {
          ...next,
          viseme: sample.id,
          mouthOpen: open,
          mouthSpread:
            sample.id === 'round' || sample.id === 'narrow'
              ? 0.78
              : sample.id === 'wide' || sample.id === 'smile'
                ? 1.2
                : 1.05,
          smile: sample.id === 'smile' || sample.id === 'wide' ? 0.55 : 0.15,
          jaw: open * 0.85,
          brow: 0.2 + open * 0.4 + 0.1 * Math.sin(now / 160),
          headNod: Math.sin(now / 130) * 2.4,
          headTilt: Math.sin(now / 280) * 2.8,
          lid: 0.05,
        };
      } else if (expr === 'think') {
        next = {
          ...next,
          gazeX: 0.3 + 0.2 * Math.sin(now / 850),
          brow: -0.55 + 0.1 * Math.sin(now / 650),
          headTilt: 3 + Math.sin(now / 1000) * 1.5,
        };
      } else if (expr === 'type') {
        next = {
          ...next,
          mouthOpen: 0.05 + 0.04 * Math.abs(Math.sin(now / 85)),
          jaw: 0.03 + 0.02 * Math.abs(Math.sin(now / 85)),
          headNod: Math.sin(now / 190) * 1.1,
        };
      } else {
        next = {
          ...next,
          headTilt: next.headTilt + Math.sin(now / 2300) * 1.8,
          headNod: next.headNod + Math.sin(now / 2700) * 1.4,
          smile: next.smile + 0.06 * Math.sin(now / 1700),
        };
      }

      next = { ...next, lid: Math.max(next.lid, blink) };
      setPose(next);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [expr, level, speakingText, speechProgress, schedule, blink]);

  const geom = mouthGeom(pose.viseme, pose.mouthOpen, pose.mouthSpread, pose.smile);
  const showTeeth = pose.viseme === 'teeth' || pose.mouthOpen > 0.35;
  const showInner = pose.mouthOpen > 0.2;

  return (
    <div
      className={`cam-face-live expr-${expr}${listening ? ' live' : ''}${
        pose.mouthOpen > 0.2 ? ' mouth-open' : ''
      }`}
      style={
        {
          ['--mouth-open' as string]: String(pose.mouthOpen),
          ['--mouth-spread' as string]: String(pose.mouthSpread),
          ['--jaw' as string]: String(pose.jaw),
          ['--brow' as string]: String(pose.brow),
          ['--lid' as string]: String(pose.lid),
          ['--gaze-x' as string]: String(pose.gazeX),
          ['--smile' as string]: String(pose.smile),
          ['--level' as string]: String(level),
          ['--head-tilt' as string]: `${pose.headTilt}deg`,
          ['--head-nod' as string]: `${pose.headNod}px`,
          ['--mouth-w' as string]: `${geom.w}%`,
          ['--mouth-h' as string]: `${geom.h}%`,
          ['--mouth-y' as string]: `${geom.y}%`,
          ['--mouth-round' as string]: `${geom.round}%`,
        } as CSSProperties
      }
    >
      <div className="cam-face-live-inner">
        <div className="cam-face-photo-stack" aria-hidden={false}>
          <img
            className="cam-face-photo"
            src={src}
            alt="Cam"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.opacity = '0.3';
            }}
          />
          <div className="cam-face-jaw-warp" aria-hidden>
            <img className="cam-face-photo cam-face-jaw" src={src} alt="" />
          </div>
        </div>

        {/* Brows */}
        <span className="cam-face-brow left" aria-hidden />
        <span className="cam-face-brow right" aria-hidden />

        {/* Lids / blink */}
        <span className="cam-face-lid left" aria-hidden />
        <span className="cam-face-lid right" aria-hidden />

        {/* Cheeks */}
        <span className="cam-face-cheek left" aria-hidden />
        <span className="cam-face-cheek right" aria-hidden />

        {/* Mouth */}
        <div className={`cam-face-mouth viseme-${pose.viseme}`} aria-hidden>
          {showInner ? <span className="cam-face-mouth-inner" /> : null}
          {showTeeth ? <span className="cam-face-teeth" /> : null}
        </div>
      </div>
    </div>
  );
}
