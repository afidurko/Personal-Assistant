/* Cam Connectome live brain + spinal cord visualization */
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
    { id: "openclaw", label: "OpenClaw patterns", region: "motor" },
    { id: "assistant", label: "Assistant-", region: "motor" },
  ];

  // Anatomical layout: brain centers top, spinal sensory left / motor right
  const NODES = {
    // Brain
    "center.chief": { x: 450, y: 130, r: 28, label: "Cam chief", kind: "center", repos: ["nullclaw", "nullhub"] },
    "center.router": { x: 450, y: 200, r: 18, label: "router", kind: "center", repos: ["nullboiler"] },
    "center.memory": { x: 330, y: 120, r: 20, label: "memory", kind: "center", repos: ["smart-second-brain", "nulltickets"] },
    "center.research": { x: 370, y: 185, r: 16, label: "research", kind: "center", repos: ["smart-second-brain"] },
    "center.careers": { x: 530, y: 185, r: 16, label: "careers", kind: "center", repos: ["nullclaw"] },
    "center.comms": { x: 570, y: 125, r: 18, label: "comms", kind: "center", repos: ["llmavatartalk", "openclaw"] },
    "center.ops": { x: 510, y: 235, r: 15, label: "ops", kind: "center", repos: ["jarvis"] },
    "center.docs": { x: 390, y: 235, r: 15, label: "docs", kind: "center", repos: ["nullclaw"] },
    "center.coding": { x: 340, y: 255, r: 15, label: "coding", kind: "center", repos: ["cline"] },
    "center.vision": { x: 300, y: 175, r: 15, label: "vision", kind: "center", repos: ["paddledetection"] },
    "center.qa": { x: 450, y: 255, r: 14, label: "QA", kind: "center", repos: ["nullclaw"] },
    // Switches (mid brain/spine junction)
    "switch.autonomy": { x: 450, y: 310, r: 12, label: "autonomy", kind: "switch", repos: ["nulltickets"] },
    "switch.outbound": { x: 520, y: 340, r: 11, label: "outbound", kind: "switch", repos: ["openclaw", "assistant"] },
    "switch.careers_submit": { x: 560, y: 300, r: 11, label: "submit", kind: "switch", repos: ["nulltickets"] },
    "switch.presence": { x: 580, y: 250, r: 11, label: "presence", kind: "switch", repos: ["llmavatartalk"] },
    "switch.kill": { x: 450, y: 360, r: 13, label: "KILL", kind: "switch", repos: ["nullhub"] },
    // Sensory (left spinal roots)
    "sense.chat.aaron": { x: 250, y: 360, r: 14, label: "Aaron chat", kind: "sense", repos: ["nullclaw"] },
    "sense.vault.hit": { x: 220, y: 300, r: 13, label: "vault", kind: "sense", repos: ["smart-second-brain"] },
    "sense.careers.listing": { x: 210, y: 420, r: 13, label: "LinkedIn/Indeed", kind: "sense", repos: ["nullclaw"] },
    "sense.calendar.event": { x: 240, y: 480, r: 12, label: "calendar", kind: "sense", repos: ["jarvis"] },
    "sense.audio.transcript": { x: 280, y: 240, r: 13, label: "ASR", kind: "sense", repos: ["llmavatartalk"] },
    "sense.vision.detection": { x: 200, y: 200, r: 13, label: "vision in", kind: "sense", repos: ["paddledetection"] },
    "sense.email.thread": { x: 230, y: 540, r: 12, label: "email", kind: "sense", repos: ["openclaw"] },
    "sense.cline.result": { x: 200, y: 360, r: 12, label: "Cline result", kind: "sense", repos: ["cline"] },
    // Motor (right spinal roots)
    "motor.text": { x: 680, y: 340, r: 14, label: "text", kind: "motor", repos: ["openclaw", "assistant"] },
    "motor.call": { x: 700, y: 390, r: 13, label: "call", kind: "motor", repos: ["openclaw"] },
    "motor.facetime": { x: 690, y: 440, r: 13, label: "FaceTime", kind: "motor", repos: ["assistant"] },
    "motor.speak": { x: 670, y: 250, r: 16, label: "speak+face", kind: "motor", repos: ["llmavatartalk"] },
    "motor.jarvis": { x: 710, y: 490, r: 13, label: "Jarvis", kind: "motor", repos: ["jarvis"] },
    "motor.cline": { x: 740, y: 460, r: 14, label: "Cline", kind: "motor", repos: ["cline"] },
    "motor.docs": { x: 660, y: 540, r: 12, label: "docs", kind: "motor", repos: ["nullclaw"] },
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
    "sense.cline.result": {
      pathway: ["sense.cline.result", "center.coding", "center.memory", "switch.autonomy", "motor.mesh"],
      feedback: ["motor.mesh", "sense.cline.result", "center.coding", "center.chief"],
      behavior: "Cline result → mesh (all workspaces)",
      repos: ["cline", "nulltickets"],
    },
  };

  const svg = document.getElementById("nervous");
  const nodesG = document.getElementById("nodes");
  const basePaths = document.getElementById("base-paths");
  const activePaths = document.getElementById("active-paths");
  const bursts = document.getElementById("bursts");
  const particles = document.getElementById("particles");
  const logEl = document.getElementById("log");
  const reposEl = document.getElementById("repos");
  const controlsEl = document.getElementById("controls");
  const chipKill = document.getElementById("chip-kill");
  const chipLoop = document.getElementById("chip-loop");

  let busy = false;
  let killed = false;

  function el(name, attrs = {}, parent = null) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    if (parent) parent.appendChild(n);
    return n;
  }

  function drawNodes() {
    Object.entries(NODES).forEach(([id, n]) => {
      const g = el("g", { id: `node-${cssId(id)}`, "data-id": id }, nodesG);
      el("circle", {
        class: "node-core",
        cx: n.x,
        cy: n.y,
        r: n.r,
      }, g);
      el("text", {
        class: n.r < 13 ? "label label-sm" : "label",
        x: n.x,
        y: n.y + n.r + 14,
        "text-anchor": "middle",
      }, g).textContent = n.label;
    });
  }

  function cssId(id) {
    return id.replace(/\./g, "-");
  }

  function link(a, b, group, cls = "path-base") {
    const A = NODES[a];
    const B = NODES[b];
    if (!A || !B) return null;
    const mx = (A.x + B.x) / 2;
    const my = (A.y + B.y) / 2 - 20;
    return el("path", {
      class: cls,
      d: `M ${A.x} ${A.y} Q ${mx} ${my} ${B.x} ${B.y}`,
      "data-from": a,
      "data-to": b,
    }, group);
  }

  function drawBaseSkeleton() {
    // Ascending sensory roots into spine/brain
    const sensory = Object.keys(NODES).filter((k) => k.startsWith("sense."));
    sensory.forEach((s) => link(s, "center.chief", basePaths));
    // Descending motor roots
    const motors = Object.keys(NODES).filter((k) => k.startsWith("motor."));
    motors.forEach((m) => link("center.router", m, basePaths));
    link("center.chief", "center.router", basePaths);
    link("center.router", "switch.autonomy", basePaths);
    link("switch.autonomy", "switch.kill", basePaths);
  }

  function clearActive() {
    activePaths.innerHTML = "";
    particles.innerHTML = "";
    bursts.innerHTML = "";
    Object.keys(NODES).forEach((id) => {
      const c = document.querySelector(`#node-${cssId(id)} .node-core`);
      if (c) c.className.baseVal = "node-core";
    });
    document.querySelectorAll(".repo").forEach((r) => r.classList.remove("active"));
  }

  function light(id, cls = "lit") {
    const c = document.querySelector(`#node-${cssId(id)} .node-core`);
    if (c) {
      c.classList.remove("lit", "motor-fire", "feedback");
      c.classList.add(cls);
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

  function spawnParticle(pathEl, color) {
    const len = pathEl.getTotalLength();
    const dot = el("circle", { r: 3.5, fill: color, filter: "url(#softGlow)" }, particles);
    const start = performance.now();
    const dur = 650;
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

    // Forward sweep
    for (let i = 0; i < hot.pathway.length - 1; i++) {
      const a = hot.pathway[i];
      const b = hot.pathway[i + 1];
      light(a, a.startsWith("motor.") ? "motor-fire" : "lit");
      const path = link(a, b, activePaths, b.startsWith("motor.") ? "path-active path-motor" : "path-active");
      if (path) await spawnParticle(path, b.startsWith("motor.") ? "#e07a5f" : "#5fd4c4");
      light(b, b.startsWith("motor.") ? "motor-fire" : "lit");
      if (b.startsWith("center.")) log(`<span class="center">CENTER</span> ${b}`);
      if (b.startsWith("switch.")) log(`<span class="center">SWITCH</span> ${b} → act`);
      if (b.startsWith("motor.")) {
        burstAt(b);
        log(`<span class="motor">MOTOR</span> ${b} · live action effect`);
      }
      await sleep(90);
    }

    // Feedback return — information coming back
    chipLoop.classList.add("on");
    chipLoop.textContent = "feedback returning";
    log(`<span class="back">FEEDBACK</span> efference copy / sensory return`);
    for (let i = 0; i < hot.feedback.length - 1; i++) {
      const a = hot.feedback[i];
      const b = hot.feedback[i + 1];
      const path = link(a, b, activePaths, "path-feedback");
      light(a, "feedback");
      if (path) await spawnParticle(path, "#d4a84b");
      light(b, "feedback");
      await sleep(80);
    }
    log(`<span class="back">INTEGRATED</span> Cam chief updated · mesh/vault ready`);
    busy = false;
  }

  function renderRepos() {
    REPOS.forEach((r) => {
      const s = document.createElement("span");
      s.className = "repo";
      s.dataset.repo = r.id;
      s.textContent = r.label;
      reposEl.appendChild(s);
    });
  }

  function renderControls() {
    const buttons = [
      ["sense.chat.aaron", "Aaron task", "gold"],
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
      "sense.chat.aaron",
      "sense.careers.listing",
      "sense.audio.transcript",
      "sense.vision.detection",
      "sense.calendar.event",
    ];
    for (const s of seq) {
      if (killed) break;
      await runPathway(s);
      await sleep(500);
    }
  }

  drawNodes();
  drawBaseSkeleton();
  renderRepos();
  renderControls();
  log(`<span class="center">READY</span> Cam connectome online · all repos mapped`);
})();
