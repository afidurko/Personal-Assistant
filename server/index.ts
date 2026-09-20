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
import { RuntimeStore } from './core/runtime-store.js';
import { SystemBridge } from './core/system-bridge.js';
import { a2fStatus } from './avatar/a2f-bridge.js';
import { higgsfieldStatus, runHiggsfield, underRoot } from './avatar/higgsfield.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.env.PORT ?? 8787);

const app = express();
app.use(cors());
app.use(express.json());

const runtime = new RuntimeStore(ROOT);
await runtime.ensure();

const orchestrator = new ScanOrchestrator({
  rootDir: ROOT,
  intervalMs: Number(process.env.SCAN_INTERVAL_MS ?? 25_000),
  dataDir: path.join(ROOT, 'data'),
});

const converse = new CamConverse(ROOT);
const autonomy = new CamAutonomy(runtime);
const bridge = new SystemBridge(ROOT, runtime);
let micListeningHint = false;

await orchestrator.init();

function fullState() {
  return {
    ...orchestrator.getFullState(),
    camSelfTasks: autonomy.getTasks(),
  };
}

/** Compact fingerprint so we can skip identical full-state broadcasts. */
function stateFingerprint(state: ReturnType<typeof fullState>): string {
  return JSON.stringify({
    cycle: state.cycleCount,
    scanning: state.scanning,
    jobs: (state.loopJobs ?? []).map((j) => [j.id, j.status, j.attempts]),
    tasks: (state.camSelfTasks ?? []).map((t) => [t.id, t.status]),
    scores: (state.workspaces ?? []).map((w) => [w.id, w.score, w.status]),
    guide: [state.activeConceptId, state.guideStep],
    agentEff: state.lastAgentCycle?.efficiencyGain ?? null,
  });
}

let lastStateFingerprint = '';

app.get('/api/health', async (_req, res) => {
  const system = await bridge.status({
    sessionId: converse.sessionId,
    scanning: orchestrator.isRunning() || orchestrator.isScanning(),
    listening: micListeningHint,
  });
  const voicePolicy = await converse.voiceAddons.loadPolicy();
  res.json({
    ok: system.ok,
    service: 'personal-assistant',
    assistant: 'Cam',
    scanning: orchestrator.isRunning() || orchestrator.isScanning(),
    listening: micListeningHint,
    overall: system.overall,
    pieces: system.pieces.length,
    capabilities: {
      mic: true,
      speak: true,
      cortex3d: true,
      autonomy: true,
      system_bridge: true,
      connectome_kernel: true,
      trajectory_physics: true,
      enabled: true,
      aaron_voice_only: true,
      voice_addons: true,
    },
    session_id: converse.sessionId,
    circadian: system.circadian,
    blockers: system.blockers?.length ?? 0,
    voice_gate: voicePolicy,
    voice_gate_stats: converse.getVoiceStats(),
  });
});

app.get('/api/system', async (_req, res) => {
  const system = await bridge.status({
    sessionId: converse.sessionId,
    scanning: orchestrator.isRunning() || orchestrator.isScanning(),
    listening: micListeningHint,
  });
  res.json(system);
});

