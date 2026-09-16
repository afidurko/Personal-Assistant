import { useCallback, useMemo, useState, type MouseEvent } from 'react';
import { STATUS_COLORS, type BrainNode, type ScanStatus } from '@shared/types';
import { useMeshStore } from '@/store/meshStore';

const VIEW_W = 1000;
const VIEW_H = 620;

/** Soft brain silhouette — top-down-ish lateral outline */
const BRAIN_PATH =
  'M 220 310 C 210 180, 280 90, 400 70 C 480 55, 540 70, 580 95 ' +
  'C 620 70, 700 55, 780 85 C 870 125, 910 210, 900 300 ' +
  'C 895 380, 860 450, 800 490 C 740 530, 660 545, 580 530 ' +
  'C 540 555, 470 560, 410 535 C 340 555, 270 520, 235 450 ' +
  'C 210 395, 225 350, 220 310 Z ' +
  'M 500 95 C 490 180, 505 280, 500 380 C 495 450, 505 500, 510 530';

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
          const color = isConcept
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

          return (
            <g
              key={node.id}
              className={`brain-node${selected ? ' selected' : ''}${isConcept ? ' concept' : ''}${node.status === 'scanning' || (scanning && node.workspaceId) ? ' scanning' : ''}${dimmed ? ' dimmed' : ''}`}
              transform={`translate(${cx} ${cy})`}
              onClick={() => handleNodeClick(node)}
              onMouseEnter={(e) => {
                const svg = e.currentTarget.ownerSVGElement;
                if (!svg) return;
                const rect = svg.getBoundingClientRect();
                const ws = node.workspaceId
                  ? workspaces.find((w) => w.id === node.workspaceId)
                  : undefined;
                setTooltip({
                  x: e.clientX - rect.left,
                  y: e.clientY - rect.top,
                  label: isConcept ? `Swift · ${node.label}` : node.label,
                  status: node.status,
                  score: ws?.score,
                });
              }}
              onMouseLeave={() => setTooltip(null)}
            >
              {(node.status === 'critical' ||
                node.status === 'warning' ||
                selected ||
                isConcept) && (
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
      </div>
    </div>
  );
}
