import type { NeuralMeshState, WorkspaceSnapshot } from '@shared/types';

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export async function fetchState(): Promise<NeuralMeshState> {
  const res = await fetch('/api/state');
  return parseJson<NeuralMeshState>(res);
}

export async function triggerScan(): Promise<NeuralMeshState | { ok: boolean }> {
  const res = await fetch('/api/scan', { method: 'POST' });
  return parseJson(res);
}

export async function fetchWorkspace(id: string): Promise<WorkspaceSnapshot> {
  const res = await fetch(`/api/workspaces/${encodeURIComponent(id)}`);
  return parseJson<WorkspaceSnapshot>(res);
}
