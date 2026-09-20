/**
 * CamFace — Cam’s real portrait, animated by canvas mesh warp.
 * No cartoon. No sticker mouth. The photo itself moves.
 */
import { useEffect, useMemo, useRef, type CSSProperties } from 'react';
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

/** Landmark fractions on cam-face.jpg (cover-cropped square). */
const L = {
  browY: 0.36,
  eyeY: 0.42,
  eyeLX: 0.38,
  eyeRX: 0.62,
  noseY: 0.52,
  mouthY: 0.605,
  chinY: 0.78,
};

function basePose(expr: FaceExpression): FacePose {
  switch (expr) {
    case 'listen':
      return {
        mouthOpen: 0.02,
        mouthSpread: 1.02,
        smile: 0.28,
        brow: 0.35,
        lid: 0.04,
        gazeX: 0,
        jaw: 0.02,
        headTilt: -1.8,
        headNod: 1,
        viseme: 'smile',
      };
    case 'think':
      return {
        mouthOpen: 0.01,
        mouthSpread: 0.96,
        smile: 0.04,
        brow: -0.45,
        lid: 0.14,
        gazeX: 0.28,
        jaw: 0.01,
        headTilt: 3.5,
        headNod: -1,
        viseme: 'rest',
      };
    case 'type':
      return {
        mouthOpen: 0.02,
        mouthSpread: 1,
        smile: 0.22,
        brow: 0.12,
        lid: 0.08,
        gazeX: 0.12,
        jaw: 0.02,
        headTilt: 1,
        headNod: 0.4,
        viseme: 'smile',
      };
    case 'speak':
      return {
        mouthOpen: 0.35,
        mouthSpread: 1.06,
        smile: 0.12,
        brow: 0.18,
        lid: 0.05,
        gazeX: 0,
        jaw: 0.32,
        headTilt: 0,
        headNod: 0,
        viseme: 'open',
      };
    case 'concern':
      return {
        mouthOpen: 0.03,
        mouthSpread: 0.94,
        smile: -0.12,
        brow: -0.35,
        lid: 0.12,
        gazeX: 0,
        jaw: 0.02,
        headTilt: 2,
        headNod: -0.8,
        viseme: 'narrow',
      };
    case 'ignored':
      return {
        mouthOpen: 0.01,
        mouthSpread: 0.97,
        smile: 0.06,
        brow: -0.18,
        lid: 0.15,
        gazeX: -0.18,
        jaw: 0.01,
        headTilt: -1.5,
        headNod: 0,
        viseme: 'rest',
      };
    default:
      return {
        mouthOpen: 0.015,
        mouthSpread: 1,
        smile: 0.2,
        brow: 0.05,
        lid: 0.06,
        gazeX: 0,
        jaw: 0.01,
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

function drawWarpedFace(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement,
  size: number,
  pose: FacePose,
) {
  const w = size;
  const h = size;
  const iw = img.naturalWidth || img.width;
  const ih = img.naturalHeight || img.height;
  if (!iw || !ih) return;

  const scale = Math.max(w / iw, h / ih);
  const dw = iw * scale;
  const dh = ih * scale;
  const ox = (w - dw) / 2;
  const oy = (h - dh) / 2;

  const drawCover = () => {
    ctx.drawImage(img, 0, 0, iw, ih, ox, oy, dw, dh);
  };

  ctx.clearRect(0, 0, w, h);
  ctx.save();
  ctx.beginPath();
  ctx.arc(w / 2, h / 2, w / 2 - 1, 0, Math.PI * 2);
  ctx.closePath();
  ctx.clip();

  ctx.translate(w / 2, h / 2 + pose.headNod);
  ctx.rotate((pose.headTilt * Math.PI) / 180);
  ctx.translate(-w / 2, -h / 2);

  const mouthY = L.mouthY * h;
  const eyeY = L.eyeY * h;
  const browY = L.browY * h;
  const open = Math.min(1, Math.max(0, pose.mouthOpen));
  const jaw = Math.min(1, Math.max(0, pose.jaw));
  const smile = Math.max(0, pose.smile);

  // Full portrait
  drawCover();

  // Brow micro-shift (redraw a band from the same cover mapping)
  if (Math.abs(pose.brow) > 0.08) {
    const bandTop = browY - h * 0.035;
    const bandH = h * 0.06;
    const shift = -pose.brow * h * 0.01;
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, bandTop + Math.min(0, shift), w, bandH + Math.abs(shift) + 2);
    ctx.clip();
    ctx.translate(0, shift);
    drawCover();
    ctx.restore();
  }

  // Blink — soft vertical compress around eyes
  if (pose.lid > 0.06) {
    const eyeH = h * 0.065;
    const eyeTop = eyeY - eyeH * 0.5;
    const squish = 1 - pose.lid * 0.65;
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, eyeTop - 2, w, eyeH + 4);
    ctx.clip();
    ctx.translate(w / 2, eyeY);
    ctx.scale(1, squish);
    ctx.translate(-w / 2, -eyeY);
    drawCover();
    ctx.restore();
  }

  // Lower-face jaw: one clean scale from the mouth line (no strip artifacts)
  const lowerScale = 1 + jaw * 0.11 + open * 0.09;
  const lowerSpread = 1 + (pose.mouthSpread - 1) * 0.35 + smile * 0.02;
  if (lowerScale > 1.01 || Math.abs(lowerSpread - 1) > 0.01) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, mouthY - 1, w, h - mouthY + 2);
    ctx.clip();
    ctx.translate(w / 2, mouthY);
    ctx.scale(lowerSpread, lowerScale);
    ctx.translate(-w / 2, -mouthY);
    drawCover();
    ctx.restore();
  }

  // Soft oral cavity tucked into the lips — very restrained
  if (open > 0.2) {
    const mx = w * 0.5;
    const my = mouthY + h * (0.012 + open * 0.02);
    const mw = w * (0.085 + open * 0.04);
    const mh = h * (0.008 + open * 0.028);
    const grd = ctx.createRadialGradient(mx, my, 0.5, mx, my, mh * 1.6);
    grd.addColorStop(0, `rgba(70, 28, 34, ${0.22 + open * 0.28})`);
    grd.addColorStop(1, 'rgba(50, 20, 26, 0)');
    ctx.beginPath();
    ctx.ellipse(mx, my, mw, mh, 0, 0, Math.PI * 2);
    ctx.fillStyle = grd;
    ctx.fill();
  }

  ctx.restore();
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
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const poseRef = useRef<FacePose>(basePose('idle'));
  const blendRef = useRef({ from: basePose('idle'), t: 1 });
  const prevExprRef = useRef<FaceExpression>('idle');
  const blinkRef = useRef(0);
  const speakStartedRef = useRef(0);
  const speakDurRef = useRef(2500);
  const rafRef = useRef(0);
  const sizeRef = useRef(512);

  // Load portrait
  useEffect(() => {
    const img = new Image();
    img.decoding = 'async';
    img.src = src;
    img.onload = () => {
      imgRef.current = img;
    };
    return () => {
      imgRef.current = null;
    };
  }, [src]);

  // Blink
  useEffect(() => {
    let timeout = 0;
    const tick = () => {
      blinkRef.current = 1;
      window.setTimeout(() => {
        blinkRef.current = 0;
      }, 120);
      timeout = window.setTimeout(tick, 2400 + Math.random() * 3200);
    };
    timeout = window.setTimeout(tick, 1500);
    return () => window.clearTimeout(timeout);
  }, []);

  // Speech clock
  useEffect(() => {
    if (!speakingText) return;
    speakStartedRef.current = performance.now();
    speakDurRef.current = estimateSpeechMs(speakingText);
  }, [speakingText]);

  // Expression blend reset
  useEffect(() => {
    if (prevExprRef.current === expr) return;
    blendRef.current = { from: { ...poseRef.current }, t: 0 };
    prevExprRef.current = expr;
  }, [expr]);

  // Fit canvas to element
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver((entries) => {
      const cr = entries[0]?.contentRect;
      if (!cr) return;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const css = Math.max(180, Math.floor(Math.min(cr.width, cr.height)));
      sizeRef.current = css;
      canvas.width = Math.floor(css * dpr);
      canvas.height = Math.floor(css * dpr);
      canvas.style.width = `${css}px`;
      canvas.style.height = `${css}px`;
    });
    ro.observe(canvas.parentElement || canvas);
    return () => ro.disconnect();
  }, []);

  // Animation loop
  useEffect(() => {
    const loop = (now: number) => {
      const target = basePose(expr);
      const blend = blendRef.current;
      if (blend.t < 1) blend.t = Math.min(1, blend.t + 0.09);
      let next = mixPose(blend.from, target, blend.t);

      if (expr === 'listen' || expr === 'idle') {
        next = {
          ...next,
          brow: next.brow + level * 0.2,
          jaw: next.jaw + level * 0.06,
          mouthOpen: next.mouthOpen + level * 0.05,
          headNod: next.headNod + level * 1.8,
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
        const flutter = 0.08 * Math.sin(now / 40) + 0.05 * Math.sin(now / 23);
        const open = Math.min(1, Math.max(0.08, sample.open + Math.max(0, flutter)));
        next = {
          ...next,
          viseme: sample.id,
          mouthOpen: open,
          jaw: open * 0.92,
          mouthSpread:
            sample.id === 'round' || sample.id === 'narrow'
              ? 0.88
              : sample.id === 'wide' || sample.id === 'smile'
                ? 1.14
                : 1.04,
          smile: sample.id === 'smile' || sample.id === 'wide' ? 0.4 : 0.1,
          brow: 0.12 + open * 0.28 + 0.06 * Math.sin(now / 160),
          headNod: Math.sin(now / 110) * 2.8,
          headTilt: Math.sin(now / 230) * 3.2,
          lid: 0.04,
        };
      } else if (expr === 'think') {
        next = {
          ...next,
          gazeX: 0.22 + 0.14 * Math.sin(now / 900),
          brow: -0.4 + 0.08 * Math.sin(now / 700),
          headTilt: 3 + Math.sin(now / 1100) * 1.4,
        };
      } else if (expr === 'type') {
        next = {
          ...next,
          mouthOpen: 0.02 + 0.02 * Math.abs(Math.sin(now / 90)),
          jaw: 0.02 + 0.015 * Math.abs(Math.sin(now / 90)),
          headNod: Math.sin(now / 190) * 0.9,
        };
      } else {
        next = {
          ...next,
          headTilt: next.headTilt + Math.sin(now / 2400) * 1.4,
          headNod: next.headNod + Math.sin(now / 2800) * 1.1,
          smile: next.smile + 0.04 * Math.sin(now / 1800),
        };
      }

      next = { ...next, lid: Math.max(next.lid, blinkRef.current) };
      poseRef.current = next;

      const canvas = canvasRef.current;
      const img = imgRef.current;
      if (canvas && img?.complete) {
        const ctx = canvas.getContext('2d');
        if (ctx) {
          const dpr = canvas.width / Math.max(1, sizeRef.current);
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          drawWarpedFace(ctx, img, sizeRef.current, next);
        }
      }

      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(rafRef.current);
  }, [expr, level, speakingText, speechProgress, schedule]);

  return (
    <div
      className={`cam-face-live expr-${expr}${listening ? ' live' : ''}${
        speakingText ? ' mouth-open' : ''
      }`}
      style={{ ['--level' as string]: String(level) } as CSSProperties}
      role="img"
      aria-label={`Cam, ${expr}`}
    >
      <div className="cam-face-live-inner">
        <canvas ref={canvasRef} className="cam-face-canvas" />
      </div>
    </div>
  );
}
