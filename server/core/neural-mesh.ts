import { mkdir, readFile, rename, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  STATUS_COLORS,
  WORKSPACE_META,
  type BrainNode,
  type BrainRegion,
  type MeshEdge,
  type MeshEdgeKind,
  type ScanStatus,
  type WorkspaceKind,
  type WorkspaceSnapshot,
} from '../../shared/types.js';
import { layoutForRegion } from './brain-map-layout.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DEFAULT_DATA_DIR = path.resolve(__dirname, '../../data');

const HUB_NODES: Array<{
  id: string;
  label: string;
  region: BrainRegion;
  tags: string[];
}> = [
  { id: 'hub-cortex', label: 'Cortex', region: 'cortex', tags: ['hub', 'integration'] },
  { id: 'hub-hippocampus', label: 'Hippocampus', region: 'hippocampus', tags: ['hub', 'memory'] },
];

export interface NeuralMeshOptions {
  dataDir?: string;
}

export class NeuralMesh {
  private nodes: BrainNode[] = [];
  private edges: MeshEdge[] = [];
  private readonly filePath: string;
  private readonly dataDir: string;
  private loaded = false;

  constructor(options: NeuralMeshOptions = {}) {
    this.dataDir = options.dataDir ?? DEFAULT_DATA_DIR;
    this.filePath = path.join(this.dataDir, 'mesh.json');
  }

  async load(): Promise<void> {
    await mkdir(this.dataDir, { recursive: true });
    try {
      const raw = await readFile(this.filePath, 'utf8');
      const parsed = JSON.parse(raw) as { nodes?: BrainNode[]; edges?: MeshEdge[] };
      this.nodes = Array.isArray(parsed.nodes) ? parsed.nodes : [];
      this.edges = Array.isArray(parsed.edges) ? parsed.edges : [];
    } catch (err) {
      const code = (err as NodeJS.ErrnoException).code;
      if (code !== 'ENOENT') throw err;
      this.seedDefaultTopology();
    }
    if (this.nodes.length === 0) this.seedDefaultTopology();
    this.loaded = true;
  }

  async save(): Promise<void> {
    if (!this.loaded) await this.load();
    await mkdir(this.dataDir, { recursive: true });
    await atomicWriteJson(this.filePath, { nodes: this.nodes, edges: this.edges });
  }

