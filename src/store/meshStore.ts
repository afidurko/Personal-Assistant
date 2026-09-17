import { create } from 'zustand';
import type {
  AgentCycleResult,
  BrainNode,
  LoopJob,
  MemoryTrace,
  MeshEdge,
  NeuralMeshState,
  SuggestiveImplementation,
  WorkspaceSnapshot,
} from '@shared/types';
import { SWIFT_GUIDE_BY_ID, type SwiftConceptId } from '@shared/swiftGuide';

const emptyState: NeuralMeshState = {
  nodes: [],
  edges: [],
  workspaces: [],
  memory: [],
  scanning: false,
  lastCycleAt: null,
  cycleCount: 0,
  activeConceptId: null,
  guideStep: 0,
  suggestions: [],
  loopJobs: [],
  lastAgentCycle: null,
};

export interface MeshStore extends NeuralMeshState {
  selectedNodeId: string | null;
  selectedWorkspaceId: string | null;
  connected: boolean;
  setConnected: (connected: boolean) => void;
  setStateFromServer: (state: Partial<NeuralMeshState> | NeuralMeshState) => void;
  selectNode: (nodeId: string | null) => void;
  selectWorkspace: (workspaceId: string | null) => void;
  selectConcept: (conceptId: string | null) => void;
  setScanning: (scanning: boolean) => void;
  upsertMemory: (traces: MemoryTrace[]) => void;
}

function resolveWorkspaceFromNode(
  nodes: BrainNode[],
  nodeId: string | null,
): string | null {
  if (!nodeId) return null;
  const node = nodes.find((n) => n.id === nodeId);
  if (node?.workspaceId) return node.workspaceId;
  if (node?.conceptId) {
    const concept = SWIFT_GUIDE_BY_ID[node.conceptId as SwiftConceptId];
    const kind = concept?.relatedWorkspaceKinds[0];
    return kind ? `workspace-${kind}` : null;
  }
  return null;
}

function workspaceAliases(workspaceId: string): string[] {
  const aliases = new Set<string>([workspaceId]);
  if (workspaceId.startsWith('workspace-')) {
    aliases.add(workspaceId.slice('workspace-'.length));
  } else {
    aliases.add(`workspace-${workspaceId}`);
  }
  return [...aliases];
}

function resolveNodeFromWorkspace(
  nodes: BrainNode[],
  workspaceId: string | null,
): string | null {
  if (!workspaceId) return null;
  const aliases = workspaceAliases(workspaceId);
  return (
    nodes.find(
      (n) =>
        (n.workspaceId && aliases.includes(n.workspaceId)) ||
        aliases.some((a) => n.id === `ws-${a}` || n.id === a),
    )?.id ?? null
  );
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
      activeConceptId:
        next.activeConceptId !== undefined ? next.activeConceptId : prev.activeConceptId,
      guideStep: typeof next.guideStep === 'number' ? next.guideStep : prev.guideStep,
      suggestions:
        (next.suggestions as SuggestiveImplementation[] | undefined) ?? prev.suggestions,
      loopJobs: (next.loopJobs as LoopJob[] | undefined) ?? prev.loopJobs,
      lastAgentCycle:
        next.lastAgentCycle !== undefined
          ? (next.lastAgentCycle as AgentCycleResult | null)
          : prev.lastAgentCycle,
    });
  },

  selectNode: (nodeId) => {
    const { nodes } = get();
    const node = nodeId ? nodes.find((n) => n.id === nodeId) : null;
    set({
      selectedNodeId: nodeId,
      selectedWorkspaceId: resolveWorkspaceFromNode(nodes, nodeId),
      activeConceptId: node?.conceptId ?? get().activeConceptId,
    });
  },

  selectWorkspace: (workspaceId) => {
    const { nodes } = get();
    set({
      selectedWorkspaceId: workspaceId,
      selectedNodeId: resolveNodeFromWorkspace(nodes, workspaceId),
    });
  },

  selectConcept: (conceptId) => {
    const { nodes } = get();
    const node = conceptId
      ? nodes.find((n) => n.conceptId === conceptId || n.id === `swift-${conceptId}`)
      : null;
    const concept = conceptId
      ? SWIFT_GUIDE_BY_ID[conceptId as SwiftConceptId]
      : null;
    set({
      activeConceptId: conceptId,
      guideStep: concept?.tourOrder ?? get().guideStep,
      selectedNodeId: node?.id ?? null,
      selectedWorkspaceId: concept
        ? `workspace-${concept.relatedWorkspaceKinds[0]}`
        : get().selectedWorkspaceId,
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
