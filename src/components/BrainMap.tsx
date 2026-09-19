import { useCallback, useMemo, useState, type MouseEvent } from 'react';
import { STATUS_COLORS, type BrainNode, type ScanStatus } from '@shared/types';
import { useMeshStore } from '@/store/meshStore';

const VIEW_W = 1000;
const VIEW_H = 620;

/** Left-lateral human brain silhouette (anterior left, superior top) */
const BRAIN_PATH =
  'M 160 300 ' +
  'C 155 220, 175 140, 230 95 ' +
  'C 290 50, 370 40, 450 55 ' +
  'C 520 38, 600 45, 670 80 ' +
  'C 740 115, 800 170, 835 240 ' +
  'C 860 300, 855 370, 820 430 ' +
  'C 780 500, 700 545, 610 560 ' +
  'C 540 575, 470 565, 420 530 ' +
  'C 380 560, 320 555, 270 510 ' +
  'C 220 470, 175 400, 160 300 Z';

const SYLVIAN_PATH = 'M 280 280 C 360 300, 450 310, 540 280';
const MIDLINE_PATH = 'M 500 90 C 505 180, 510 280, 500 400';

const LEGEND: { status: ScanStatus; label: string }[] = [
  { status: 'idle', label: 'Idle' },
  { status: 'scanning', label: 'Scanning' },
  { status: 'healthy', label: 'Healthy' },
  { status: 'warning', label: 'Warning' },
  { status: 'critical', label: 'Critical' },
  { status: 'stale', label: 'Stale' },
];

function toSvg(node: BrainNode): { cx: number; cy: number; r: number } {
  return {
    cx: 80 + node.x * (VIEW_W - 160),
    cy: 60 + node.y * (VIEW_H - 120),
    r: 8 + node.radius * 10,
  };
}

function hexPoints(r: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 6; i++) {
    const a = (Math.PI / 180) * (60 * i - 30);
    pts.push(`${(Math.cos(a) * r).toFixed(2)},${(Math.sin(a) * r).toFixed(2)}`);
  }
  return pts.join(' ');
}

function curvePath(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
): string {
  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const dx = x2 - x1;
  const dy = y2 - y1;
  const cx = mx - dy * 0.18;
  const cy = my + dx * 0.18;
  return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
}

interface BrainMapProps {
  onFocusNode: (nodeId: string) => void;
}