  seedDefaultTopology(): void {
    const workspaceKinds = Object.keys(WORKSPACE_META) as WorkspaceKind[];
    const regionCounts = new Map<BrainRegion, number>();
    for (const kind of workspaceKinds) {
      const region = WORKSPACE_META[kind].region;
      regionCounts.set(region, (regionCounts.get(region) ?? 0) + 1);
    }
    for (const hub of HUB_NODES) {
      regionCounts.set(hub.region, (regionCounts.get(hub.region) ?? 0) + 1);
    }

    const regionIndex = new Map<BrainRegion, number>();
    const nodes: BrainNode[] = [];

    for (const kind of workspaceKinds) {
      const meta = WORKSPACE_META[kind];
      const total = regionCounts.get(meta.region) ?? 1;
      const idx = regionIndex.get(meta.region) ?? 0;
      regionIndex.set(meta.region, idx + 1);
      const { x, y } = layoutForRegion(meta.region, idx, total);
      nodes.push({
        id: `ws-${kind}`,
        label: meta.name,
        workspaceId: kind,
        region: meta.region,
        x,
        y,
        activation: 0.15,
        status: 'idle',
        color: meta.defaultColor,
        radius: 0.045,
        tags: [kind, 'workspace', meta.region],
        interactive: true,
      });
    }

    for (const hub of HUB_NODES) {
      const total = regionCounts.get(hub.region) ?? 1;
      const idx = regionIndex.get(hub.region) ?? 0;
      regionIndex.set(hub.region, idx + 1);
      const { x, y } = layoutForRegion(hub.region, idx, total);
      nodes.push({
        id: hub.id,
        label: hub.label,
        workspaceId: null,
        region: hub.region,
        x,
        y,
        activation: 0.2,
        status: 'idle',
        color: STATUS_COLORS.idle,
        radius: 0.055,
        tags: hub.tags,
        interactive: true,
      });
    }

    const edges: MeshEdge[] = [
      // Workspaces feed hippocampus (memory consolidation)
      edge('ws-health', 'hub-hippocampus', 'feeds', 0.55, 'health → memory'),
      edge('ws-architecture', 'hub-hippocampus', 'feeds', 0.5, 'architecture → memory'),
      edge('ws-vulnerability', 'hub-hippocampus', 'feeds', 0.6, 'vulns → memory'),
      edge('ws-updates', 'hub-hippocampus', 'feeds', 0.45, 'updates → memory'),
      edge('ws-improvements', 'hub-hippocampus', 'feeds', 0.5, 'improvements → memory'),

      // Vulnerability correlates with improvements
      edge('ws-vulnerability', 'ws-improvements', 'correlates', 0.7, 'threats ↔ fixes'),

      // Health monitors architecture
      edge('ws-health', 'ws-architecture', 'monitors', 0.65, 'vitals monitor structure'),

      // Updates suggests improvements
      edge('ws-updates', 'ws-improvements', 'suggests', 0.6, 'drift → actions'),

      // Cortex integrates workspace signals
      edge('ws-health', 'hub-cortex', 'depends_on', 0.4),
      edge('ws-architecture', 'hub-cortex', 'depends_on', 0.45),
      edge('ws-vulnerability', 'hub-cortex', 'depends_on', 0.4),
      edge('hub-cortex', 'hub-hippocampus', 'hebbian', 0.35, 'integration ↔ memory'),

      // Seed Hebbian links among co-activated peers
      edge('ws-health', 'ws-vulnerability', 'hebbian', 0.25),
      edge('ws-architecture', 'ws-improvements', 'hebbian', 0.3),
      edge('ws-updates', 'ws-health', 'hebbian', 0.2),
    ];

    this.nodes = nodes;
    this.edges = edges;
  }

  applyScanResults(snapshots: WorkspaceSnapshot[]): Record<string, number> {
    const deltas: Record<string, number> = {};
    const activated = new Set<string>();

    for (const snap of snapshots) {
      const node = this.nodes.find((n) => n.workspaceId === snap.id || n.id === `ws-${snap.id}`);
      if (!node) continue;

      const prev = node.activation;
      const target = scoreToActivation(snap.score);
      const status: ScanStatus = snap.status === 'scanning' ? 'scanning' : statusFromScore(snap.score, snap.status);

      node.status = status;
      node.color = status === 'scanning' ? STATUS_COLORS.scanning : this.colorForStatus(status);
      node.activation = status === 'scanning' ? Math.max(target, 0.75) : target;
      node.tags = unique([...(node.tags ?? []), snap.kind, ...Object.keys(snap.metrics ?? {}).slice(0, 4)]);

      deltas[node.id] = node.activation - prev;
      activated.add(node.id);

      if (status === 'scanning' || snap.findings.length > 0) {
        this.spreadActivation(node.id, 0.15 + snap.findings.length * 0.02);
      }
    }

    // Hebbian: strengthen edges between co-activated workspace nodes
    const activatedList = [...activated];
    for (let i = 0; i < activatedList.length; i++) {
      for (let j = i + 1; j < activatedList.length; j++) {
        this.reinforceEdge(activatedList[i], activatedList[j], 0.02);
      }
    }

    // Pulse hippocampus when scans land
    const hippo = this.nodes.find((n) => n.id === 'hub-hippocampus');
    if (hippo && activated.size > 0) {
      const prev = hippo.activation;
      hippo.activation = clamp01(hippo.activation + 0.08 * activated.size);
      hippo.status = 'healthy';
      hippo.color = this.colorForStatus(hippo.status);
      deltas[hippo.id] = (deltas[hippo.id] ?? 0) + (hippo.activation - prev);
    }

    return deltas;
  }

