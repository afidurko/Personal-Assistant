/**
 * CamStage — large interactive avatar: listens, thinks (mini-brain), types + speaks.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useCamVoice, type CamVoiceStatus } from '@/hooks/useCamVoice';
import { useTypewriter } from '@/hooks/useTypewriter';
import { MiniBrain, type BrainPhase } from '@/components/MiniBrain';
import { CamFace } from '@/components/CamFace';

interface CamStageProps {
  onListeningChange?: (listening: boolean) => void;
}

function toBrainPhase(status: CamVoiceStatus, typing: boolean): BrainPhase {
  if (typing) return 'answering';
  switch (status) {
    case 'listening':
    case 'enrolling':
    case 'requesting':
      return 'hearing';
    case 'thinking':
      return 'routing';
    case 'speaking':
      return 'speaking';
    default:
      return 'idle';
  }
}

export function CamStage({ onListeningChange }: CamStageProps) {
  const {
    status,
    partial,
    level,
    voiceScore,
    bubbles,
    error,
    listening,
    enrolled,
    enrollProgress,
    adaptiveRaised,
    lastRoute,
    bridgeBusy,
    speechFace,
    startListening,
    startEnroll,
    stop,
    sendTurn,
    flushSpeak,
  } = useCamVoice();

  const [draft, setDraft] = useState('');
  const [higgsClip, setHiggsClip] = useState<string | null>(null);
  const [higgsNote, setHiggsNote] = useState<string | null>(null);
  const [higgsReady, setHiggsReady] = useState(false);
  const [higgsHasKeys, setHiggsHasKeys] = useState(false);
  const [higgsBusy, setHiggsBusy] = useState(false);
  const [higgsPlaying, setHiggsPlaying] = useState(false);
  const [typedCam, setTypedCam] = useState('');
  const [typingActive, setTypingActive] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const lastCamRef = useRef('');
  const prevTypedDoneRef = useRef(true);

  useEffect(() => {
    onListeningChange?.(listening);
  }, [listening, onListeningChange]);

  useEffect(() => {
    void fetch('/api/avatar/higgsfield')
      .then((r) => r.json())
      .then(
        (j: {
          public_path?: string;
          credentials_present?: boolean;
          live_enabled?: boolean;
          ready_to_render?: boolean;
          last_error?: string | null;
        }) => {
          setHiggsClip(j.public_path || null);
          setHiggsHasKeys(Boolean(j.credentials_present));
          setHiggsReady(Boolean(j.ready_to_render));
          if (j.last_error) setHiggsNote(j.last_error);
          else if (j.ready_to_render) setHiggsNote('Higgsfield Speak ready — render a line to play a clip');
          else if (j.credentials_present)
            setHiggsNote('Keys present — set HIGGSFIELD_LIVE=1 to render. Preview is free.');
          else setHiggsNote('Speak needs HF_API_KEY_ID + HF_API_KEY_SECRET (or HIGGSFIELD_* aliases).');
        },
      )
      .catch(() => undefined);
  }, []);

  const runHiggsSpeak = (live: boolean) => {
    const text = typedCam || lastCamRef.current || 'Hello Aaron';
    setHiggsBusy(true);
    setHiggsPlaying(false);
    setHiggsNote(live ? 'Uploading portrait + WAV, then Speak…' : 'Previewing Speak request (no upload)…');
    void fetch('/api/avatar/higgsfield/speak', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, live }),
      signal: AbortSignal.timeout(live ? 240_000 : 30_000),
    })
      .then(async (r) => {
        const j = (await r.json()) as {
          ok?: boolean;
          report?: {
            ok?: boolean;
            error?: string;
            last?: { public_path?: string; error?: string };
            notes?: string;
            local_image?: string;
            audio_plan?: { engine?: { id?: string } };
            planned_steps?: string[];
          };
          error?: string;
          detail?: string;
        };
        const report = j.report || {};
        const clip = report.last?.public_path;
        if (live && (j.ok || report.ok) && clip) {
          setHiggsClip(clip);
          setHiggsNote('Clip ready — press Play Speak clip');
        } else if (!live && (j.ok || report.ok)) {
          const engine = report.audio_plan?.engine?.id || 'local TTS';
          setHiggsNote(
            `Dry-run ok. Portrait ${report.local_image ? 'found' : 'missing'}; WAV via ${engine}. Live still gated.`,
          );
        } else {
          setHiggsNote(report.last?.error || report.error || j.detail || j.error || 'Speak request failed');
        }
      })
      .catch((e: unknown) => {
        setHiggsNote(e instanceof Error ? e.message : 'Speak request failed');
      })
      .finally(() => setHiggsBusy(false));
  };

  // When a new Cam bubble arrives, type it out then speak
  useEffect(() => {
    const lastCam = [...bubbles].reverse().find((b) => b.who === 'cam');
    if (!lastCam || lastCam.text === lastCamRef.current) return;
    lastCamRef.current = lastCam.text;
    prevTypedDoneRef.current = true; // reset; speak only after done flips false→true
    setTypedCam(lastCam.text);
    setTypingActive(true);
  }, [bubbles]);

  const { shown: typedOut, done: typedDone } = useTypewriter(typedCam, typingActive, 56);

  useEffect(() => {
    const justFinished = typedDone && !prevTypedDoneRef.current;
    prevTypedDoneRef.current = typedDone;
    if (!justFinished) return;
    setTypingActive(false);
    flushSpeak();
  }, [typedDone, flushSpeak]);

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [bubbles, partial, typedOut]);

  const phase = toBrainPhase(status, typingActive);
  const tracts = useMemo(() => {
    const fromRoute = lastRoute?.tracts ?? [];
    const fromDual = lastRoute?.dual_stream?.tracts ?? [];
    return fromRoute.length ? fromRoute : fromDual;
  }, [lastRoute]);
  const areas = useMemo(() => {
    return [...(lastRoute?.pathway || [])].filter((p) => p.startsWith('area.'));
  }, [lastRoute]);

  const statusLine =
    status === 'enrolling'
      ? `Learning your voice… ${Math.round(enrollProgress * 100)}%`
      : status === 'listening'
        ? enrolled
          ? `Listening for Aaron · ${(voiceScore * 100).toFixed(0)}%`
          : 'Listening — enroll so only you get through'
        : status === 'thinking' || bridgeBusy
          ? 'Thinking through the cortex…'
          : typingActive
            ? 'Typing…'
            : status === 'speaking'
              ? 'Speaking…'
              : status === 'ignored'
                ? 'Ignored surrounding speech'
                : status === 'error'
                  ? error || 'Something went wrong'
                  : 'Tap Enable mic — I’m here';

  return (
    <section className="cam-stage" aria-label="Cam presence stage">
      <div className="cam-stage-main">
        <div
          className={`cam-avatar-stage status-${status}${listening ? ' live' : ''}${
            typingActive ? ' typing' : ''
          }`}
          style={{ ['--level' as string]: String(level) }}
        >
          <div className="cam-avatar-glow" aria-hidden />
          <div className="cam-avatar-ring" aria-hidden />
          <div className="cam-avatar-face-wrap">
            <CamFace
              status={speechFace.active ? 'speaking' : status}
              listening={listening}
              level={level}
              typing={typingActive && !speechFace.active}
              speakingText={speechFace.active ? speechFace.text : ''}
              speechProgress={speechFace.active ? speechFace.progress : -1}
              clipUrl={higgsClip}
              clipActive={higgsPlaying}
              onClipEnded={() => setHiggsPlaying(false)}
            />
          </div>
          <p className="cam-avatar-name">Cam</p>
          <p className="cam-avatar-status">{statusLine}</p>
          {adaptiveRaised ? (
            <p className="cam-avatar-note">Noise gate raised — room chatter filtered</p>
          ) : null}
          {higgsNote ? <p className="cam-avatar-note">{higgsNote}</p> : null}
          <div className="cam-higgs-controls">
            <button
              type="button"
              className="btn btn-ghost"
              disabled={higgsBusy}
              onClick={() => runHiggsSpeak(false)}
            >
              {higgsBusy && !higgsReady ? 'Previewing…' : 'Preview Speak request'}
            </button>
            <button
              type="button"
              className="btn"
              disabled={higgsBusy || !higgsReady}
              onClick={() => runHiggsSpeak(true)}
              title={higgsReady ? 'Uploads Cam’s face and spends credits' : 'Needs keys + HIGGSFIELD_LIVE=1'}
            >
              {higgsBusy && higgsReady ? 'Rendering…' : 'Render Speak clip'}
            </button>
            {higgsClip ? (
              <button
                type="button"
                className="btn btn-ghost"
                disabled={higgsBusy}
                onClick={() => setHiggsPlaying(true)}
              >
                Play Speak clip
              </button>
            ) : null}
          </div>
          {!higgsHasKeys ? (
            <p className="cam-avatar-note">
              Official names work: HF_API_KEY_ID / HF_API_KEY_SECRET or HF_CREDENTIALS.
            </p>
          ) : null}
        </div>

        <MiniBrain
          phase={phase}
          tracts={tracts}
          areas={areas}
          label={
            lastRoute?.behavior && phase !== 'idle'
              ? String(lastRoute.behavior).replace(/_/g, ' ')
              : undefined
          }
        />
      </div>

      <div className="cam-stage-converse">
        <div className="cam-stage-transcript" ref={transcriptRef} aria-live="polite">
          {bubbles.length === 0 && !partial ? (
            <p className="cam-stage-empty">
              Enable the mic and talk — or type. You’ll see my cortex light the path, then I’ll type
              and speak the answer.
            </p>
          ) : (
            bubbles.map((b, i) => {
              const isLastCam =
                b.who === 'cam' && i === bubbles.map((x) => x.who).lastIndexOf('cam');
              const text =
                isLastCam && typingActive ? typedOut : isLastCam ? typedOut || b.text : b.text;
              return (
                <div key={`${b.at}-${i}`} className={`cam-stage-bubble ${b.who}`}>
                  <span className="who">
                    {b.who === 'aaron' ? 'Aaron' : b.who === 'cam' ? 'Cam' : 'System'}
                  </span>
                  <span className="text">
                    {text}
                    {isLastCam && typingActive ? <span className="cam-caret" aria-hidden /> : null}
                  </span>
                </div>
              );
            })
          )}
          {partial ? (
            <div className="cam-stage-bubble aaron interim">
              <span className="who">Aaron</span>
              <span className="text">{partial}</span>
            </div>
          ) : null}
        </div>

        <div className="cam-stage-controls">
          {!listening ? (
            <>
              <button
                type="button"
                className="btn cam-listen-btn"
                onClick={() => void startListening()}
              >
                Enable mic & talk
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => void startEnroll()}>
                {enrolled ? 'Re-enroll voice' : 'Enroll my voice'}
              </button>
            </>
          ) : (
            <button type="button" className="btn btn-ghost" onClick={stop}>
              Pause listening
            </button>
          )}
        </div>

        <form
          className="cam-text-form cam-stage-form"
          onSubmit={(e) => {
            e.preventDefault();
            const v = draft;
            setDraft('');
            void sendTurn(v, 'text');
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type to Cam…"
            aria-label="Message Cam"
            autoComplete="off"
          />
          <button type="submit" className="btn">
            Send
          </button>
        </form>
        {error && status === 'error' ? <p className="cam-stage-error">{error}</p> : null}
      </div>
    </section>
  );
}
