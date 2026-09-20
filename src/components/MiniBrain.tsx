/**
 * Compact live brain — shows Cam thinking a request through sense → tracts → reply.
 */
import { useEffect, useMemo, useState } from 'react';

export type BrainPhase = 'idle' | 'hearing' | 'routing' | 'answering' | 'speaking';

interface MiniBrainProps {
  phase: BrainPhase;
  tracts?: string[];
  areas?: string[];
  label?: string;
}

const NODES = [
  { id: 'area.auditory', label: 'Hear', x: 28, y: 62 },
  { id: 'area.wernicke', label: 'Understand', x: 62, y: 48 },
  { id: 'area.mtl', label: 'Memory', x: 48, y: 78 },
  { id: 'area.dlpfc', label: 'Plan', x: 38, y: 28 },
  { id: 'area.broca', label: 'Speak', x: 72, y: 30 },
  { id: 'area.cingulate', label: 'Check', x: 50, y: 18 },
] as const;

const EDGES: Array<[string, string]> = [
  ['area.auditory', 'area.wernicke'],
  ['area.wernicke', 'area.mtl'],
  ['area.wernicke', 'area.dlpfc'],
  ['area.dlpfc', 'area.broca'],
  ['area.cingulate', 'area.dlpfc'],
  ['area.mtl', 'area.broca'],
];

function phaseAreas(phase: BrainPhase): string[] {
  switch (phase) {
    case 'hearing':
      return ['area.auditory', 'area.wernicke'];
    case 'routing':
      return ['area.wernicke', 'area.dlpfc', 'area.mtl', 'area.cingulate'];
    case 'answering':
      return ['area.dlpfc', 'area.broca', 'area.mtl'];
    case 'speaking':
      return ['area.broca', 'area.auditory'];
    default:
      return [];
  }
}

export function MiniBrain({ phase, tracts = [], areas = [], label }: MiniBrainProps) {
  const [tick, setTick] = useState(0);
  const lit = useMemo(() => {
    const set = new Set([...phaseAreas(phase), ...areas]);
    return set;
  }, [phase, areas]);

  useEffect(() => {
    if (phase === 'idle') return;
    const id = window.setInterval(() => setTick((t) => t + 1), 420);
    return () => window.clearInterval(id);
  }, [phase]);

  const phaseLabel =
    label ||
    ({
      idle: 'Cortex quiet',
      hearing: 'Hearing you…',
      routing: 'Routing through mesh…',
      answering: 'Forming reply…',
      speaking: 'Speaking…',
    }[phase] as string);

  return (
    <aside className={`mini-brain phase-${phase}`} aria-label="Cam live cortex">
      <header className="mini-brain-head">
        <span className="mini-brain-title">Live cortex</span>
        <span className="mini-brain-phase">{phaseLabel}</span>
      </header>
      <svg className="mini-brain-svg" viewBox="0 0 100 100" role="img">
        <defs>
          <radialGradient id="miniBrainGlow" cx="50%" cy="45%" r="55%">
            <stop offset="0%" stopColor="rgba(61,184,168,0.35)" />
            <stop offset="70%" stopColor="rgba(26,107,107,0.08)" />
            <stop offset="100%" stopColor="rgba(6,16,20,0)" />
          </radialGradient>
        </defs>
        <ellipse cx="50" cy="48" rx="38" ry="40" fill="url(#miniBrainGlow)" />
        <ellipse
          cx="50"
          cy="48"
          rx="34"
          ry="36"
          fill="none"
          stroke="rgba(61,184,168,0.22)"
          strokeWidth="0.6"
        />
        {EDGES.map(([a, b], i) => {
          const na = NODES.find((n) => n.id === a)!;
          const nb = NODES.find((n) => n.id === b)!;
          const hot = lit.has(a) && lit.has(b);
          const pulse = hot && (tick + i) % 2 === 0;
          return (
            <line
              key={`${a}-${b}`}
              x1={na.x}
              y1={na.y}
              x2={nb.x}
              y2={nb.y}
              className={`mini-edge${hot ? ' lit' : ''}${pulse ? ' pulse' : ''}`}
            />
          );
        })}
        {NODES.map((n) => {
          const hot = lit.has(n.id);
          return (
            <g key={n.id} className={`mini-node${hot ? ' lit' : ''}`}>
              <circle cx={n.x} cy={n.y} r={hot ? 4.2 : 3.2} />
              <text x={n.x} y={n.y + 9} textAnchor="middle">
                {n.label}
              </text>
            </g>
          );
        })}
      </svg>
      {tracts.length > 0 ? (
        <p className="mini-brain-tracts">{tracts.slice(0, 3).map(shortTract).join(' · ')}</p>
      ) : (
        <p className="mini-brain-tracts muted">sense → tracts → reply</p>
      )}
    </aside>
  );
}

function shortTract(t: string): string {
  return t.replace(/^tract\./, '');
}
