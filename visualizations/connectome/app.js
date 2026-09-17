/* Cam Connectome — Brodmann cortex + columns + association mesh + spinal + mind map */
(() => {
  const REPOS = [
    { id: "nullclaw", label: "nullclaw", region: "brain" },
    { id: "nulltickets", label: "nulltickets", region: "spine" },
    { id: "nullboiler", label: "nullboiler", region: "brain" },
    { id: "nullhub", label: "nullhub", region: "brain" },
    { id: "jarvis", label: "Jarvis", region: "motor" },
    { id: "cline", label: "Cline", region: "motor" },
    { id: "paddledetection", label: "PaddleDetection", region: "sense" },
    { id: "llmavatartalk", label: "LLMAvatarTalk", region: "motor" },
    { id: "smart-second-brain", label: "smart-second-brain", region: "brain" },
    { id: "swiftguide", label: "SwiftGuide", special: true, region: "brain" },
    { id: "openclaw", label: "OpenClaw patterns", region: "motor" },
    { id: "assistant", label: "Assistant-", region: "motor" },
  ];

  // Brodmann functional areas (lateral cortex layout)
  const AREAS = {
    "area.dlpfc": { x: 340, y: 200, r: 34, label: "DLPFC", ba: "BA9/46", lobe: "frontal", repos: ["nullclaw", "nullboiler", "nullhub"] },
    "area.apfc": { x: 250, y: 160, r: 26, label: "aPFC", ba: "BA10", lobe: "frontal", repos: ["swiftguide", "nullclaw"] },
    "area.ofc": { x: 220, y: 260, r: 22, label: "OFC", ba: "BA11", lobe: "frontal", repos: ["nullhub"] },
    "area.broca": { x: 300, y: 300, r: 24, label: "Broca", ba: "BA44/45", lobe: "frontal", repos: ["llmavatartalk", "openclaw"] },
    "area.premotor": { x: 390, y: 280, r: 18, label: "PM/SMA", ba: "BA6", lobe: "frontal", repos: ["nullclaw"] },
    "area.motor": { x: 450, y: 260, r: 20, label: "M1", ba: "BA4", lobe: "frontal", repos: ["openclaw", "assistant"] },
    "area.parietal": { x: 520, y: 170, r: 28, label: "Parietal", ba: "BA5/7", lobe: "parietal", repos: ["jarvis"] },
    "area.wernicke": { x: 560, y: 280, r: 26, label: "Wernicke+", ba: "BA22/39/40", lobe: "temporoparietal", repos: ["smart-second-brain"] },
    "area.temporal": { x: 480, y: 380, r: 28, label: "Temporal", ba: "BA20/21/37", lobe: "temporal", repos: ["smart-second-brain", "nullclaw"] },
    "area.auditory": { x: 400, y: 400, r: 18, label: "Auditory", ba: "BA41/42", lobe: "temporal", repos: ["llmavatartalk"] },
    "area.visual": { x: 680, y: 320, r: 30, label: "Visual", ba: "BA17–19", lobe: "occipital", repos: ["paddledetection"] },
    "area.mtl": { x: 430, y: 470, r: 24, label: "MTL", ba: "memory", lobe: "medial_temporal", repos: ["smart-second-brain", "nulltickets"] },
    "area.cingulate": { x: 360, y: 120, r: 22, label: "ACC", ba: "BA24/32", lobe: "medial", repos: ["nullclaw"] },
  };

  const TRACTS = [
    { id: "tract.arcuate", a: "area.wernicke", b: "area.broca", label: "arcuate" },
    { id: "tract.slf", a: "area.parietal", b: "area.dlpfc", label: "SLF" },
    { id: "tract.uncinate", a: "area.ofc", b: "area.temporal", label: "uncinate" },
    { id: "tract.cingulum", a: "area.cingulate", b: "area.mtl", label: "cingulum" },
    { id: "tract.cingulum2", a: "area.mtl", b: "area.dlpfc", label: "cingulum" },
    { id: "tract.ilf", a: "area.visual", b: "area.temporal", label: "ILF" },
    { id: "tract.ifof", a: "area.visual", b: "area.apfc", label: "IFOF" },
    { id: "tract.corticospinal", a: "area.premotor", b: "area.motor", label: "CST" },
  ];

  // Columns (agents + loops) orbit their area
  const COLUMNS = [
    { id: "neuron.chief", area: "area.dlpfc", kind: "agent", label: "chief" },
    { id: "neuron.router", area: "area.dlpfc", kind: "agent", label: "router" },
    { id: "neuron.delegate_burst", area: "area.dlpfc", kind: "loop", label: "spawn" },
    { id: "neuron.cartographer", area: "area.apfc", kind: "agent", label: "map" },
    { id: "neuron.docs", area: "area.apfc", kind: "agent", label: "docs" },
    { id: "neuron.plan_loop", area: "area.apfc", kind: "loop", label: "plan↻" },
    { id: "neuron.boundary", area: "area.ofc", kind: "agent", label: "bound" },
    { id: "neuron.identity_gate", area: "area.ofc", kind: "loop", label: "ID↻" },
    { id: "neuron.comms", area: "area.broca", kind: "agent", label: "comms" },
    { id: "neuron.speak_loop", area: "area.broca", kind: "loop", label: "talk↻" },
    { id: "neuron.ops", area: "area.parietal", kind: "agent", label: "ops" },
    { id: "neuron.life_ops_loop", area: "area.parietal", kind: "loop", label: "life↻" },
    { id: "neuron.research", area: "area.temporal", kind: "agent", label: "research" },
    { id: "neuron.careers", area: "area.temporal", kind: "agent", label: "jobs" },
    { id: "neuron.watch_loop", area: "area.temporal", kind: "loop", label: "watch↻" },
    { id: "neuron.vision", area: "area.visual", kind: "agent", label: "vision" },
    { id: "neuron.enroll_loop", area: "area.visual", kind: "loop", label: "enroll↻" },
    { id: "neuron.asr", area: "area.auditory", kind: "agent", label: "ASR" },
    { id: "neuron.memory", area: "area.mtl", kind: "agent", label: "memory" },
    { id: "neuron.mesh_sync_loop", area: "area.mtl", kind: "loop", label: "mesh↻" },
    { id: "neuron.qa", area: "area.cingulate", kind: "agent", label: "QA" },
    { id: "neuron.qa_cycle", area: "area.cingulate", kind: "loop", label: "QA↻" },
    { id: "neuron.language_in", area: "area.wernicke", kind: "agent", label: "lang-in" },
    { id: "neuron.motor_plan", area: "area.premotor", kind: "loop", label: "plan" },
    { id: "neuron.effector", area: "area.motor", kind: "agent", label: "fire" },
  ];

  // Spinal nodes (periphery) for CNS lens — keyed to Brodmann hubs + Cline/HAAS centers
  const NODES = {
    ...Object.fromEntries(
      Object.entries(AREAS).map(([id, a]) => [
        id,
        { x: a.x, y: Math.min(a.y, 240), r: Math.max(12, a.r * 0.55), label: a.label, kind: "area", repos: a.repos },
      ])
    ),
    // Main-only higher centers (Cline / AGI / enhance / swarm)
    "center.coding": { x: 340, y: 255, r: 15, label: "coding", kind: "center", repos: ["cline"] },
    "center.agi_scan": { x: 280, y: 145, r: 16, label: "AGI scan", kind: "center", repos: ["smart-second-brain", "nullclaw"] },
    "center.enhance": { x: 250, y: 210, r: 14, label: "enhance", kind: "center", repos: ["nullclaw"] },
    "center.capability": { x: 620, y: 200, r: 15, label: "capability", kind: "center", repos: ["nullclaw", "nullboiler"] },
    "center.info": { x: 340, y: 250, r: 14, label: "info", kind: "center", repos: ["smart-second-brain"] },
    "center.slm": { x: 580, y: 175, r: 13, label: "sLM", kind: "center", repos: ["nullclaw"] },
    "center.dl": { x: 270, y: 270, r: 13, label: "DL", kind: "center", repos: ["paddledetection", "nullclaw"] },
    "center.tooling": { x: 600, y: 240, r: 14, label: "tooling", kind: "center", repos: ["jarvis", "nullclaw"] },
    "switch.autonomy": { x: 450, y: 310, r: 12, label: "autonomy", kind: "switch", repos: ["nulltickets"] },
    "switch.outbound": { x: 520, y: 340, r: 11, label: "outbound", kind: "switch", repos: ["openclaw"] },
    "switch.careers_submit": { x: 560, y: 300, r: 11, label: "submit", kind: "switch", repos: ["nulltickets"] },
    "switch.presence": { x: 580, y: 250, r: 11, label: "presence", kind: "switch", repos: ["llmavatartalk"] },
    "switch.research_scan": { x: 380, y: 300, r: 11, label: "scan", kind: "switch", repos: ["nulltickets"] },
    "switch.cam_enhance": { x: 320, y: 330, r: 11, label: "enhance", kind: "switch", repos: ["nullhub"] },
    "switch.slm_local": { x: 600, y: 310, r: 10, label: "sLM on", kind: "switch", repos: ["nullclaw"] },
    "switch.dl_local": { x: 280, y: 340, r: 10, label: "DL on", kind: "switch", repos: ["nullclaw"] },
    "switch.tooling": { x: 540, y: 360, r: 11, label: "tools", kind: "switch", repos: ["jarvis", "nulltickets"] },
    "switch.kill": { x: 450, y: 360, r: 13, label: "KILL", kind: "switch", repos: ["nullhub"] },
    "switch.identity": { x: 400, y: 340, r: 11, label: "identity", kind: "switch", repos: ["nullhub"] },
    "switch.tasking": { x: 380, y: 370, r: 11, label: "tasking", kind: "switch", repos: ["nullclaw"] },
    "switch.ios_capture": { x: 340, y: 400, r: 11, label: "iOS cap", kind: "switch", repos: ["nullclaw"] },
    "sense.chat.aaron": { x: 250, y: 360, r: 14, label: "Aaron chat", kind: "sense", repos: ["nullclaw"] },
    "sense.vault.hit": { x: 220, y: 300, r: 13, label: "vault", kind: "sense", repos: ["smart-second-brain"] },
    "sense.swiftguide.map": { x: 195, y: 250, r: 14, label: "SwiftGuide", kind: "sense", repos: ["swiftguide"] },
    "sense.careers.listing": { x: 210, y: 420, r: 13, label: "jobs", kind: "sense", repos: ["nullclaw"] },
    "sense.calendar.event": { x: 240, y: 480, r: 12, label: "calendar", kind: "sense", repos: ["jarvis"] },
    "sense.audio.transcript": { x: 280, y: 230, r: 13, label: "ASR", kind: "sense", repos: ["llmavatartalk"] },
    "sense.vision.detection": { x: 200, y: 190, r: 13, label: "vision in", kind: "sense", repos: ["paddledetection"] },
    "sense.email.thread": { x: 230, y: 540, r: 12, label: "email", kind: "sense", repos: ["openclaw"] },
    "sense.cline.result": { x: 200, y: 360, r: 12, label: "Cline result", kind: "sense", repos: ["cline"] },
    "sense.clock.daily": { x: 180, y: 260, r: 12, label: "daily clock", kind: "sense", repos: ["nullboiler"] },
    "sense.web.arxiv": { x: 170, y: 320, r: 12, label: "arXiv", kind: "sense", repos: ["smart-second-brain"] },
    "sense.web.agi_feed": { x: 165, y: 380, r: 12, label: "AGI feeds", kind: "sense", repos: ["smart-second-brain"] },
    "sense.slm.inference": { x: 200, y: 160, r: 11, label: "sLM out", kind: "sense", repos: ["nullclaw"] },
    "sense.dl.embedding": { x: 190, y: 120, r: 11, label: "DL out", kind: "sense", repos: ["nullclaw"] },
    "sense.swarm.message": { x: 175, y: 450, r: 11, label: "swarm bus", kind: "sense", repos: ["nulltickets"] },
    "sense.tool.result": { x: 185, y: 500, r: 11, label: "tool result", kind: "sense", repos: ["jarvis"] },
    "motor.text": { x: 680, y: 340, r: 14, label: "text", kind: "motor", repos: ["openclaw", "assistant"] },
    "motor.speak": { x: 670, y: 250, r: 16, label: "speak+face", kind: "motor", repos: ["llmavatartalk"] },
    "motor.jarvis": { x: 710, y: 490, r: 13, label: "Jarvis", kind: "motor", repos: ["jarvis"] },
    "motor.cline": { x: 740, y: 460, r: 14, label: "Cline", kind: "motor", repos: ["cline"] },
    "motor.docs": { x: 660, y: 540, r: 12, label: "docs", kind: "motor", repos: ["nullclaw", "swiftguide"] },
    "motor.jobs": { x: 720, y: 300, r: 14, label: "apply", kind: "motor", repos: ["nullclaw"] },
    "motor.vault": { x: 650, y: 190, r: 13, label: "vault write", kind: "motor", repos: ["smart-second-brain"] },
    "motor.mesh": { x: 620, y: 150, r: 12, label: "mesh", kind: "motor", repos: ["nulltickets"] },
    "motor.calendar": { x: 730, y: 540, r: 12, label: "cal write", kind: "motor", repos: ["jarvis"] },
    "motor.call": { x: 700, y: 390, r: 12, label: "call", kind: "motor", repos: ["openclaw"] },
    "motor.facetime": { x: 690, y: 440, r: 12, label: "FaceTime", kind: "motor", repos: ["assistant"] },
    "motor.web_fetch": { x: 640, y: 280, r: 13, label: "web fetch", kind: "motor", repos: ["nullclaw"] },
    "motor.enhance": { x: 630, y: 220, r: 12, label: "enhance", kind: "motor", repos: ["nullhub", "nullclaw"] },
    "motor.slm": { x: 700, y: 220, r: 12, label: "sLM run", kind: "motor", repos: ["nullclaw"] },
    "motor.dl": { x: 710, y: 170, r: 12, label: "DL run", kind: "motor", repos: ["nullclaw"] },
    "motor.tool": { x: 735, y: 250, r: 12, label: "tool run", kind: "motor", repos: ["jarvis", "nullclaw"] },
    "motor.swarm": { x: 740, y: 330, r: 12, label: "swarm ops", kind: "motor", repos: ["nulltickets"] },
  };

  const HOTSPOTS = {
    "sense.careers.listing": {
      pathway: ["sense.careers.listing", "area.temporal", "area.cingulate", "switch.careers_submit", "motor.jobs"],
      feedback: ["motor.jobs", "area.mtl", "area.dlpfc"],
      columns: ["neuron.careers", "neuron.watch_loop", "neuron.qa"],
      tracts: ["tract.uncinate", "tract.cingulum", "tract.cingulum2"],
      behavior: "watch → rank → apply",
      repos: ["nullclaw", "nulltickets", "smart-second-brain"],
    },
    "sense.audio.transcript": {
      pathway: ["sense.audio.transcript", "area.auditory", "area.dlpfc", "area.broca", "switch.presence", "switch.outbound", "motor.speak"],
      feedback: ["motor.speak", "area.mtl", "area.dlpfc"],
      columns: ["neuron.asr", "neuron.speak_loop", "neuron.comms"],
      tracts: ["tract.arcuate", "tract.cingulum2"],
      behavior: "hear → DLPFC → Broca speak",
      repos: ["llmavatartalk", "nullclaw"],
    },
    "sense.chat.aaron": {
      pathway: ["sense.chat.aaron", "area.wernicke", "area.dlpfc", "area.temporal", "sense.vault.hit", "area.cingulate", "switch.autonomy", "motor.vault"],
      feedback: ["motor.vault", "area.mtl", "area.dlpfc"],
      columns: ["neuron.language_in", "neuron.chief", "neuron.research", "neuron.qa_cycle"],
      tracts: ["tract.arcuate", "tract.cingulum", "tract.cingulum2"],
      behavior: "Aaron → Wernicke → DLPFC → research/QA",
      repos: ["nullclaw", "nullboiler", "smart-second-brain"],
    },
    "sense.calendar.event": {
      pathway: ["sense.calendar.event", "area.parietal", "switch.autonomy", "motor.calendar"],
      feedback: ["motor.calendar", "area.mtl", "area.dlpfc"],
      columns: ["neuron.ops", "neuron.life_ops_loop"],
      tracts: ["tract.slf", "tract.cingulum2"],
      behavior: "parietal life-ops loop",
      repos: ["jarvis", "nullclaw"],
    },
    "sense.vision.detection": {
      pathway: ["sense.vision.detection", "area.visual", "area.dlpfc", "area.mtl", "switch.autonomy", "motor.mesh"],
      feedback: ["motor.mesh", "area.mtl", "area.dlpfc"],
      columns: ["neuron.vision", "neuron.memory"],
      tracts: ["tract.ilf", "tract.ifof", "tract.cingulum2"],
      behavior: "V1+ → semantic mesh",
      repos: ["paddledetection", "nulltickets"],
    },
    "sense.email.thread": {
      pathway: ["sense.email.thread", "area.wernicke", "area.broca", "switch.outbound", "motor.text"],
      feedback: ["motor.text", "area.mtl", "area.dlpfc"],
      columns: ["neuron.language_in", "neuron.comms"],
      tracts: ["tract.arcuate"],
      behavior: "arcuate language loop",
      repos: ["openclaw", "assistant"],
    },
    "sense.vault.hit": {
      pathway: ["sense.vault.hit", "area.mtl", "switch.autonomy", "motor.mesh"],
      feedback: ["motor.mesh", "area.mtl", "area.dlpfc"],
      columns: ["neuron.memory", "neuron.mesh_sync_loop"],
      tracts: ["tract.cingulum2"],
      behavior: "MTL engram recall",
      repos: ["smart-second-brain", "nulltickets"],
    },
    "sense.swiftguide.map": {
      pathway: ["sense.swiftguide.map", "area.apfc", "area.mtl", "area.cingulate", "switch.autonomy", "motor.docs"],
      feedback: ["motor.docs", "area.mtl", "area.dlpfc"],
      columns: ["neuron.cartographer", "neuron.docs", "neuron.qa"],
      tracts: ["tract.ifof", "tract.cingulum", "tract.cingulum2"],
      behavior: "BA10 cartography → stack brief",
      repos: ["swiftguide", "smart-second-brain"],
      mindFocus: ["map.swiftguide", "sg.2026", "sg.2026.stack", "map.centers", "center.cartography"],
    },
    "sense.cline.result": {
      pathway: ["sense.cline.result", "center.coding", "area.mtl", "switch.autonomy", "motor.mesh"],
      feedback: ["motor.mesh", "sense.cline.result", "center.coding", "area.dlpfc"],
      behavior: "Cline result → mesh (all workspaces)",
      repos: ["cline", "nulltickets"],
    },
    "sense.clock.daily": {
      pathway: ["sense.clock.daily", "center.agi_scan", "center.enhance", "area.cingulate", "switch.research_scan", "motor.web_fetch", "motor.vault", "motor.mesh"],
      feedback: ["motor.web_fetch", "area.mtl", "area.dlpfc"],
      behavior: "daily AGI scan → propose Cam enhancements",
      repos: ["nullclaw", "smart-second-brain", "nulltickets"],
    },
    "sense.web.arxiv": {
      pathway: ["sense.web.arxiv", "center.agi_scan", "center.enhance", "area.cingulate", "switch.research_scan", "motor.web_fetch", "motor.vault"],
      feedback: ["motor.vault", "area.mtl", "area.dlpfc"],
      behavior: "arXiv papers → Cam relevance proposals",
      repos: ["smart-second-brain", "nullclaw"],
    },
    "sense.web.agi_feed": {
      pathway: ["sense.web.agi_feed", "center.agi_scan", "center.enhance", "area.cingulate", "switch.research_scan", "motor.web_fetch"],
      feedback: ["motor.web_fetch", "area.mtl", "area.dlpfc"],
      behavior: "AGI feeds → distill",
      repos: ["smart-second-brain", "nullclaw"],
    },
    "sense.swarm.message": {
      pathway: ["sense.swarm.message", "center.tooling", "center.capability", "switch.autonomy", "motor.swarm"],
      feedback: ["motor.swarm", "sense.swarm.message", "area.mtl", "area.dlpfc"],
      behavior: "boss/worker assign → broadcast → resolve",
      repos: ["nulltickets", "nullclaw", "jarvis"],
    },
    "sense.tool.result": {
      pathway: ["sense.tool.result", "center.tooling", "area.cingulate", "area.mtl", "switch.autonomy", "motor.mesh"],
      feedback: ["motor.mesh", "sense.tool.result", "center.tooling"],
      behavior: "tool result → QA → mesh",
      repos: ["jarvis", "nulltickets", "nullclaw"],
    },
  };

  const MIND_TREE = {
    id: "map.cam",
    label: "Cam",
    children: [
      {
        id: "map.sense",
        label: "Sensory",
        children: [
          { id: "sense.chat.aaron", label: "Aaron" },
          { id: "sense.vault.hit", label: "Vault" },
          { id: "sense.swiftguide.map", label: "SwiftGuide" },
          { id: "sense.audio.transcript", label: "ASR" },
        ],
      },
      {
        id: "map.centers",
        label: "Cortex",
        children: [
          { id: "area.dlpfc", label: "DLPFC" },
          { id: "area.apfc", label: "aPFC" },
          { id: "area.mtl", label: "MTL" },
          { id: "area.cingulate", label: "ACC" },
          { id: "center.cartography", label: "Cartography" },
        ],
      },
      {
        id: "map.motor",
        label: "Motor",
        children: [
          { id: "motor.speak", label: "Speak" },
          { id: "motor.vault", label: "Vault" },
          { id: "motor.docs", label: "Docs" },
          { id: "motor.mesh", label: "Mesh" },
        ],
      },
      {
        id: "map.swiftguide",
        label: "SwiftGuide",
        children: [
          {
            id: "sg.classification",
            label: "Classification",
            children: [
              { id: "sg.class.ui", label: "SwiftUI" },
              { id: "sg.class.data", label: "Local-first" },
            ],
          },
          {
            id: "sg.2026",
            label: "2026 report",
            children: [
              { id: "sg.2026.stack", label: "Cam iOS stack" },
              { id: "sg.arch.tca", label: "TCA" },
            ],
          },
        ],
      },
    ],
  };

  const cortexSvg = document.getElementById("cortex");
  const nervousSvg = document.getElementById("nervous");
  const mindSvg = document.getElementById("mindmap");
  const cxTracts = document.getElementById("cx-tracts");
  const cxAreas = document.getElementById("cx-areas");
  const cxNeurons = document.getElementById("cx-neurons");
  const cxActive = document.getElementById("cx-active");
  const cxParticles = document.getElementById("cx-particles");
  const nodesG = document.getElementById("nodes");
  const basePaths = document.getElementById("base-paths");
  const activePaths = document.getElementById("active-paths");
  const bursts = document.getElementById("bursts");
  const particles = document.getElementById("particles");
  const mmLinks = document.getElementById("mm-links");
  const mmNodes = document.getElementById("mm-nodes");
  const mmActive = document.getElementById("mm-active");
  const mmParticles = document.getElementById("mm-particles");
  const logEl = document.getElementById("log");
  const reposEl = document.getElementById("repos");
  const controlsEl = document.getElementById("controls");
  const chipKill = document.getElementById("chip-kill");
  const chipLoop = document.getElementById("chip-loop");
  const chipLens = document.getElementById("chip-lens");

  let busy = false;
  let killed = false;
  let lens = "cortex";
  const mmLayout = {};
  const columnPos = {};

  function el(name, attrs = {}, parent = null) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    if (parent) parent.appendChild(n);
    return n;
  }

  function cssId(id) {
    return id.replace(/\./g, "-");
  }

  function link(a, b, group, cls, layout) {
    const A = layout[a];
    const B = layout[b];
    if (!A || !B) return null;
    const mx = (A.x + B.x) / 2;
    const my = (A.y + B.y) / 2 - 16;
    return el("path", { class: cls, d: `M ${A.x} ${A.y} Q ${mx} ${my} ${B.x} ${B.y}`, "data-from": a, "data-to": b }, group);
  }

  function drawCortex() {
    TRACTS.forEach((t) => {
      const A = AREAS[t.a];
      const B = AREAS[t.b];
      if (!A || !B) return;
      const mx = (A.x + B.x) / 2 + (t.a.includes("visual") ? 20 : 0);
      const my = (A.y + B.y) / 2 - 30;
      el(
        "path",
        {
          id: `tract-${cssId(t.id)}`,
          class: "tract-fiber",
          d: `M ${A.x} ${A.y} Q ${mx} ${my} ${B.x} ${B.y}`,
        },
        cxTracts
      );
    });

    Object.entries(AREAS).forEach(([id, a]) => {
      const g = el("g", { id: `area-${cssId(id)}`, "data-id": id }, cxAreas);
      el("circle", { class: "area-core", cx: a.x, cy: a.y, r: a.r }, g);
      el("text", { class: "label", x: a.x, y: a.y + 4, "text-anchor": "middle" }, g).textContent = a.label;
      el("text", { class: "label label-sm", x: a.x, y: a.y + a.r + 12, "text-anchor": "middle" }, g).textContent = a.ba;
    });

    const byArea = {};
    COLUMNS.forEach((c) => {
      byArea[c.area] = byArea[c.area] || [];
      byArea[c.area].push(c);
    });
    Object.entries(byArea).forEach(([areaId, cols]) => {
      const a = AREAS[areaId];
      if (!a) return;
      cols.forEach((c, i) => {
        const ang = -Math.PI / 2 + (i / cols.length) * Math.PI * 2;
        const rad = a.r + 16;
        const x = a.x + Math.cos(ang) * rad;
        const y = a.y + Math.sin(ang) * rad;
        columnPos[c.id] = { x, y, r: c.kind === "loop" ? 5 : 4.5, label: c.label, kind: c.kind, area: c.area };
        const g = el("g", { id: `col-${cssId(c.id)}`, "data-id": c.id }, cxNeurons);
        el("circle", { class: c.kind === "loop" ? "col-loop" : "col-agent", cx: x, cy: y, r: columnPos[c.id].r }, g);
        el("text", { class: "label label-sm", x: x, y: y + 12, "text-anchor": "middle" }, g).textContent = c.label;
      });
    });
  }

  function drawSpinal() {
    Object.entries(NODES).forEach(([id, n]) => {
      const g = el("g", { id: `node-${cssId(id)}`, "data-id": id }, nodesG);
      el("circle", { class: "node-core", cx: n.x, cy: n.y, r: n.r }, g);
      el("text", { class: n.r < 13 ? "label label-sm" : "label", x: n.x, y: n.y + n.r + 12, "text-anchor": "middle" }, g).textContent = n.label;
    });
    Object.keys(NODES)
      .filter((k) => k.startsWith("sense."))
      .forEach((s) => link(s, "area.dlpfc", basePaths, "path-base", NODES));
    Object.keys(NODES)
      .filter((k) => k.startsWith("motor."))
      .forEach((m) => link("area.motor", m, basePaths, "path-base", NODES));
    link("area.dlpfc", "switch.autonomy", basePaths, "path-base", NODES);
    link("switch.autonomy", "switch.kill", basePaths, "path-base", NODES);
  }

  function layoutMindTree(node, depth, angleStart, angleEnd, cx, cy, radius) {
    const angle = (angleStart + angleEnd) / 2;
    const r = depth === 0 ? 0 : radius;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    mmLayout[node.id] = { x, y, r: depth === 0 ? 28 : depth === 1 ? 16 : depth === 2 ? 12 : 9, label: node.label, depth, parent: null };
    const kids = node.children || [];
    if (!kids.length) return;
    const span = angleEnd - angleStart;
    const pad = kids.length > 1 ? span * 0.04 : 0;
    const usable = span - pad * 2;
    const slice = usable / kids.length;
    kids.forEach((child, i) => {
      const a0 = angleStart + pad + i * slice;
      const a1 = a0 + slice;
      layoutMindTree(child, depth + 1, a0, a1, cx, cy, 95 + depth * 78);
      mmLayout[child.id].parent = node.id;
    });
  }

  function drawMindMap() {
    layoutMindTree(MIND_TREE, 0, -Math.PI * 0.75, Math.PI * 1.25, 450, 330, 0);
    Object.entries(mmLayout).forEach(([id, n]) => {
      if (n.parent && mmLayout[n.parent]) {
        const p = mmLayout[n.parent];
        el("path", { class: "mm-link", d: `M ${p.x} ${p.y} Q ${(p.x + n.x) / 2} ${(p.y + n.y) / 2} ${n.x} ${n.y}` }, mmLinks);
      }
    });
    Object.entries(mmLayout).forEach(([id, n]) => {
      const g = el("g", { id: `mm-${cssId(id)}`, "data-id": id }, mmNodes);
      const cls = n.depth === 0 ? "mm-core" : n.depth === 1 ? "mm-branch" : "mm-leaf";
      el("circle", { class: cls, cx: n.x, cy: n.y, r: n.r }, g);
      el("text", { class: n.depth > 2 ? "label label-sm" : "label", x: n.x, y: n.depth === 0 ? n.y + 5 : n.y + n.r + 12, "text-anchor": "middle" }, g).textContent =
        n.label;
    });
  }

  function clearActive() {
    activePaths.innerHTML = "";
    particles.innerHTML = "";
    bursts.innerHTML = "";
    cxActive.innerHTML = "";
    cxParticles.innerHTML = "";
    mmActive.innerHTML = "";
    mmParticles.innerHTML = "";
    document.querySelectorAll(".area-core, .node-core, .col-agent, .col-loop, .mm-core, .mm-branch, .mm-leaf").forEach((c) => {
      c.classList.remove("lit", "motor-fire", "feedback", "looping");
    });
    document.querySelectorAll(".tract-fiber").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".repo").forEach((r) => r.classList.remove("active"));
  }

  function light(id, cls = "lit") {
    const selectors = [
      `#area-${cssId(id)} .area-core`,
      `#node-${cssId(id)} .node-core`,
      `#col-${cssId(id)} circle`,
      `#mm-${cssId(id)} circle`,
    ];
    selectors.forEach((sel) => {
      const c = document.querySelector(sel);
      if (c) {
        c.classList.remove("lit", "motor-fire", "feedback", "looping");
        c.classList.add(cls);
      }
    });
  }

  function lightTract(id) {
    const t = document.querySelector(`#tract-${cssId(id)}`);
    if (t) t.classList.add("active");
  }

  function activateRepos(list) {
    document.querySelectorAll(".repo").forEach((r) => r.classList.remove("active"));
    (list || []).forEach((id) => {
      const elr = document.querySelector(`[data-repo="${id}"]`);
      if (elr) elr.classList.add("active");
    });
  }

  function log(html) {
    const div = document.createElement("div");
    div.className = "entry";
    div.innerHTML = html;
    logEl.prepend(div);
  }

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }

  function spawnParticle(pathEl, color, host) {
    if (!pathEl) return Promise.resolve();
    const len = pathEl.getTotalLength();
    const glow =
      lens === "cortex" ? "url(#softGlow)" : lens === "mindmap" ? "url(#mapGlow)" : "url(#spineGlow)";
    const dot = el("circle", { r: 3.5, fill: color, filter: glow }, host);
    const start = performance.now();
    return new Promise((resolve) => {
      function frame(t) {
        const p = Math.min(1, (t - start) / 600);
        const pt = pathEl.getPointAtLength(p * len);
        dot.setAttribute("cx", pt.x);
        dot.setAttribute("cy", pt.y);
        if (p < 1) requestAnimationFrame(frame);
        else {
          dot.remove();
          resolve();
        }
      }
      requestAnimationFrame(frame);
    });
  }

  function setLens(next) {
    lens = next;
    cortexSvg.classList.toggle("hidden", lens !== "cortex");
    nervousSvg.classList.toggle("hidden", lens !== "cns");
    mindSvg.classList.toggle("hidden", lens !== "mindmap");
    document.querySelectorAll(".lens-toggle .lens").forEach((b) => {
      const on = b.dataset.lens === lens;
      b.classList.toggle("on", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    chipLens.textContent = `lens: ${lens === "cns" ? "spinal" : lens}`;
    chipLens.classList.add("on");
  }

  function layoutFor(a, b) {
    if (lens === "cortex") {
      if (AREAS[a] && AREAS[b]) return AREAS;
      if (columnPos[a] && columnPos[b]) return columnPos;
      const mixed = { ...AREAS, ...columnPos, ...NODES };
      return mixed;
    }
    if (lens === "mindmap" && mmLayout[a] && mmLayout[b]) return mmLayout;
    return NODES;
  }

  async function runPathway(senseId) {
    if (busy) return;
    busy = true;
    clearActive();
    if (killed) {
      light("switch.kill", "motor-fire");
      chipKill.classList.add("on");
      chipKill.textContent = "KILL ACTIVE";
      log(`<span class="motor">KILL</span> — all motor silenced`);
      busy = false;
      return;
    }
    const hot = HOTSPOTS[senseId];
    if (!hot) {
      busy = false;
      return;
    }
    activateRepos(hot.repos);
    log(`<span class="in">IN</span> ${senseId} · ${hot.behavior}`);
    chipLoop.classList.remove("on");
    chipLoop.textContent = "column loops";

    (hot.tracts || []).forEach(lightTract);
    (hot.columns || []).forEach((c) => {
      light(c, c.includes("loop") || c.includes("cycle") || c.includes("watch") || c.includes("speak") || c.includes("mesh") || c.includes("plan") || c.includes("enroll") || c.includes("gate") || c.includes("burst") ? "looping" : "lit");
    });
    if ((hot.columns || []).some((c) => c.includes("loop") || c.includes("cycle") || c.includes("watch"))) {
      chipLoop.classList.add("on");
      chipLoop.textContent = "loops firing";
      log(`<span class="center">COLUMNS</span> ${(hot.columns || []).join(" · ")}`);
    }
    if (hot.tracts && hot.tracts.length) {
      log(`<span class="center">TRACTS</span> ${hot.tracts.join(" · ")}`);
    }

    if (lens === "mindmap" && hot.mindFocus) {
      const chain = ["map.cam", ...hot.mindFocus];
      for (let i = 0; i < chain.length - 1; i++) {
        light(chain[i], "lit");
        const path = link(chain[i], chain[i + 1], mmActive, "mm-link-active", mmLayout);
        if (path) await spawnParticle(path, "#5fd4c4", mmParticles);
        light(chain[i + 1], "lit");
        await sleep(60);
      }
    }

    for (let i = 0; i < hot.pathway.length - 1; i++) {
      const a = hot.pathway[i];
      const b = hot.pathway[i + 1];
      light(a, a.startsWith("motor.") ? "motor-fire" : "lit");
      const layout = layoutFor(a, b);
      const host = lens === "cortex" ? cxParticles : lens === "mindmap" ? mmParticles : particles;
      const group = lens === "cortex" ? cxActive : lens === "mindmap" ? mmActive : activePaths;
      const cls =
        lens === "mindmap"
          ? "mm-link-active"
          : b.startsWith("motor.")
            ? "path-active path-motor"
            : "path-active";
      const path = link(a, b, group, cls, layout);
      if (path) await spawnParticle(path, b.startsWith("motor.") ? "#e07a5f" : "#5fd4c4", host);
      light(b, b.startsWith("motor.") ? "motor-fire" : "lit");
      if (b.startsWith("area.")) log(`<span class="center">AREA</span> ${b}`);
      if (b.startsWith("switch.")) log(`<span class="center">SWITCH</span> ${b} → act`);
      if (b.startsWith("motor.")) log(`<span class="motor">MOTOR</span> ${b}`);
      await sleep(85);
    }

    chipLoop.classList.add("on");
    chipLoop.textContent = "mesh feedback";
    log(`<span class="back">FEEDBACK</span> Hebbian mesh return via cingulum`);
    for (let i = 0; i < hot.feedback.length - 1; i++) {
      const a = hot.feedback[i];
      const b = hot.feedback[i + 1];
      const layout = layoutFor(a, b);
      const host = lens === "cortex" ? cxParticles : lens === "mindmap" ? mmParticles : particles;
      const group = lens === "cortex" ? cxActive : lens === "mindmap" ? mmActive : activePaths;
      const cls = lens === "mindmap" ? "mm-link-feedback" : "path-feedback";
      const path = link(a, b, group, cls, layout);
      light(a, "feedback");
      if (path) await spawnParticle(path, "#d4a84b", host);
      light(b, "feedback");
      await sleep(75);
    }
    light("neuron.mesh_sync_loop", "looping");
    log(`<span class="back">INTEGRATED</span> DLPFC + MTL updated · tracts strengthened`);
    busy = false;
  }

  function renderRepos() {
    REPOS.forEach((r) => {
      const s = document.createElement("span");
      s.className = "repo" + (r.special ? " swiftguide" : "");
      s.dataset.repo = r.id;
      s.textContent = r.label;
      reposEl.appendChild(s);
    });
  }

  function renderControls() {
    [
      ["sense.chat.aaron", "Aaron task", "gold"],
      ["sense.swiftguide.map", "SwiftGuide map", "gold"],
      ["sense.audio.transcript", "Speak / hear", ""],
      ["sense.careers.listing", "Jobs spike", ""],
      ["sense.calendar.event", "Life ops", ""],
      ["sense.vision.detection", "Vision", ""],
      ["sense.email.thread", "Email", ""],
      ["sense.vault.hit", "Vault recall", ""],
      ["sense.cline.result", "Cline result", ""],
      ["__demo__", "Auto demo", "gold"],
      ["__kill__", "Kill switch", "danger"],
      ["__reset__", "Reset", ""],
    ].forEach(([id, label, cls]) => {
      const b = document.createElement("button");
      b.textContent = label;
      if (cls) b.className = cls;
      b.addEventListener("click", async () => {
        if (id === "__demo__") return demo();
        if (id === "__kill__") {
          killed = !killed;
          chipKill.classList.toggle("on", killed);
          chipKill.textContent = killed ? "KILL ACTIVE" : "kill armed";
          clearActive();
          log(killed ? `<span class="motor">KILL ON</span>` : `<span class="center">KILL OFF</span>`);
          return;
        }
        if (id === "__reset__") {
          killed = false;
          chipKill.classList.remove("on");
          chipKill.textContent = "kill armed";
          chipLoop.classList.remove("on");
          chipLoop.textContent = "column loops";
          clearActive();
          log(`<span class="center">RESET</span>`);
          return;
        }
        await runPathway(id);
      });
      controlsEl.appendChild(b);
    });
  }

  async function demo() {
    for (const s of ["sense.chat.aaron", "sense.swiftguide.map", "sense.audio.transcript", "sense.careers.listing", "sense.vision.detection"]) {
      if (killed) break;
      await runPathway(s);
      await sleep(400);
    }
  }

  document.querySelectorAll(".lens-toggle .lens").forEach((btn) => {
    btn.addEventListener("click", () => setLens(btn.dataset.lens));
  });

  drawCortex();
  drawSpinal();
  drawMindMap();
  renderRepos();
  renderControls();
  setLens("cortex");
  log(`<span class="center">READY</span> Brodmann cortex online · columns=agents/loops · tracts=mesh`);
})();
