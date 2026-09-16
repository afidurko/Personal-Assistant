/* Cam Connectome — dual lens: CNS anatomy + SwiftGuide mind-map cartography */
(() => {
  const REPOS = [
    { id: "nullclaw", label: "nullclaw", region: "brain" },
    { id: "nulltickets", label: "nulltickets", region: "spine" },
    { id: "nullboiler", label: "nullboiler", region: "brain" },
    { id: "nullhub", label: "nullhub", region: "brain" },
    { id: "jarvis", label: "Jarvis", region: "motor" },
    { id: "paddledetection", label: "PaddleDetection", region: "sense" },
    { id: "llmavatartalk", label: "LLMAvatarTalk", region: "motor" },
    { id: "smart-second-brain", label: "smart-second-brain", region: "brain" },
    { id: "swiftguide", label: "SwiftGuide", region: "brain", special: true },
    { id: "openclaw", label: "OpenClaw patterns", region: "motor" },
    { id: "assistant", label: "Assistant-", region: "motor" },
  ];

  const NODES = {
    "center.chief": { x: 450, y: 125, r: 26, label: "Cam chief", kind: "center", repos: ["nullclaw", "nullhub"] },
    "center.router": { x: 450, y: 195, r: 17, label: "router", kind: "center", repos: ["nullboiler"] },
    "center.memory": { x: 320, y: 115, r: 18, label: "memory", kind: "center", repos: ["smart-second-brain", "nulltickets"] },
    "center.cartography": { x: 360, y: 165, r: 17, label: "cartography", kind: "center", repos: ["swiftguide", "smart-second-brain"] },
    "center.research": { x: 390, y: 220, r: 15, label: "research", kind: "center", repos: ["smart-second-brain", "swiftguide"] },
    "center.careers": { x: 530, y: 180, r: 15, label: "careers", kind: "center", repos: ["nullclaw"] },
    "center.comms": { x: 575, y: 120, r: 17, label: "comms", kind: "center", repos: ["llmavatartalk", "openclaw"] },
    "center.ops": { x: 515, y: 235, r: 14, label: "ops", kind: "center", repos: ["jarvis"] },
    "center.docs": { x: 405, y: 250, r: 14, label: "docs", kind: "center", repos: ["nullclaw", "swiftguide"] },
    "center.vision": { x: 290, y: 185, r: 14, label: "vision", kind: "center", repos: ["paddledetection"] },
    "center.qa": { x: 450, y: 255, r: 13, label: "QA", kind: "center", repos: ["nullclaw"] },
    "switch.autonomy": { x: 450, y: 310, r: 12, label: "autonomy", kind: "switch", repos: ["nulltickets"] },
    "switch.outbound": { x: 520, y: 340, r: 11, label: "outbound", kind: "switch", repos: ["openclaw", "assistant"] },
    "switch.careers_submit": { x: 560, y: 300, r: 11, label: "submit", kind: "switch", repos: ["nulltickets"] },
    "switch.presence": { x: 580, y: 250, r: 11, label: "presence", kind: "switch", repos: ["llmavatartalk"] },
    "switch.kill": { x: 450, y: 360, r: 13, label: "KILL", kind: "switch", repos: ["nullhub"] },
    "sense.chat.aaron": { x: 250, y: 360, r: 14, label: "Aaron chat", kind: "sense", repos: ["nullclaw"] },
    "sense.vault.hit": { x: 220, y: 300, r: 13, label: "vault", kind: "sense", repos: ["smart-second-brain"] },
    "sense.swiftguide.map": { x: 195, y: 250, r: 14, label: "SwiftGuide", kind: "sense", repos: ["swiftguide"] },
    "sense.careers.listing": { x: 210, y: 420, r: 13, label: "LinkedIn/Indeed", kind: "sense", repos: ["nullclaw"] },
    "sense.calendar.event": { x: 240, y: 480, r: 12, label: "calendar", kind: "sense", repos: ["jarvis"] },
    "sense.audio.transcript": { x: 280, y: 230, r: 13, label: "ASR", kind: "sense", repos: ["llmavatartalk"] },
    "sense.vision.detection": { x: 200, y: 190, r: 13, label: "vision in", kind: "sense", repos: ["paddledetection"] },
    "sense.email.thread": { x: 230, y: 540, r: 12, label: "email", kind: "sense", repos: ["openclaw"] },
    "motor.text": { x: 680, y: 340, r: 14, label: "text", kind: "motor", repos: ["openclaw", "assistant"] },
    "motor.call": { x: 700, y: 390, r: 13, label: "call", kind: "motor", repos: ["openclaw"] },
    "motor.facetime": { x: 690, y: 440, r: 13, label: "FaceTime", kind: "motor", repos: ["assistant"] },
    "motor.speak": { x: 670, y: 250, r: 16, label: "speak+face", kind: "motor", repos: ["llmavatartalk"] },
    "motor.jarvis": { x: 710, y: 490, r: 13, label: "Jarvis", kind: "motor", repos: ["jarvis"] },
    "motor.docs": { x: 660, y: 540, r: 12, label: "docs", kind: "motor", repos: ["nullclaw", "swiftguide"] },
    "motor.jobs": { x: 720, y: 300, r: 14, label: "apply", kind: "motor", repos: ["nullclaw"] },
    "motor.vault": { x: 650, y: 190, r: 13, label: "vault write", kind: "motor", repos: ["smart-second-brain"] },
    "motor.mesh": { x: 620, y: 150, r: 12, label: "mesh", kind: "motor", repos: ["nulltickets"] },
    "motor.calendar": { x: 730, y: 540, r: 12, label: "cal write", kind: "motor", repos: ["jarvis"] },
  };

  const HOTSPOTS = {
    "sense.careers.listing": {
      pathway: ["sense.careers.listing", "center.careers", "center.qa", "switch.careers_submit", "motor.jobs", "motor.vault", "motor.mesh"],
      feedback: ["motor.jobs", "sense.careers.listing", "center.memory", "center.chief"],
      behavior: "watch → rank → apply/write",
      repos: ["nullclaw", "nulltickets", "smart-second-brain"],
    },
    "sense.audio.transcript": {
      pathway: ["sense.audio.transcript", "center.chief", "center.comms", "switch.presence", "switch.outbound", "motor.speak"],
      feedback: ["motor.speak", "sense.audio.transcript", "center.chief"],
      behavior: "hear → think → speak (Cam face/voice)",
      repos: ["llmavatartalk", "nullclaw", "openclaw"],
    },
    "sense.chat.aaron": {
      pathway: ["sense.chat.aaron", "center.chief", "center.router", "center.research", "sense.vault.hit", "center.qa", "motor.vault", "motor.mesh"],
      feedback: ["motor.vault", "sense.vault.hit", "center.memory", "center.chief"],
      behavior: "Aaron task → research → vault/mesh",
      repos: ["nullclaw", "nullboiler", "smart-second-brain", "nulltickets"],
    },
    "sense.calendar.event": {
      pathway: ["sense.calendar.event", "center.ops", "switch.autonomy", "motor.jarvis", "motor.calendar", "motor.vault"],
      feedback: ["motor.jarvis", "sense.calendar.event", "center.ops", "center.chief"],
      behavior: "schedule → Jarvis/calendar motor",
      repos: ["jarvis", "nullclaw", "smart-second-brain"],
    },
    "sense.vision.detection": {
      pathway: ["sense.vision.detection", "center.vision", "center.chief", "motor.mesh", "motor.vault"],
      feedback: ["motor.mesh", "sense.vision.detection", "center.vision"],
      behavior: "see → distill → remember",
      repos: ["paddledetection", "nulltickets", "smart-second-brain"],
    },
    "sense.email.thread": {
      pathway: ["sense.email.thread", "center.comms", "switch.outbound", "motor.text", "motor.vault"],
      feedback: ["motor.text", "sense.email.thread", "center.comms", "center.chief"],
      behavior: "inbox → draft/send → log",
      repos: ["openclaw", "assistant", "nullclaw"],
    },
    "sense.vault.hit": {
      pathway: ["sense.vault.hit", "center.memory", "center.chief", "motor.mesh"],
      feedback: ["motor.mesh", "sense.vault.hit", "center.memory"],
      behavior: "vault recall → mesh",
      repos: ["smart-second-brain", "nulltickets"],
    },
    "sense.swiftguide.map": {
      pathway: ["sense.swiftguide.map", "center.cartography", "center.docs", "center.qa", "switch.autonomy", "motor.docs", "motor.vault"],
      feedback: ["motor.docs", "center.memory", "center.cartography", "center.chief"],
      behavior: "mind-map hit → iOS/stack brief → vault",
      repos: ["swiftguide", "smart-second-brain", "nullclaw"],
      mindFocus: ["map.swiftguide", "sg.2026", "sg.2026.stack", "map.centers", "center.cartography"],
    },
  };

  // SwiftGuide-inspired radial mind tree (dual lens)
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
          { id: "sense.ios.camera", label: "iPhone cam" },
        ],
      },
      {
        id: "map.centers",
        label: "Centers",
        children: [
          { id: "center.chief", label: "Chief" },
          { id: "center.cartography", label: "Cartography" },
          { id: "center.memory", label: "Memory" },
          { id: "center.research", label: "Research" },
          { id: "center.docs", label: "Docs" },
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
          { id: "motor.jarvis", label: "Jarvis" },
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
              { id: "sg.class.foundation", label: "Frameworks" },
              { id: "sg.class.ui", label: "SwiftUI" },
              { id: "sg.class.data", label: "Local-first" },
            ],
          },
          {
            id: "sg.architecture",
            label: "Architecture",
            children: [
              { id: "sg.arch.tca", label: "TCA" },
              { id: "sg.arch.md", label: "Markdown" },
            ],
          },
          {
            id: "sg.2026",
            label: "2026 report",
            children: [
              { id: "sg.2026.stack", label: "Cam iOS stack" },
              { id: "sg.2026.proj", label: "100 projects" },
            ],
          },
        ],
      },
    ],
  };

  const nervousSvg = document.getElementById("nervous");
  const mindSvg = document.getElementById("mindmap");
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
  let lens = "cns";
  const mmLayout = {};

  function el(name, attrs = {}, parent = null) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    if (parent) parent.appendChild(n);
    return n;
  }

  function cssId(id) {
    return id.replace(/\./g, "-");
  }

  function drawNodes() {
    Object.entries(NODES).forEach(([id, n]) => {
      const g = el("g", { id: `node-${cssId(id)}`, "data-id": id }, nodesG);
      el("circle", { class: "node-core", cx: n.x, cy: n.y, r: n.r }, g);
      el(
        "text",
        {
          class: n.r < 13 ? "label label-sm" : "label",
          x: n.x,
          y: n.y + n.r + 14,
          "text-anchor": "middle",
        },
        g
      ).textContent = n.label;
    });
  }

  function link(a, b, group, cls = "path-base", layout = NODES) {
    const A = layout[a];
    const B = layout[b];
    if (!A || !B) return null;
    const mx = (A.x + B.x) / 2;
    const my = (A.y + B.y) / 2 - 18;
    return el(
      "path",
      {
        class: cls,
        d: `M ${A.x} ${A.y} Q ${mx} ${my} ${B.x} ${B.y}`,
        "data-from": a,
        "data-to": b,
      },
      group
    );
  }

  function drawBaseSkeleton() {
    Object.keys(NODES)
      .filter((k) => k.startsWith("sense."))
      .forEach((s) => link(s, "center.chief", basePaths));
    Object.keys(NODES)
      .filter((k) => k.startsWith("motor."))
      .forEach((m) => link("center.router", m, basePaths));
    link("center.chief", "center.router", basePaths);
    link("center.router", "switch.autonomy", basePaths);
    link("switch.autonomy", "switch.kill", basePaths);
    link("sense.swiftguide.map", "center.cartography", basePaths);
    link("center.cartography", "center.chief", basePaths);
  }

  function layoutMindTree(node, depth, angleStart, angleEnd, cx, cy, radius) {
    const angle = (angleStart + angleEnd) / 2;
    const r = depth === 0 ? 0 : radius;
    const x = cx + Math.cos(angle) * r;
    const y = cy + Math.sin(angle) * r;
    mmLayout[node.id] = {
      x,
      y,
      r: depth === 0 ? 28 : depth === 1 ? 16 : depth === 2 ? 12 : 9,
      label: node.label,
      depth,
      parent: null,
    };
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
    mmLinks.innerHTML = "";
    mmNodes.innerHTML = "";
    Object.keys(mmLayout).forEach((k) => delete mmLayout[k]);
    layoutMindTree(MIND_TREE, 0, -Math.PI * 0.75, Math.PI * 1.25, 450, 330, 0);

    Object.entries(mmLayout).forEach(([id, n]) => {
      if (n.parent && mmLayout[n.parent]) {
        const p = mmLayout[n.parent];
        el(
          "path",
          {
            class: "mm-link",
            d: `M ${p.x} ${p.y} Q ${(p.x + n.x) / 2} ${(p.y + n.y) / 2} ${n.x} ${n.y}`,
            "data-from": n.parent,
            "data-to": id,
          },
          mmLinks
        );
      }
    });

    Object.entries(mmLayout).forEach(([id, n]) => {
      const g = el("g", { id: `mm-${cssId(id)}`, "data-id": id }, mmNodes);
      const cls = n.depth === 0 ? "mm-core" : n.depth === 1 ? "mm-branch" : "mm-leaf";
      el("circle", { class: cls, cx: n.x, cy: n.y, r: n.r }, g);
      const labelY = n.depth === 0 ? n.y + 5 : n.y + n.r + 12;
      el(
        "text",
        {
          class: n.depth > 2 ? "label label-sm" : "label",
          x: n.x,
          y: labelY,
          "text-anchor": "middle",
        },
        g
      ).textContent = n.label;
    });
  }

  function clearActive() {
    activePaths.innerHTML = "";
    particles.innerHTML = "";
    bursts.innerHTML = "";
    mmActive.innerHTML = "";
    mmParticles.innerHTML = "";
    Object.keys(NODES).forEach((id) => {
      const c = document.querySelector(`#node-${cssId(id)} .node-core`);
      if (c) c.className.baseVal = "node-core";
    });
    Object.keys(mmLayout).forEach((id) => {
      const c = document.querySelector(`#mm-${cssId(id)} circle`);
      if (!c) return;
      const depth = mmLayout[id].depth;
      c.className.baseVal = depth === 0 ? "mm-core" : depth === 1 ? "mm-branch" : "mm-leaf";
    });
    document.querySelectorAll(".repo").forEach((r) => r.classList.remove("active"));
  }

  function light(id, cls = "lit") {
    const c = document.querySelector(`#node-${cssId(id)} .node-core`);
    if (c) {
      c.classList.remove("lit", "motor-fire", "feedback");
      c.classList.add(cls);
    }
    const mm = document.querySelector(`#mm-${cssId(id)} circle`);
    if (mm) {
      mm.classList.remove("lit", "motor-fire", "feedback");
      mm.classList.add(cls);
    }
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
    const len = pathEl.getTotalLength();
    const dot = el("circle", { r: 3.5, fill: color, filter: "url(#softGlow)" }, host);
    const start = performance.now();
    const dur = 620;
    return new Promise((resolve) => {
      function frame(t) {
        const p = Math.min(1, (t - start) / dur);
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

  function burstAt(id) {
    const n = NODES[id];
    if (!n) return;
    const c = el("circle", { class: "burst go", cx: n.x, cy: n.y, r: 6 }, bursts);
    setTimeout(() => c.remove(), 750);
  }

  function setLens(next) {
    lens = next;
    nervousSvg.classList.toggle("hidden", lens !== "cns");
    mindSvg.classList.toggle("hidden", lens !== "mindmap");
    document.querySelectorAll(".lens-toggle .lens").forEach((b) => {
      const on = b.dataset.lens === lens;
      b.classList.toggle("on", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
    chipLens.textContent = lens === "cns" ? "lens: CNS" : "lens: mind map";
    chipLens.classList.add("on");
  }

  async function runMindFocus(ids) {
    const chain = ["map.cam", ...(ids || [])];
    for (let i = 0; i < chain.length - 1; i++) {
      const a = chain[i];
      const b = chain[i + 1];
      light(a, "lit");
      light(b, "lit");
      const path = link(a, b, mmActive, "mm-link-active", mmLayout);
      if (path) await spawnParticle(path, "#5fd4c4", mmParticles);
      await sleep(70);
    }
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

    if (lens === "mindmap" && hot.mindFocus) {
      await runMindFocus(hot.mindFocus);
    }

    for (let i = 0; i < hot.pathway.length - 1; i++) {
      const a = hot.pathway[i];
      const b = hot.pathway[i + 1];
      light(a, a.startsWith("motor.") ? "motor-fire" : "lit");
      const pathGroup = lens === "mindmap" ? mmActive : activePaths;
      const host = lens === "mindmap" ? mmParticles : particles;
      const layout = lens === "mindmap" && mmLayout[a] && mmLayout[b] ? mmLayout : NODES;
      const cls =
        lens === "mindmap"
          ? b.startsWith("motor.")
            ? "mm-link-active"
            : "mm-link-active"
          : b.startsWith("motor.")
            ? "path-active path-motor"
            : "path-active";
      const path = link(a, b, pathGroup, cls, layout);
      if (path) await spawnParticle(path, b.startsWith("motor.") ? "#e07a5f" : "#5fd4c4", host);
      light(b, b.startsWith("motor.") ? "motor-fire" : "lit");
      if (b.startsWith("center.")) log(`<span class="center">CENTER</span> ${b}`);
      if (b.startsWith("switch.")) log(`<span class="center">SWITCH</span> ${b} → act`);
      if (b.startsWith("motor.")) {
        if (lens === "cns") burstAt(b);
        log(`<span class="motor">MOTOR</span> ${b} · live action effect`);
      }
      await sleep(90);
    }

    chipLoop.classList.add("on");
    chipLoop.textContent = "feedback returning";
    log(`<span class="back">FEEDBACK</span> efference copy / sensory return`);
    for (let i = 0; i < hot.feedback.length - 1; i++) {
      const a = hot.feedback[i];
      const b = hot.feedback[i + 1];
      const pathGroup = lens === "mindmap" ? mmActive : activePaths;
      const host = lens === "mindmap" ? mmParticles : particles;
      const layout = lens === "mindmap" && mmLayout[a] && mmLayout[b] ? mmLayout : NODES;
      const cls = lens === "mindmap" ? "mm-link-feedback" : "path-feedback";
      const path = link(a, b, pathGroup, cls, layout);
      light(a, "feedback");
      if (path) await spawnParticle(path, "#d4a84b", host);
      light(b, "feedback");
      await sleep(80);
    }
    log(`<span class="back">INTEGRATED</span> Cam chief updated · mesh/vault ready`);
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
    const buttons = [
      ["sense.chat.aaron", "Aaron task", "gold"],
      ["sense.swiftguide.map", "SwiftGuide map", "gold"],
      ["sense.audio.transcript", "Speak / hear", ""],
      ["sense.careers.listing", "Jobs spike", ""],
      ["sense.calendar.event", "Life ops", ""],
      ["sense.vision.detection", "Vision", ""],
      ["sense.email.thread", "Email", ""],
      ["sense.vault.hit", "Vault recall", ""],
      ["__demo__", "Auto demo", "gold"],
      ["__kill__", "Kill switch", "danger"],
      ["__reset__", "Reset", ""],
    ];
    buttons.forEach(([id, label, cls]) => {
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
          if (killed) {
            light("switch.kill", "motor-fire");
            log(`<span class="motor">KILL ON</span> — Aaron master switch`);
          } else {
            log(`<span class="center">KILL OFF</span> — pathways armed`);
          }
          return;
        }
        if (id === "__reset__") {
          killed = false;
          chipKill.classList.remove("on");
          chipKill.textContent = "kill armed";
          chipLoop.classList.remove("on");
          chipLoop.textContent = "feedback loop";
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
    const seq = [
      "sense.swiftguide.map",
      "sense.chat.aaron",
      "sense.careers.listing",
      "sense.audio.transcript",
      "sense.vault.hit",
    ];
    for (const s of seq) {
      if (killed) break;
      await runPathway(s);
      await sleep(450);
    }
  }

  document.querySelectorAll(".lens-toggle .lens").forEach((btn) => {
    btn.addEventListener("click", () => setLens(btn.dataset.lens));
  });

  drawNodes();
  drawBaseSkeleton();
  drawMindMap();
  renderRepos();
  renderControls();
  setLens("cns");
  log(`<span class="center">READY</span> dual-lens connectome · SwiftGuide cartography online`);
})();
