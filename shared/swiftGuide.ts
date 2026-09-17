/** Swift Guide (A Swift Tour) concepts for interactive brain-map exploration */

import type { BrainRegion, WorkspaceKind } from './types.js';

export type SwiftConceptId =
  | 'simple-values'
  | 'control-flow'
  | 'functions-closures'
  | 'objects-classes'
  | 'enums-structs'
  | 'concurrency'
  | 'protocols-extensions'
  | 'error-handling'
  | 'generics';

export interface SwiftConcept {
  id: SwiftConceptId;
  title: string;
  tourOrder: number;
  region: BrainRegion;
  /** Accent for concept nodes (distinct from scan status colors) */
  color: string;
  summary: string;
  /** Playground-style prompt shown when the concept is focused */
  explore: string;
  sample: string;
  relatedWorkspaceKinds: WorkspaceKind[];
  /** Next concept in the guided tour */
  nextId: SwiftConceptId | null;
  tags: string[];
}

/**
 * Concept catalog inspired by Apple's "A Swift Tour" progressive guide:
 * short summaries, runnable-feeling samples, and jump-to-related topics.
 */
export const SWIFT_GUIDE_CONCEPTS: SwiftConcept[] = [
  {
    id: 'simple-values',
    title: 'Simple Values',
    tourOrder: 1,
    region: 'thalamus',
    color: '#7ec8e3',
    summary:
      'Constants and variables, type inference, strings, and collections — the atoms of a Swift program.',
    explore:
      'Prefer let until mutation is required. Watch how typed values keep the mesh honest.',
    sample: 'let nodes = 7\nvar pulse = 0.2\npulse += 0.1',
    relatedWorkspaceKinds: ['health', 'architecture'],
    nextId: 'control-flow',
    tags: ['basics', 'let', 'var', 'collections'],
  },
  {
    id: 'control-flow',
    title: 'Control Flow',
    tourOrder: 2,
    region: 'prefrontal',
    color: '#8eb5ff',
    summary:
      'if, switch, for-in, and while — branching and looping that shape decision paths through the map.',
    explore:
      'Trace a scan cycle: for each workspace, switch on status and route findings.',
    sample: 'for ws in workspaces {\n  switch ws.status {\n  case .critical: raise()\n  default: continue\n  }\n}',
    relatedWorkspaceKinds: ['architecture', 'health'],
    nextId: 'functions-closures',
    tags: ['if', 'switch', 'loops'],
  },
  {
    id: 'functions-closures',
    title: 'Functions & Closures',
    tourOrder: 3,
    region: 'cortex',
    color: '#9adbc8',
    summary:
      'Named functions and trailing closures compose behavior — scanners, reducers, and mesh updates.',
    explore:
      'Treat each workspace scan as a function; pipe results through a closure into memory.',
    sample: 'func scan(_ root: URL) async -> Snapshot {\n  await runAll(root)\n}\ntraces.map { $0.salience }',
    relatedWorkspaceKinds: ['architecture', 'improvements'],
    nextId: 'objects-classes',
    tags: ['func', 'closure', 'async'],
  },
  {
    id: 'objects-classes',
    title: 'Objects & Classes',
    tourOrder: 4,
    region: 'prefrontal',
    color: '#b8a4e8',
    summary:
      'Reference types with inheritance and identity — orchestrators that own long-lived mesh state.',
    explore:
      'NeuralMesh and ScanOrchestrator behave like classes: shared identity, mutating methods.',
    sample: 'class ScanOrchestrator {\n  func start() { /* continuous loop */ }\n}',
    relatedWorkspaceKinds: ['architecture', 'health'],
    nextId: 'enums-structs',
    tags: ['class', 'identity', 'oop'],
  },
  {
    id: 'enums-structs',
    title: 'Enums & Structs',
    tourOrder: 5,
    region: 'cerebellum',
    color: '#e6c07b',
    summary:
      'Value types and exhaustive enums model status, severity, and snapshots without shared mutation.',
    explore:
      'ScanStatus and Finding are natural enums/structs — safe to copy across the mesh.',
    sample: 'enum ScanStatus { case idle, scanning, healthy, warning, critical }\nstruct Finding { let title: String }',
    relatedWorkspaceKinds: ['updates', 'architecture'],
    nextId: 'concurrency',
    tags: ['enum', 'struct', 'value-types'],
  },
  {
    id: 'concurrency',
    title: 'Concurrency',
    tourOrder: 6,
    region: 'insula',
    color: '#5ec4d4',
    summary:
      'async/await and structured tasks run workspace scanners in parallel without blocking the UI.',
    explore:
      'runAllScans uses Promise.all — the JS cousin of Swift concurrent tasks.',
    sample: 'async let health = scanHealth()\nasync let vulns = scanVulns()\nlet snaps = await [health, vulns]',
    relatedWorkspaceKinds: ['health', 'improvements'],
    nextId: 'protocols-extensions',
    tags: ['async', 'await', 'tasks'],
  },
  {
    id: 'protocols-extensions',
    title: 'Protocols & Extensions',
    tourOrder: 7,
    region: 'cortex',
    color: '#6ecf9a',
    summary:
      'Protocols define contracts; extensions add behavior — WorkspaceScanner is the mesh interface.',
    explore:
      'Each scanner conforms to one protocol so the orchestrator stays decoupled.',
    sample: 'protocol WorkspaceScanner {\n  func scan(_ root: URL) async -> Snapshot\n}',
    relatedWorkspaceKinds: ['architecture', 'improvements'],
    nextId: 'error-handling',
    tags: ['protocol', 'extension', 'abstraction'],
  },
  {
    id: 'error-handling',
    title: 'Error Handling',
    tourOrder: 8,
    region: 'amygdala',
    color: '#e88a7a',
    summary:
      'throw, try, and Result turn failures into data — vulnerability findings instead of silent crashes.',
    explore:
      'Map thrown scanner errors into critical findings so the amygdala node lights coral.',
    sample: 'do {\n  try await audit()\n} catch {\n  emit(.critical, error)\n}',
    relatedWorkspaceKinds: ['vulnerability', 'health'],
    nextId: 'generics',
    tags: ['throw', 'try', 'Result'],
  },
  {
    id: 'generics',
    title: 'Generics',
    tourOrder: 9,
    region: 'insula',
    color: '#4ecdc4',
    summary:
      'Type parameters keep mesh helpers reusable — query<T>, ranked memory, typed activation maps.',
    explore:
      'PersistentMemory.query works across tags and text with one generic ranking pipeline.',
    sample: 'func ranked<T>(_ items: [T], by: (T) -> Double) -> [T] {\n  items.sorted { by($0) > by($1) }\n}',
    relatedWorkspaceKinds: ['improvements', 'architecture'],
    nextId: null,
    tags: ['generics', 'reuse', 'types'],
  },
];

export const SWIFT_GUIDE_BY_ID: Record<SwiftConceptId, SwiftConcept> = Object.fromEntries(
  SWIFT_GUIDE_CONCEPTS.map((c) => [c.id, c]),
) as Record<SwiftConceptId, SwiftConcept>;

export function conceptNodeId(id: SwiftConceptId): string {
  return `swift-${id}`;
}

export function isSwiftConceptNodeId(nodeId: string): boolean {
  return nodeId.startsWith('swift-');
}
