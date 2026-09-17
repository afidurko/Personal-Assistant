import cors from 'cors';
import express from 'express';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { WebSocketServer, type WebSocket } from 'ws';
import type { WsClientMessage, WsServerMessage } from '../shared/types.js';
import { SWIFT_GUIDE_CONCEPTS, isSwiftConceptNodeId } from '../shared/swiftGuide.js';
import { AGENT_LAYERS, MESH_AGENTS } from '../shared/agentLayers.js';
import { ScanOrchestrator } from './core/scan-orchestrator.js';
import { CamConverse } from './core/cam-converse.js';
import { CamAutonomy } from './core/cam-autonomy.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.env.PORT ?? 8787);

const app = express();
app.use(cors());
app.use(express.json());

const orchestrator = new ScanOrchestrator({
  rootDir: ROOT,
  intervalMs: Number(process.env.SCAN_INTERVAL_MS ?? 25_000),
  dataDir: path.join(ROOT, 'data'),
});

const converse = new CamConverse(ROOT);
const autonomy = new CamAutonomy(ROOT);
let micListeningHint = false;

await orchestrator.init();

function fullState() {
  return {
    ...orchestrator.getFullState(),
    camSelfTasks: autonomy.getTasks(),
  };
}

app.get('/api/health', (_req, res) => {
  res.json({
    ok: true,
    service: 'personal-assistant',
    assistant: 'Cam',
    scanning: orchestrator.isRunning() || orchestrator.isScanning(),
    capabilities: {
      mic: true,
      speak: true,
      cortex3d: true,
      autonomy: true,
      enabled: true,
    },
    session_id: converse.sessionId,
  });
});

