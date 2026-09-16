import { useEffect, useRef } from 'react';
import type {
  MemoryTrace,
  NeuralMeshState,
  ScanCycleResult,
  WsClientMessage,
  WsServerMessage,
} from '@shared/types';
import { useMeshStore } from '@/store/meshStore';
import { fetchState } from '@/api/client';

const RECONNECT_BASE_MS = 800;
const RECONNECT_MAX_MS = 12_000;

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws`;
}

export function useMeshSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);

  const setConnected = useMeshStore((s) => s.setConnected);
  const setStateFromServer = useMeshStore((s) => s.setStateFromServer);
  const setScanning = useMeshStore((s) => s.setScanning);
  const upsertMemory = useMeshStore((s) => s.upsertMemory);
  const selectNode = useMeshStore((s) => s.selectNode);

  useEffect(() => {
    unmountedRef.current = false;

    const handleMessage = (raw: MessageEvent) => {
      let msg: WsServerMessage;
      try {
        msg = JSON.parse(String(raw.data)) as WsServerMessage;
      } catch {
        return;
      }

      switch (msg.type) {
        case 'state': {
          const payload = msg.payload as NeuralMeshState;
          setStateFromServer(payload);
          if (typeof payload.scanning === 'boolean') {
            setScanning(payload.scanning);
          }
          break;
        }
        case 'scan_tick': {
          const payload = msg.payload as { cycle?: number; at?: string };
          setScanning(true);
          setStateFromServer({
            scanning: true,
            cycleCount: typeof payload.cycle === 'number' ? payload.cycle : undefined,
            lastCycleAt: payload.at ?? undefined,
          });
          break;
        }
        case 'scan_complete': {
          const payload = msg.payload as ScanCycleResult;
          setStateFromServer({
            workspaces: payload.workspaces,
            scanning: true,
          });
          if (Array.isArray(payload.memoryWrites)) {
            upsertMemory(payload.memoryWrites);
          }
          break;
        }
        case 'memory_update': {
          const traces = msg.payload as MemoryTrace[] | { memory: MemoryTrace[] };
          const list = Array.isArray(traces) ? traces : traces.memory;
          if (list) upsertMemory(list);
          break;
        }
        case 'node_focus': {
          const payload = msg.payload as { nodeId?: string };
          if (payload?.nodeId) selectNode(payload.nodeId);
          break;
        }
        default:
          break;
      }
    };

    const connect = () => {
      if (unmountedRef.current) return;

      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;

      ws.addEventListener('open', () => {
        retryRef.current = 0;
        setConnected(true);
        void fetchState()
          .then((state) => setStateFromServer(state))
          .catch(() => {
            /* server may not be up yet; WS will push state */
          });
      });

      ws.addEventListener('message', handleMessage);

      ws.addEventListener('close', () => {
        setConnected(false);
        wsRef.current = null;
        if (unmountedRef.current) return;
        const delay = Math.min(
          RECONNECT_BASE_MS * 2 ** retryRef.current,
          RECONNECT_MAX_MS,
        );
        retryRef.current += 1;
        timerRef.current = setTimeout(connect, delay);
      });

      ws.addEventListener('error', () => {
        ws.close();
      });
    };

    connect();

    return () => {
      unmountedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      wsRef.current?.close();
      wsRef.current = null;
      setConnected(false);
    };
  }, [setConnected, setStateFromServer, setScanning, upsertMemory, selectNode]);

  const send = (message: WsClientMessage) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(message));
    return true;
  };

  return {
    send,
    startScan: () => {
      setScanning(true);
      return send({ type: 'start_scan' });
    },
    stopScan: () => {
      setScanning(false);
      return send({ type: 'stop_scan' });
    },
    focusNode: (nodeId: string) =>
      send({ type: 'focus_node', payload: { nodeId, id: nodeId } }),
    openWorkspace: (workspaceId: string) =>
      send({
        type: 'open_workspace',
        payload: { workspaceId, id: workspaceId },
      }),
  };
}

export type MeshSocketApi = ReturnType<typeof useMeshSocket>;
