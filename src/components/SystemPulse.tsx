import { useEffect, useState } from 'react';

export interface SystemPiece {
  id: string;
  title: string;
  layer: string;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  detail?: string;
}

export interface SystemStatusPayload {
  ok: boolean;
  overall: string;
  at: string;
  pieces: SystemPiece[];
  bus?: Record<string, string>;
  listening?: boolean;
  scanning?: boolean;
}

export function SystemPulse() {
  const [status, setStatus] = useState<SystemStatusPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      void fetch('/api/system')
        .then(async (r) => {
          if (!r.ok) throw new Error(`system ${r.status}`);
          return r.json() as Promise<SystemStatusPayload>;
        })
        .then((data) => {
          if (!cancelled) {
            setStatus(data);
            setError(null);
          }
        })
        .catch((e: unknown) => {
          if (!cancelled) setError(e instanceof Error ? e.message : 'system offline');
        });
    };
    load();
    const t = setInterval(load, 20_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const overall = status?.overall ?? (error ? 'critical' : 'unknown');
  const pieces = status?.pieces ?? [];

  return (
    <section className="system-pulse" aria-label="Cam system pulse">
      <header className="system-pulse-head">
        <h2>System pulse</h2>
        <p>
          Every Cam piece on one bus — converse, connectome, mesh, and motors.
        </p>
        <span className={`system-overall status-${overall}`}>{overall}</span>
      </header>
      {error && !status ? <p className="system-error">{error}</p> : null}
      <ul className="system-piece-list">
        {pieces.map((p) => (
          <li key={p.id} className={`system-piece status-${p.status}`}>
            <span className="system-piece-dot" aria-hidden />
            <span className="system-piece-title">{p.title}</span>
            <span className="system-piece-layer">{p.layer}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
