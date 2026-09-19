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
    bubbles,
    error,
    listening,
    startListening,
    stop,
    sendTurn,
  } = useCamVoice();
  const [draft, setDraft] = useState('');
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    onListeningChange?.(listening);
  }, [listening, onListeningChange]);

  useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [bubbles, partial]);

  const statusLabel =
    status === 'listening'
      ? 'Listening to the room…'
      : status === 'thinking'
        ? 'Cam is thinking…'
        : status === 'speaking'
          ? 'Cam is speaking…'
          : status === 'requesting'
            ? 'Requesting mic…'
            : status === 'error'
              ? error || 'Mic issue'
              : 'Tap to let Cam listen';

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
          <p className="cam-tag">soft airy · always on · listening when you open the mic</p>
          <p className={`cam-status status-${status}`}>{statusLabel}</p>
        </div>
      </div>

      <div className="cam-meter" aria-hidden>
        <span style={{ width: `${Math.round(level * 100)}%` }} />
      </div>
      {partial ? <p className="cam-partial">{partial}</p> : null}

      <div className="cam-transcript" ref={transcriptRef} aria-live="polite">
        {bubbles.length === 0 ? (
          <p className="cam-empty">
            Enable the mic and speak — or type. Cam stays in the background spawning improve tasks
            for herself and her agents.
          </p>
        ) : (
          bubbles.map((b, i) => (
            <div key={`${b.at}-${i}`} className={`cam-bubble ${b.who}`}>
              <span className="who">{b.who === 'aaron' ? 'Aaron' : 'Cam'}</span>
              <span className="text">{b.text}</span>
            </div>
          ))
        )}
      </div>

      <div className="cam-controls">
        {!listening ? (
          <button type="button" className="btn cam-listen-btn" onClick={() => void startListening()}>
            Enable mic & talk
          </button>
        ) : (
          <button type="button" className="btn btn-ghost" onClick={stop}>
            Pause listening
          </button>
        )}
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