app.get('/api/state', (_req, res) => {
  res.json(fullState());
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

app.get('/api/suggestions', (_req, res) => {
  res.json(orchestrator.getSuggestions());
});

app.get('/api/agents', (_req, res) => {
  res.json({
    layers: AGENT_LAYERS,
    agents: MESH_AGENTS,
    loopArmed: orchestrator.isIssueLoopArmed(),
    jobs: orchestrator.getLoopJobs(),
    lastCycle: orchestrator.getFullState().lastAgentCycle ?? null,
    camSelfTasks: autonomy.getTasks(),
    capacity: { selfTaskSlots: 64, loopJobHint: 80 },
  });
});

app.post('/api/agents/cycle', async (_req, res) => {
  const result = await orchestrator.runAgentCycle();
  res.json(result);
});

app.post('/api/agents/issue-loop/start', (_req, res) => {
  orchestrator.setIssueLoopArmed(true);
  res.json({ loopArmed: true, jobs: orchestrator.getLoopJobs() });
});

app.post('/api/agents/issue-loop/stop', (_req, res) => {
  orchestrator.setIssueLoopArmed(false);
  res.json({ loopArmed: false });
});

app.get('/api/cam/autonomy', (_req, res) => {
  res.json({
    tasks: autonomy.getTasks(),
    capacity: { selfTaskSlots: 64, loopJobHint: 80 },
    listening: micListeningHint,
  });
});

app.post('/api/cam/autonomy/tick', async (_req, res) => {
  const result = await autonomy.tick({
    workspaces: orchestrator.getWorkspaces(),
    loopJobs: orchestrator.getLoopJobs(),
    listening: micListeningHint,
  });
  res.json(result);
});

app.get('/api/session', (_req, res) => {
  res.json({
    session_id: converse.sessionId,
    started: converse.started,
    history: converse.getHistory(),
  });
});

app.post('/api/turn', async (req, res) => {
  const body = req.body as { text?: string; transcript?: string; source?: string };
  const text = String(body.text ?? body.transcript ?? '');
  const source = String(body.source ?? 'text');
  const reply = await converse.turn(text, source);
  // Pulse autonomy when Aaron talks so Cam keeps self-tasks warm
  void autonomy.tick({
    workspaces: orchestrator.getWorkspaces(),
    loopJobs: orchestrator.getLoopJobs(),
    listening: true,
  });
  res.json(reply);
});

app.post('/api/spike/mic', (req, res) => {
  micListeningHint = true;
  const body = req.body as { purpose?: string; transcript?: string };
  res.json({
    ok: true,
    sense: 'sense.ios.mic',
    purpose: body.purpose ?? 'conversation',
    accepted: true,
  });
});

app.post('/api/spike/mic/stop', (_req, res) => {
  micListeningHint = false;
  res.json({ ok: true, listening: false });
});

app.post('/api/spike/camera', (req, res) => {
  const body = req.body as { purpose?: string };
  res.json({
    ok: true,
    sense: 'sense.ios.camera',
    purpose: body.purpose ?? 'presence',
    accepted: true,
  });
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

// Static assets for Cam face, 3D cortex, and live-activity JSON the cortex polls
app.use('/identity', express.static(path.join(ROOT, 'identity')));
app.use('/vault', express.static(path.join(ROOT, 'vault')));
app.use('/config', express.static(path.join(ROOT, 'config')));
app.use('/viz', express.static(path.join(ROOT, 'visualizations')));
app.use('/companions', express.static(path.join(ROOT, 'companions')));
// Relative fetches from /viz/connectome → ../../vault|config|identity
app.use('/visualizations', express.static(path.join(ROOT, 'visualizations')));

const distWeb = path.join(ROOT, 'dist');
app.use(express.static(distWeb));

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
orchestrator.on('state', () => broadcast('state', fullState()));
orchestrator.on('memory_update', (payload) => broadcast('memory_update', payload));
orchestrator.on('agent_cycle', (payload) => broadcast('agent_cycle', payload));
orchestrator.on('loop_update', (payload) => broadcast('loop_update', payload));

wss.on('connection', (socket) => {
  send(socket, 'state', fullState());

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
        broadcast('state', fullState());
        break;
      case 'stop_scan':
        orchestrator.stop();
        broadcast('state', fullState());
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
            broadcast('state', fullState());
          } else {
            const focused = orchestrator.focusNode(id);
            send(socket, 'node_focus', focused);
            broadcast('state', fullState());
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
          broadcast('state', fullState());
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
          broadcast('state', fullState());
        }
        break;
      }
      case 'guide_start': {
        const focused = await orchestrator.guideStart();
        send(socket, 'guide_focus', focused);
        send(socket, 'node_focus', focused);
        broadcast('state', fullState());
        break;
      }
      case 'guide_next': {
        const focused = await orchestrator.guideNext();
        if (focused) {
          send(socket, 'guide_focus', focused);
          send(socket, 'node_focus', focused);
          broadcast('state', fullState());
        }
        break;
      }
      case 'guide_prev': {
        const focused = await orchestrator.guidePrev();
        if (focused) {
          send(socket, 'guide_focus', focused);
          send(socket, 'node_focus', focused);
          broadcast('state', fullState());
        }
        break;
      }
      case 'run_agent_cycle': {
        const result = await orchestrator.runAgentCycle();
        send(socket, 'agent_cycle', result);
        broadcast('state', fullState());
        break;
      }
      case 'start_issue_loop': {
        orchestrator.setIssueLoopArmed(true);
        send(socket, 'loop_update', orchestrator.getLoopJobs());
        broadcast('state', fullState());
        break;
      }
      case 'stop_issue_loop': {
        orchestrator.setIssueLoopArmed(false);
        send(socket, 'loop_update', orchestrator.getLoopJobs());
        broadcast('state', fullState());
        break;
      }
      case 'reinforce': {
        const edge = msg.payload as { from?: string; to?: string; delta?: number } | undefined;
        if (edge?.from && edge?.to) {
          orchestrator.reinforce(edge.from, edge.to, edge.delta ?? 0.05);
          broadcast('state', fullState());
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

// Cam background autonomy — self-improve tasks while she listens
const autonomyMs = Number(process.env.CAM_AUTONOMY_MS ?? 18_000);
const autonomyTimer = setInterval(() => {
  void autonomy
    .tick({
      workspaces: orchestrator.getWorkspaces(),
      loopJobs: orchestrator.getLoopJobs(),
      listening: micListeningHint,
    })
    .then((result) => {
      if (result.spawned > 0 || result.advanced > 0) {
        broadcast('autonomy_update', {
          tasks: autonomy.getTasks(),
          loopJobs: orchestrator.getLoopJobs(),
          spawned: result.spawned,
          advanced: result.advanced,
        });
      }
    })
    .catch(() => undefined);
}, autonomyMs);
autonomyTimer.unref?.();
// Kick once immediately so spawn bay isn't empty
void autonomy.tick({
  workspaces: orchestrator.getWorkspaces(),
  loopJobs: orchestrator.getLoopJobs(),
  listening: false,
}).then(() => {
  broadcast('autonomy_update', {
    tasks: autonomy.getTasks(),
    loopJobs: orchestrator.getLoopJobs(),
  });
});

server.listen(PORT, () => {
  console.log(`Cam neural mesh + 3D cortex on http://localhost:${PORT}`);
  console.log(`  3D viz → http://localhost:${PORT}/viz/connectome/`);
});
