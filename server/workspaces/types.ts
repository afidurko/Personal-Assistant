import type { WorkspaceKind, WorkspaceSnapshot } from '../../shared/types.js';

export interface WorkspaceScanner {
  id: string;
  kind: WorkspaceKind;
  scan(rootDir: string): Promise<WorkspaceSnapshot>;
}