app.post('/api/system/route', async (req, res) => {
  const body = req.body as { sense?: string; goal?: string };
  const sense = String(body.sense ?? 'sense.chat.aaron');
  const goal = String(body.goal ?? '');
  const route = await bridge.routeSense(sense, goal);
  res.json(route);
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

app.get('/api/avatar/a2f', async (_req, res) => {
  res.json(await a2fStatus());
});

app.get('/api/avatar/higgsfield', async (_req, res) => {
  res.json(await higgsfieldStatus());
});

app.post('/api/avatar/higgsfield/speak', async (req, res) => {
  const body = req.body as {
    text?: string;
    image?: string;
    audio?: string;
    image_url?: string;
    audio_url?: string;
    live?: boolean;
    quality?: string;
    duration?: number;
  };
  const live = Boolean(body.live);
  if (live && !['1', 'true', 'yes', 'on'].includes(String(process.env.HIGGSFIELD_LIVE || '').toLowerCase())) {
    res.status(403).json({
      ok: false,
      error: 'higgsfield_live_disabled',
      detail: 'Set HIGGSFIELD_LIVE=1 to spend. /api/turn never calls this.',
    });
    return;
  }
  const args = ['speak', '--text', String(body.text || 'Hello Aaron')];
  if (!live) args.push('--dry-run');
  else args.push('--live');
  const image = underRoot(body.image);
  const audio = underRoot(body.audio);
  if (image) args.push('--image', image);
  if (audio) args.push('--audio', audio);
  if (body.image_url) args.push('--image-url', String(body.image_url));
  if (body.audio_url) args.push('--audio-url', String(body.audio_url));
  if (body.quality) args.push('--quality', String(body.quality));
  if (body.duration) args.push('--duration', String(body.duration));
  const result = await runHiggsfield(args);
  res.status(result.ok ? 200 : 400).json(result);
});

app.get('/api/session', (_req, res) => {
  res.json({
    session_id: converse.sessionId,
    started: converse.started,
    history: converse.getHistory(),
  });
});

app.post('/api/turn', async (req, res) => {
  const body = req.body as {
    text?: string;
    transcript?: string;
    source?: string;
    aaron_voice_score?: number;
    aaronVoiceScore?: number;
    enrolled?: boolean;
    multi_speaker_hint?: boolean;
    device_id?: string;
  };
  const text = String(body.text ?? body.transcript ?? '');
  const source = String(body.source ?? 'text');
  const scoreRaw = body.aaron_voice_score ?? body.aaronVoiceScore;
  const aaronVoiceScore =
    source === 'mic' || source === 'speech'
      ? typeof scoreRaw === 'number'
        ? scoreRaw
        : null
      : undefined;

  // Identity physics: mic without score is rejected by kernel
  if ((source === 'mic' || source === 'speech') && aaronVoiceScore == null) {
    res.status(403).json({
      error: 'aaron_voice_required',
      detail: 'Mic turns require aaron_voice_score ≥ identity threshold (or use text)',
    });
    return;
  }

  const reply = await converse.turn({
    text,
    source,
    aaron_voice_score: aaronVoiceScore ?? body.aaron_voice_score,
    enrolled: body.enrolled,
    multi_speaker_hint: body.multi_speaker_hint,
    device_id: body.device_id,
  });
  if (reply.rejected) {
    res.status(403).json(reply);
    return;
  }
  const bridged = await bridge.onTurn(text, source, { aaronVoiceScore });
  // Pulse autonomy when Aaron talks so Cam keeps self-tasks warm
  void autonomy.tick({
    workspaces: orchestrator.getWorkspaces(),
    loopJobs: orchestrator.getLoopJobs(),
    listening: true,
  });
  res.json({
    ...reply,
    bridge: {
      route: bridged.route,
      activities: bridged.activities.length,
      execution: bridged.execution,
      memory: bridged.memory,
    },
  });
});

app.post('/api/voice/gate/reject', async (req, res) => {
  const body = req.body as {
    score?: number;
    threshold?: number;
    reason?: string;
    source?: string;
    multi_speaker_hint?: boolean;
    device_id?: string;
  };
  const at = new Date().toISOString();
  await converse.voiceAddons.recordReject({
    at,
    source: String(body.source ?? 'mic'),
    score: Number(body.score ?? 0),
    threshold: Number(body.threshold ?? 0.88),
    reason: String(body.reason ?? 'client_reject'),
    multi_speaker_hint: Boolean(body.multi_speaker_hint),
    device_id: body.device_id,
  });
  res.json({ ok: true, stats: converse.getVoiceStats() });
});

app.get('/api/voice/profile', async (_req, res) => {
  const saved = await converse.voiceAddons.loadSavedProfile();
  res.json({ ok: true, profile: saved });
});

app.post('/api/voice/profile', async (req, res) => {
  const body = req.body as { profile?: unknown };
  if (!body.profile) {
    res.status(400).json({ ok: false, error: 'profile_required' });
    return;
  }
  const pathWritten = await converse.voiceAddons.saveProfile(body.profile);
  res.json({ ok: true, path: pathWritten });
});

app.post('/api/spike/mic', async (req, res) => {
  micListeningHint = true;
  const body = req.body as {
    purpose?: string;
    transcript?: string;
    aaron_voice_score?: number;
  };
  const purpose = body.purpose ?? 'conversation';
  const bridged = await bridge.onMicSpike(purpose);
  res.json({
    ok: true,
    sense: 'sense.ios.mic',
    purpose,
    aaron_voice_score: body.aaron_voice_score ?? null,
    accepted: bridged.route.accepted !== false,
    route: bridged.route,
    activities: bridged.activities.length,
    execution: bridged.execution,
  });
});

app.post('/api/spike/aaron.voice', async (req, res) => {
  const body = req.body as {
    score?: number;
    enrolled?: boolean;
    multi_speaker_hint?: boolean;
    device_id?: string;
  };
  const score = typeof body.score === 'number' ? body.score : 0;
  const gate = await converse.voiceAddons.evaluateWithAddons(
    {
      source: 'mic',
      aaron_voice_score: score,
      enrolled: body.enrolled !== false,
      multi_speaker_hint: Boolean(body.multi_speaker_hint),
    },
    { note: false },
  );
  res.json({
    ok: true,
    sense: 'sense.aaron.voice',
    score,
    enrolled: Boolean(body.enrolled),
    multi_speaker_hint: Boolean(body.multi_speaker_hint),
    device_id: body.device_id ?? 'unknown',
    threshold: gate.threshold,
    accepted: gate.accept,
    gate,
    voice_stats: converse.getVoiceStats(),
  });
});

app.post('/api/spike/mic/stop', (_req, res) => {
  micListeningHint = false;
  res.json({ ok: true, listening: false });
});

app.post('/api/spike/camera', async (req, res) => {
  const body = req.body as { purpose?: string };
  const purpose = body.purpose ?? 'presence';
  const bridged = await bridge.onCameraSpike(purpose);
  res.json({
    ok: true,
    sense: 'sense.ios.camera',
    purpose,
    accepted: bridged.route.accepted !== false,
    route: bridged.route,
    activities: bridged.activities.length,
    execution: bridged.execution,
  });
});

app.post('/api/system/rehearse', async (_req, res) => {
  const steps: Array<{ id: string; ok: boolean; detail: string }> = [];
  const chat = await bridge.onTurn('system rehearsal ping', 'text');
  steps.push({
    id: 'turn_text',
    ok: chat.route.accepted,
    detail: `motors=${chat.route.motor_plan.join(',')}`,
  });
  const reject = await bridge.routeSense('sense.ios.mic', 'adversarial', {
    source: 'mic',
    aaronVoiceScore: 0.1,
  });
  steps.push({
    id: 'identity_reject',
    ok: !reject.accepted,
    detail: reject.reason || 'rejected',
  });
  const kill = await bridge.routeSense('sense.chat.aaron', 'kill test', { kill: true });
  steps.push({
    id: 'kill_silence',
    ok: !kill.accepted && kill.motor_plan.length === 0,
    detail: kill.reason || 'silenced',
  });
  const ok = steps.every((s) => s.ok);
  res.json({ ok, at: new Date().toISOString(), steps, envelope: ok ? 'pass' : 'fail' });
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


const runtimeFiles = [
  'live-activity',
  'improve-tasks',
  'system-health',
  'tract-weights',
  'plasticity-timeline',
  'neurogenesis-columns',
] as const;

for (const name of runtimeFiles) {
  app.get(`/api/runtime/${name}`, async (_req, res) => {
    const data = await runtime.readJson(`${name}.json`, {});
    res.json(data);
  });
}

app.get('/api/runtime/activity-events', async (_req, res) => {
  try {
    const { readFile } = await import('node:fs/promises');
    const raw = await readFile(runtime.pathFor('activity-events.jsonl'), 'utf8');
    res.type('text/plain').send(raw);
  } catch {
    res.type('text/plain').send('');
  }
});

// Static assets for Cam face, 3D cortex, and live-activity JSON the cortex polls
app.get('/favicon.ico', (_req, res) => {
  res.redirect(302, '/favicon.svg');
});
app.use(express.static(path.join(ROOT, 'public')));
app.use('/higgsfield-clips', express.static(path.join(ROOT, 'data/higgsfield')));
app.use('/identity', express.static(path.join(ROOT, 'identity')));
app.use('/vault', express.static(path.join(ROOT, 'vault')));
app.use('/config', express.static(path.join(ROOT, 'config')));
app.use('/viz', express.static(path.join(ROOT, 'visualizations')));
app.use('/companions', express.static(path.join(ROOT, 'companions')));
// Relative fetches from /viz/connectome → ../../vault|config|identity
app.use('/visualizations', express.static(path.join(ROOT, 'visualizations')));

const distWeb = path.join(ROOT, 'dist');
app.use(express.static(distWeb));
// SPA fallback for production builds (API routes already registered above)
app.get('*', (req, res, next) => {
  if (req.path.startsWith('/api') || req.path.startsWith('/ws')) {
    next();
    return;
  }
  const index = path.join(distWeb, 'index.html');
  res.sendFile(index, (err) => {
    if (err) next();
  });
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

// Cortex push: activity fires on the bus the instant converse/motors settle
bridge.onActivity(({ live, activities, route }) => {
  broadcast('activity_update', { live, activities, route });
});

function broadcastState(force = false) {
  const state = fullState();
  const fp = stateFingerprint(state);
  if (!force && fp === lastStateFingerprint) return false;
  lastStateFingerprint = fp;
  broadcast('state', state);
  return true;
}

orchestrator.on('tick', (payload) => broadcast('scan_tick', payload));
orchestrator.on('complete', (payload) => {
  broadcast('scan_complete', payload);
  broadcastState();
});
orchestrator.on('state', () => broadcastState());
orchestrator.on('memory_update', (payload) => broadcast('memory_update', payload));
orchestrator.on('agent_cycle', (payload) => {
  broadcast('agent_cycle', payload);
  // Prefer delta event; full state only when fingerprint changes
  broadcastState();
});
orchestrator.on('loop_update', (payload) => {
  broadcast('loop_update', payload);
  broadcastState();
});

wss.on('connection', (socket) => {
  const state = fullState();
  lastStateFingerprint = stateFingerprint(state);
  send(socket, 'state', state);

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
        broadcastState();
        break;
      case 'stop_scan':
        orchestrator.stop();
        broadcastState();
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
            broadcastState();
          } else {
            const focused = orchestrator.focusNode(id);
            send(socket, 'node_focus', focused);
            broadcastState();
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
          broadcastState();
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
          broadcastState();
        }
        break;
      }
      case 'guide_start': {
        const focused = await orchestrator.guideStart();
        send(socket, 'guide_focus', focused);
        send(socket, 'node_focus', focused);
        broadcastState();
        break;
      }
      case 'guide_next': {
        const focused = await orchestrator.guideNext();
        if (focused) {
          send(socket, 'guide_focus', focused);
          send(socket, 'node_focus', focused);
          broadcastState();
        }
        break;
      }
      case 'guide_prev': {
        const focused = await orchestrator.guidePrev();
        if (focused) {
          send(socket, 'guide_focus', focused);
          send(socket, 'node_focus', focused);
          broadcastState();
        }
        break;
      }
      case 'run_agent_cycle': {
        const result = await orchestrator.runAgentCycle();
        send(socket, 'agent_cycle', result);
        broadcastState();
        break;
      }
      case 'start_issue_loop': {
        orchestrator.setIssueLoopArmed(true);
        send(socket, 'loop_update', orchestrator.getLoopJobs());
        broadcastState();
        break;
      }
      case 'stop_issue_loop': {
        orchestrator.setIssueLoopArmed(false);
        send(socket, 'loop_update', orchestrator.getLoopJobs());
        broadcastState();
        break;
      }
      case 'reinforce': {
        const edge = msg.payload as { from?: string; to?: string; delta?: number } | undefined;
        if (edge?.from && edge?.to) {
          orchestrator.reinforce(edge.from, edge.to, edge.delta ?? 0.05);
          broadcastState();
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
