import { create } from 'zustand';
import type {
  BrainNode,
  MemoryTrace,
  MeshEdge,
  NeuralMeshState,
  WorkspaceSnapshot,
} from '@shared/types';

const emptyState: NeuralMeshState = {
  nodes: [],
  edges: [],
  workspaces: [],
  memory: [],
  scanning: false,
  lastCycleAt: null,
  cycleCount: 0,
};

export interface MeshStore extends NeuralMeshState {
  selectedNodeId: string | null;
  selectedWorkspaceId: string | null;
  connected: boolean;
  setConnected: (connected: boolean) => void;
  setStateFromServer: (state: Partial<NeuralMeshState> | NeuralMeshState) => void;
  selectNode: (nodeId: string | null) => void;
  selectWorkspace: (workspaceId: string | null) => void;
  setScanning: (scanning: boolean) => void;
  upsertMemory: (traces: MemoryTrace[]) => void;
}

function resolveWorkspaceFromNode(
  nodes: BrainNode[],
  nodeId: string | null,
): string | null {
  if (!nodeId) return null;
  return nodes.find((n) => n.id === nodeId)?.workspaceId ?? null;
}

function resolveNodeFromWorkspace(
  nodes: BrainNode[],
  workspaceId: string | null,
): string | null {
  if (!workspaceId) return null;
  return nodes.find((n) => n.workspaceId === workspaceId)?.id ?? null;
}

export const useMeshStore = create<MeshStore>((set, get) => ({
  ...emptyState,
  selectedNodeId: null,
  selectedWorkspaceId: null,
  connected: false,

  setConnected: (connected) => set({ connected }),

  setStateFromServer: (incoming) => {
    const prev = get();
    const next: Partial<NeuralMeshState> = { ...incoming };

    set({
      nodes: (next.nodes as BrainNode[] | undefined) ?? prev.nodes,
      edges: (next.edges as MeshEdge[] | undefined) ?? prev.edges,
      workspaces: (next.workspaces as WorkspaceSnapshot[] | undefined) ?? prev.workspaces,
      memory: (next.memory as MemoryTrace[] | undefined) ?? prev.memory,
      scanning: typeof next.scanning === 'boolean' ? next.scanning : prev.scanning,
      lastCycleAt:
        next.lastCycleAt !== undefined ? next.lastCycleAt : prev.lastCycleAt,
      cycleCount:
        typeof next.cycleCount === 'number' ? next.cycleCount : prev.cycleCount,
    });
  },

  selectNode: (nodeId) => {
    const { nodes } = get();
    set({
      selectedNodeId: nodeId,
      selectedWorkspaceId: resolveWorkspaceFromNode(nodes, nodeId),
    });
  },

  selectWorkspace: (workspaceId) => {
    const { nodes } = get();
    set({
      selectedWorkspaceId: workspaceId,
      selectedNodeId: resolveNodeFromWorkspace(nodes, workspaceId),
    });
  },

  setScanning: (scanning) => set({ scanning }),

  upsertMemory: (traces) => {
    if (!traces.length) return;
    const { memory } = get();
    const byId = new Map(memory.map((m) => [m.id, m]));
    for (const t of traces) byId.set(t.id, t);
    const merged = Array.from(byId.values()).sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );
    set({ memory: merged.slice(0, 80) });
  },
}));