export function BrainMap({ onFocusNode }: BrainMapProps) {
  const nodes = useMeshStore((s) => s.nodes);
  const edges = useMeshStore((s) => s.edges);
  const workspaces = useMeshStore((s) => s.workspaces);
  const scanning = useMeshStore((s) => s.scanning);
  const selectedNodeId = useMeshStore((s) => s.selectedNodeId);
  const selectedWorkspaceId = useMeshStore((s) => s.selectedWorkspaceId);
  const selectNode = useMeshStore((s) => s.selectNode);

  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    label: string;
    status: ScanStatus;
    score?: number;
  } | null>(null);

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const linkedIds = useMemo(() => {
    if (!selectedNodeId) return null;
    const set = new Set<string>([selectedNodeId]);
    for (const e of edges) {
      if (e.from === selectedNodeId || e.to === selectedNodeId) {
        set.add(e.from);
        set.add(e.to);
      }
    }
    // Also link via shared workspace selection
    if (selectedWorkspaceId) {
      for (const n of nodes) {
        if (n.workspaceId === selectedWorkspaceId) set.add(n.id);
      }
    }
    // Concept nodes light related workspace nodes
    const selected = nodes.find((n) => n.id === selectedNodeId);
    if (selected?.conceptId) {
      for (const e of edges) {
        if (e.from === selectedNodeId || e.to === selectedNodeId) {
          set.add(e.from);
          set.add(e.to);
        }
      }
    }
    return set;
  }, [selectedNodeId, selectedWorkspaceId, edges, nodes]);

  const highlightedEdges = useMemo(() => {
    if (!selectedNodeId) return null;
    return new Set(
      edges
        .filter((e) => e.from === selectedNodeId || e.to === selectedNodeId)
        .map((e) => e.id),
    );
  }, [selectedNodeId, edges]);

  const handleNodeClick = useCallback(
    (node: BrainNode) => {
      if (!node.interactive) return;
      selectNode(node.id);
      onFocusNode(node.id);
    },
    [selectNode, onFocusNode],
  );

  const handleMove = useCallback(
    (e: MouseEvent<SVGSVGElement>) => {
      if (!tooltip) return;
      const rect = e.currentTarget.getBoundingClientRect();
      setTooltip((t) =>
        t
          ? {
              ...t,
              x: e.clientX - rect.left,
              y: e.clientY - rect.top,
            }
          : null,
      );
    },
    [tooltip],
  );

  return (
    <div className="brain-stage" aria-label="Neural mesh brain map">
      <svg
        className="brain-map"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        role="img"
        aria-label="Interactive brain map of system workspaces"
        onMouseMove={handleMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <defs>
          <radialGradient id="brain-fill" cx="45%" cy="40%" r="60%">
            <stop offset="0%" stopColor="rgba(42,154,143,0.22)" />
            <stop offset="70%" stopColor="rgba(26,107,107,0.08)" />
            <stop offset="100%" stopColor="rgba(10,20,25,0.02)" />
          </radialGradient>
          <filter id="soft-glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <path className="brain-silhouette" d={BRAIN_PATH} fill="url(#brain-fill)" />
        <path
          className="brain-fissure"
          d={SYLVIAN_PATH}
          fill="none"
          stroke="rgba(230,213,184,0.22)"
          strokeWidth="1.5"
        />
        <path
          className="brain-fissure"
          d={MIDLINE_PATH}
          fill="none"
          stroke="rgba(230,213,184,0.16)"
          strokeWidth="1.2"
        />

        {edges.map((edge) => {
          const from = nodeMap.get(edge.from);
          const to = nodeMap.get(edge.to);
          if (!from || !to) return null;
          const a = toSvg(from);
          const b = toSvg(to);
          const isHi = highlightedEdges?.has(edge.id) ?? false;
          const isDim = highlightedEdges !== null && !isHi;
          const color = STATUS_COLORS[from.status] || STATUS_COLORS.idle;
          const opacity = 0.2 + edge.weight * 0.55;
          const width = 1 + edge.weight * 2.2;

          return (
            <path
              key={edge.id}
              className={`mesh-edge${scanning ? ' flowing' : ''}${isHi ? ' highlighted' : ''}${isDim ? ' dimmed' : ''}`}
              d={curvePath(a.cx, a.cy, b.cx, b.cy)}
              stroke={color}
              strokeWidth={isHi ? width + 1.2 : width}
              strokeOpacity={isDim ? 0.1 : opacity}
            />
          );
        })}

        {nodes.map((node) => {
          const { cx, cy, r } = toSvg(node);
          const isConcept = node.kind === 'concept' || Boolean(node.conceptId);
          const isAgent = node.kind === 'agent' || node.kind === 'layer';
          const color =
            isConcept || isAgent
              ? (node.color || STATUS_COLORS.idle)
              : (STATUS_COLORS[node.status] ?? node.color ?? STATUS_COLORS.idle);
          const selected = selectedNodeId === node.id;
          const dimmed = linkedIds !== null && !linkedIds.has(node.id);
          const glowClass =
            node.status === 'critical'
              ? 'critical'
              : node.status === 'warning'
                ? 'warning'
                : '';
          const glowR =
            r *
            (node.status === 'critical' ? 2.8 : node.status === 'warning' ? 2.3 : 1.8);
          const diamond = r * 1.15;
          const hex = r * 1.05;

          return (
            <g
              key={node.id}
              className={`brain-node${selected ? ' selected' : ''}${isConcept ? ' concept' : ''}${isAgent ? ` agent${node.kind === 'layer' ? ' layer' : ''}` : ''}${node.status === 'scanning' || (scanning && node.workspaceId) ? ' scanning' : ''}${dimmed ? ' dimmed' : ''}`}
              transform={`translate(${cx} ${cy})`}
              onClick={() => handleNodeClick(node)}
              onMouseEnter={(e) => {
                const svg = e.currentTarget.ownerSVGElement;
                if (!svg) return;
                const rect = svg.getBoundingClientRect();
                const ws = node.workspaceId
                  ? workspaces.find((w) => w.id === node.workspaceId)
                  : undefined;
                const prefix = isConcept
                  ? 'Swift · '
                  : node.kind === 'layer'
                    ? 'Layer · '
                    : node.kind === 'agent'
                      ? 'Agent · '
                      : '';
                setTooltip({
                  x: e.clientX - rect.left,
                  y: e.clientY - rect.top,
                  label: `${prefix}${node.label}`,
                  status: node.status,
                  score: ws?.score,
                });
              }}
              onMouseLeave={() => setTooltip(null)}
            >
              {(node.status === 'critical' ||
                node.status === 'warning' ||
                selected ||
                isConcept ||
                isAgent) && (
                <circle
                  className={`node-glow ${glowClass}`}
                  r={glowR}
                  fill={color}
                  filter="url(#soft-glow)"
                />
              )}
              {isConcept ? (
                <>
                  <rect
                    className="node-ring concept-diamond"
                    x={-diamond}
                    y={-diamond}
                    width={diamond * 2}
                    height={diamond * 2}
                    rx={2}
                    transform="rotate(45)"
                    stroke={color}
                    fill="none"
                  />
                  <rect
                    className="node-core concept-diamond"
                    x={-r * 0.85}
                    y={-r * 0.85}
                    width={r * 1.7}
                    height={r * 1.7}
                    rx={1.5}
                    transform="rotate(45)"
                    fill={color}
                    opacity={0.9}
                  />
                </>
              ) : isAgent ? (
                <>
                  <polygon
                    className="node-ring"
                    points={hexPoints(hex + 3)}
                    stroke={color}
                    fill="none"
                  />
                  <polygon
                    className="node-core"
                    points={hexPoints(selected ? hex * 1.15 : hex)}
                    fill={color}
                    opacity={0.9}
                  />
                </>
              ) : (
                <>
                  <circle
                    className="node-ring"
                    r={r + 4 + node.activation * 4}
                    stroke={color}
                  />
                  <circle
                    className="node-core"
                    r={selected ? r * 1.2 : r}
                    fill={color}
                    opacity={0.85 + node.activation * 0.15}
                  />
                </>
              )}
            </g>
          );
        })}
      </svg>

      {tooltip && (
        <div
          className="tooltip"
          style={{ left: tooltip.x, top: tooltip.y }}
          role="tooltip"
        >
          <div className="tooltip-label">{tooltip.label}</div>
          <div className="tooltip-meta">
            {tooltip.status}
            {tooltip.score != null ? ` · score ${Math.round(tooltip.score)}` : ''}
          </div>
        </div>
      )}

      <div className="legend" aria-label="Status color legend">
        {LEGEND.map(({ status, label }) => (
          <div key={status} className="legend-item">
            <span
              className="legend-swatch"
              style={{ background: STATUS_COLORS[status] }}
            />
            {label}
          </div>
        ))}
        <div className="legend-item">
          <span className="legend-swatch diamond" style={{ background: '#9adbc8' }} />
          Swift concept
        </div>
        <div className="legend-item">
          <span className="legend-swatch hex" style={{ background: '#ff8a65' }} />
          Agent / layer
        </div>
      </div>
    </div>
  );
}