  spreadActivation(seedNodeId: string, amount: number): void {
    const seed = this.nodes.find((n) => n.id === seedNodeId);
    if (!seed) return;

    seed.activation = clamp01(seed.activation + amount);

    const visited = new Set<string>([seedNodeId]);
    const queue: Array<{ id: string; energy: number }> = [{ id: seedNodeId, energy: amount }];

    while (queue.length > 0) {
      const current = queue.shift()!;
      const neighbors = this.edges.filter(
        (e) =>
          e.from === current.id ||
          (e.bidirectional && e.to === current.id) ||
          e.kind === 'hebbian' ||
          e.kind === 'correlates',
      );

      for (const edge of neighbors) {
        const nextId = edge.from === current.id ? edge.to : edge.from;
        if (visited.has(nextId)) continue;
        const transfer = current.energy * edge.weight * 0.55;
        if (transfer < 0.01) continue;

        const node = this.nodes.find((n) => n.id === nextId);
        if (!node) continue;
        node.activation = clamp01(node.activation + transfer);
        visited.add(nextId);
        queue.push({ id: nextId, energy: transfer });

        // Hebbian learning on traversed edges
        if (edge.kind === 'hebbian') {
          edge.weight = clamp01(edge.weight + transfer * 0.05);
        }
      }
    }
  }

  reinforceEdge(from: string, to: string, delta: number): void {
    let edge = this.edges.find(
      (e) => (e.from === from && e.to === to) || (e.bidirectional && e.from === to && e.to === from),
    );
    if (!edge) {
      // Prefer matching undirected hebbian pair
      edge = this.edges.find(
        (e) => e.kind === 'hebbian' && ((e.from === from && e.to === to) || (e.from === to && e.to === from)),
      );
    }
    if (!edge) {
      edge = {
        id: `e-${from}-${to}`,
        from,
        to,
        kind: 'hebbian' as MeshEdgeKind,
        weight: clamp01(delta),
        bidirectional: true,
        label: 'learned',
      };
      this.edges.push(edge);
      return;
    }
    edge.weight = clamp01(edge.weight + delta);
  }

  getState(): { nodes: BrainNode[]; edges: MeshEdge[] } {
    return {
      nodes: this.nodes.map((n) => ({ ...n, tags: [...n.tags] })),
      edges: this.edges.map((e) => ({ ...e })),
    };
  }

  focusNode(id: string): string[] {
    const node = this.nodes.find((n) => n.id === id);
    if (!node) return [];

    node.activation = clamp01(node.activation + 0.35);
    this.spreadActivation(id, 0.25);

    const related = new Set<string>();
    if (node.workspaceId) related.add(node.workspaceId);

    for (const edge of this.edges) {
      const other =
        edge.from === id ? edge.to : edge.to === id ? edge.from : null;
      if (!other) continue;
      const otherNode = this.nodes.find((n) => n.id === other);
      if (otherNode?.workspaceId) related.add(otherNode.workspaceId);
    }

    return [...related];
  }

  colorForStatus(status: ScanStatus): string {
    return STATUS_COLORS[status] ?? STATUS_COLORS.idle;
  }
}

function edge(
  from: string,
  to: string,
  kind: MeshEdgeKind,
  weight: number,
  label?: string,
): MeshEdge {
  return {
    id: `e-${from}-${to}-${kind}`,
    from,
    to,
    kind,
    weight,
    bidirectional: kind === 'correlates' || kind === 'hebbian',
    label,
  };
}

function scoreToActivation(score: number): number {
  // High health → calm mid activation; low score → high alert activation
  const risk = 1 - clamp01(score / 100);
  return clamp01(0.2 + risk * 0.7);
}

function statusFromScore(score: number, fallback: ScanStatus): ScanStatus {
  if (fallback === 'scanning' || fallback === 'stale') return fallback;
  if (score >= 85) return 'healthy';
  if (score >= 60) return 'warning';
  if (score < 60) return 'critical';
  return fallback;
}

function clamp01(n: number): number {
  return Math.max(0, Math.min(1, n));
}

function unique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

async function atomicWriteJson(filePath: string, data: unknown): Promise<void> {
  const tmp = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(tmp, JSON.stringify(data, null, 2), 'utf8');
  await rename(tmp, filePath);
}
