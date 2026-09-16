import cors from 'cors';
import express from 'express';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocketServer, type WebSocket } from 'ws';
import type { WsClientMessage, WsServerMessage } from '../shared/types.js';
import { SWIFT_GUIDE_CONCEPTS, isSwiftConceptNodeId } from '../shared/swiftGuide.js';
import { ScanOrchestrator } from './core/scan-orchestrator.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.env.PORT ?? 8787);

const app = express();
app.use(cors());
app.use(express.json());

const orchestrator = new ScanOrchestrator({
  rootDir: ROOT,
  intervalMs: Number(process.env.SCAN_INTERVAL_MS ?? 15_000),
  dataDir: path.join(ROOT, 'data'),
});

await orchestrator.init();

app.get('/api/health', (_req, res) => {
  res.json({
    ok: true,
    service: 'personal-assistant',
    scanning: orchestrator.isRunning() || orchestrator.isScanning(),
  });
});

app.get('/api/state', (_req, res) => {
  res.json(orchestrator.getFullState());
});

app.get('/api/workspaces', (_req, res) => {
  res.json(orchestrator.getWorkspaces());
});

app.get('/api/workspaces/:id', (req, res) => {
  const ws = orchestrator.getWorkspaces().find((w) => w.id === req.params.id || w.kind === req.params.id);
  if (!ws) {
    res.status(404).json({ error: 'workspace_not_found' });
    return;
  }
  res.json(ws);
});

app.post('/api/scan', async (_req, res) => {
  const result = await orchestrator.runOnce();
  res.json(result);
});

app.post('/api/scan/start', (_req, res) => {
  orchestrator.start();
  res.json({ scanning: true });
});

app.post('/api/scan/stop', (_req, res) => {
  orchestrator.stop();
  res.json({ scanning: false });
});

app.get('/api/memory', (req, res) => {
  const q = typeof req.query.q === 'string' ? req.query.q : undefined;
  res.json(orchestrator.queryMemory(q));
});

app.post('/api/nodes/:id/focus', async (req, res) => {
  const id = req.params.id;
  if (isSwiftConceptNodeId(id)) {
    const conceptId = id.replace(/^swift-/, '');
    const result = await orchestrator.openConcept(conceptId);
    res.json(result);
    return;
  }
  const result = orchestrator.focusNode(id);
  res.json(result);
});

app.get('/api/guide', (_req, res) => {
  const state = orchestrator.getFullState();
  res.json({
    concepts: SWIFT_GUIDE_CONCEPTS,
    activeConceptId: state.activeConceptId ?? null,
    guideStep: state.guideStep ?? 0,
  });
});

app.post('/api/guide/start', async (_req, res) => {
  res.json(await orchestrator.guideStart());
});

app.post('/api/guide/next', async (_req, res) => {
  res.json(await orchestrator.guideNext());
});

app.post('/api/guide/prev', async (_req, res) => {
  res.json(await orchestrator.guidePrev());
});

app.post('/api/guide/concepts/:id', async (req, res) => {
  res.json(await orchestrator.openConcept(req.params.id));
});

const server = createServer(app);
const wss = new WebSocketServer({ server, path: '/ws' });

function send(ws: WebSocket, type: WsServerMessage['type'], payload: unknown) {
  const msg: WsServerMessage = { type, payload, at: new Date().toISOString() };
  if (ws.readyState === ws.OPEN) ws.send(JSON.stringify(msg));
}

function broadcast(type: WsServerMessage['type'], payload: unknown) {
  for (const client of wss.clients) send(client, type, payload);
}

orchestrator.on('tick', (payload) => broadcast('scan_tick', payload));
orchestrator.on('complete', (payload) => broadcast('scan_complete', payload));
orchestrator.on('state', (payload) => broadcast('state', payload));
orchestrator.on('memory_update', (payload) => broadcast('memory_update', payload));

wss.on('connection', (socket) => {
  send(socket, 'state', orchestrator.getFullState());

  socket.on('message', async (raw) => {
    let msg: WsClientMessage;
    try {
      msg = JSON.parse(String(raw)) as WsClientMessage;
    } catch {
      return;
    }

    switch (msg.type) {
      case 'start_scan':
        orchestrator.start();
        broadcast('state', orchestrator.getFullState());
        break;
      case 'stop_scan':
        orchestrator.stop();
        broadcast('state', orchestrator.getFullState());
        break;
      case 'focus_node': {
        const payload = msg.payload as { id?: string; nodeId?: string } | undefined;
        const id = payload?.nodeId ?? payload?.id;
        if (id) {
          if (isSwiftConceptNodeId(id)) {
            const conceptId = id.replace(/^swift-/, '');
            const focused = await orchestrator.openConcept(conceptId);
            send(socket, 'guide_focus', focused);
            send(socket, 'node_focus', focused);
            broadcast('state', orchestrator.getFullState());
          } else {
            const focused = orchestrator.focusNode(id);
            send(socket, 'node_focus', focused);
            broadcast('state', orchestrator.getFullState());
          }
        }
        break;
      }
      case 'open_workspace': {
        const payload = msg.payload as { id?: string; workspaceId?: string } | undefined;
        const id = payload?.workspaceId ?? payload?.id;
        if (id) {
          const focused = orchestrator.focusWorkspace(id);
          send(socket, 'node_focus', focused);
          broadcast('state', orchestrator.getFullState());
        }
        break;
      }
      case 'open_concept': {
        const conceptId =
          (msg.payload as { conceptId?: string; id?: string } | undefined)?.conceptId ??
          (msg.payload as { id?: string } | undefined)?.id;
        if (conceptId) {
          const focused = await orchestrator.openConcept(conceptId);
          send(socket, 'guide_focus', focused);
          send(socket, 'node_focus', focused);
          broadcast('state', orchestrator.getFullState());
        }
        break;
      }
      case 'guide_start': {
        const focused = await orchestrator.guideStart();
        send(socket, 'guide_focus', focused);
        send(socket, 'node_focus', focused);
        broadcast('state', orchestrator.getFullState());
        break;
      }
      case 'guide_next': {
        const focused = await orchestrator.guideNext();
        if (focused) {
          send(socket, 'guide_focus', focused);
          send(socket, 'node_focus', focused);
          broadcast('state', orchestrator.getFullState());
        }
        break;
      }
      case 'guide_prev': {
        const focused = await orchestrator.guidePrev();
        if (focused) {
          send(socket, 'guide_focus', focused);
          send(socket, 'node_focus', focused);
          broadcast('state', orchestrator.getFullState());
        }
        break;
      }
      case 'reinforce': {
        const edge = msg.payload as { from?: string; to?: string; delta?: number } | undefined;
        if (edge?.from && edge?.to) {
          orchestrator.reinforce(edge.from, edge.to, edge.delta ?? 0.05);
          broadcast('state', orchestrator.getFullState());
        }
        break;
      }
      case 'query_memory': {
        const q = (msg.payload as { q?: string } | undefined)?.q;
        send(socket, 'memory_update', orchestrator.queryMemory(q));
        break;
      }
      default:
        break;
    }
  });
});

// Auto-start continuous scanning so the brain map always scans
orchestrator.start();

server.listen(PORT, () => {
  console.log(`Personal Assistant neural mesh on http://localhost:${PORT}`);
});
