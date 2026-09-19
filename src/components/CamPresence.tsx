import { useCamVoice } from '@/hooks/useCamVoice';
import { useEffect, useRef, useState } from 'react';

interface CamPresenceProps {
  onListeningChange?: (listening: boolean) => void;
}

export function CamPresence({ onListeningChange }: CamPresenceProps) {
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
    aaronOnly,
    adaptiveRaised,
    gateStats,
    startListening,
    startEnroll,
    clearEnrollment,
    exportProfile,
    importProfile,
    stop,
    sendTurn,
  } = useCamVoice();
  const [draft, setDraft] = useState('');
  const transcriptRef = useRef<HTMLDivElement>(null);
  const importRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    onListeningChange?.(listening);
  }, [listening, onListeningChange]);

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [bubbles, partial]);

  const statusLabel =
    status === 'enrolling'
      ? `Enrolling Aaron’s voice… ${Math.round(enrollProgress * 100)}%`
      : status === 'listening'
        ? aaronOnly
          ? enrolled
            ? `Aaron-only · match ${(voiceScore * 100).toFixed(0)}%${
                adaptiveRaised ? ' · adaptive↑' : ''
              }`
            : 'Aaron-only — enroll voice to filter the room'
          : 'Listening…'
        : status === 'ignored'
          ? 'Ignored surrounding speech'
          : status === 'thinking'
            ? 'Cam is thinking…'
            : status === 'speaking'
              ? 'Cam is speaking…'
              : status === 'requesting'
                ? 'Requesting mic…'
                : status === 'error'
                  ? error || 'Mic issue'
                  : 'Tap to let Cam listen (Aaron only)';

  return (
    <aside className="cam-presence" aria-label="Cam presence">
      <div className="cam-presence-head">
        <div className={`cam-face-wrap${listening ? ' live' : ''}`}>
          <img
            className="cam-face"
            src="/identity/persona/cam-face.jpg"
            alt="Cam"
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = 'none';
            }}
          />
          <span className="cam-mic-ring" style={{ ['--level' as string]: String(level) }} />
        </div>
        <div className="cam-presence-copy">
          <p className="cam-name">Cam</p>
          <p className="cam-tag">
            soft airy · Aaron-only voice · ignores room chatter when enrolled
          </p>
          <p className={`cam-status status-${status}`}>{statusLabel}</p>
          {adaptiveRaised ? (
            <p className="cam-adaptive" aria-live="polite">
              Adaptive noise gate raised after surrounding speech
            </p>
          ) : null}
          {gateStats.rejects > 0 ? (
            <p className="cam-gate-stats">
              Gate rejects {gateStats.rejects} · accepts {gateStats.accepts}
            </p>
          ) : null}
        </div>
      </div>

      <div className="cam-meter" aria-hidden>
        <span style={{ width: `${Math.round(level * 100)}%` }} />
      </div>
      {status === 'enrolling' ? (
        <div className="cam-meter cam-enroll" aria-label="Enrollment progress">
          <span style={{ width: `${Math.round(enrollProgress * 100)}%` }} />
        </div>
      ) : null}
      {partial ? <p className="cam-partial">{partial}</p> : null}

      <div className="cam-transcript" ref={transcriptRef} aria-live="polite">
        {bubbles.length === 0 ? (
          <p className="cam-empty">
            Enroll your voice once (quiet ~10s), then enable the mic. Cam will accept{' '}
            <strong>only Aaron</strong> — surrounding conversation is ignored. Typing still works
            anytime.
          </p>
        ) : (
          bubbles.map((b, i) => (
            <div key={`${b.at}-${i}`} className={`cam-bubble ${b.who}`}>
              <span className="who">
                {b.who === 'aaron' ? 'Aaron' : b.who === 'cam' ? 'Cam' : 'Gate'}
              </span>
              <span className="text">{b.text}</span>
            </div>
          ))
        )}
      </div>

      <div className="cam-controls">
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
              {enrolled ? 'Re-enroll my voice' : 'Enroll my voice (10s)'}
            </button>
          </>
        ) : (
          <button type="button" className="btn btn-ghost" onClick={stop}>
            Pause listening
          </button>
        )}
        {enrolled && !listening ? (
          <>
            <button type="button" className="btn btn-ghost" onClick={() => exportProfile()}>
              Export voice profile
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => importRef.current?.click()}
            >
              Import voice profile
            </button>
            <button type="button" className="btn btn-ghost" onClick={clearEnrollment}>
              Clear voice print
            </button>
          </>
        ) : null}
        <input
          ref={importRef}
          type="file"
          accept="application/json,.json"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            void file.text().then((raw) => importProfile(raw));
            e.target.value = '';
          }}
        />
      </div>

      <form
        className="cam-text-form"
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
          placeholder="Or type to Cam…"
          aria-label="Message Cam"
          autoComplete="off"
        />
        <button type="submit" className="btn btn-ghost">
          Send
        </button>
      </form>
    </aside>
  );
}
