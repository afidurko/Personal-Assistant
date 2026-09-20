/* Cam Live companion — chat + voice + vision + teams + inbox.
   Vanilla JS, no build step. Works fully offline against the local server;
   upgrades itself with coco-ssd object detection when a CDN is reachable. */

const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  return res.json();
};

const state = {
  ttsVoice: null,
  lastMsgAt: "",
  seenMsgIds: new Set(),
  camera: null,
  detector: null,        // coco-ssd model when available
  detectorTried: false,
  liveTimer: null,
  speaking: false,
};

/* ---------------- chat ---------------- */

function addChat(who, text, tag) {
  const div = document.createElement("div");
  div.className = `msg ${who}`;
  if (tag) {
    const t = document.createElement("span");
    t.className = "tag";
    t.textContent = tag;
    div.appendChild(t);
  }
  div.appendChild(document.createTextNode(text));
  $("chatlog").appendChild(div);
  $("chatlog").scrollTop = $("chatlog").scrollHeight;
}

function speak(text, cfg) {
  if (!$("ttsbox").checked || !("speechSynthesis" in window)) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = (cfg && cfg.rate) || 0.95;
  u.pitch = (cfg && cfg.pitch) || 1.05;
  u.lang = (cfg && cfg.lang) || "en-US";
  if (!state.ttsVoice) {
    const voices = speechSynthesis.getVoices();
    state.ttsVoice =
      voices.find((v) => /female|samantha|victoria|zira|aria/i.test(v.name)) ||
      voices.find((v) => v.lang.startsWith("en")) || null;
  }
  if (state.ttsVoice) u.voice = state.ttsVoice;
  state.speaking = true;
  u.onend = () => { state.speaking = false; };
  speechSynthesis.speak(u);
}

async function sendChat(text, source = "text") {
  if (!text.trim()) return;
  addChat("aaron", text, source === "text" ? "Aaron" : "Aaron · voice");
  try {
    const turn = await api("/api/chat", { method: "POST", body: { text, source } });
    const engine = turn.engine ? ` · ${turn.engine}` : "";
    addChat("cam", turn.cam || "…", `Cam${engine}`);
    speak(turn.cam, turn.speak);
    refreshAll();
  } catch (e) {
    addChat("cam", `(connection problem: ${e.message})`, "Cam · error");
  }
}

$("chatform").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const text = $("chatinput").value;
  $("chatinput").value = "";
  sendChat(text, "text");
});

/* ---------------- voice input (Web Speech API) ---------------- */

let recog = null;
function setupRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return null;
  const r = new SR();
  r.lang = "en-US";
  r.continuous = true;
  r.interimResults = false;
  r.onresult = (ev) => {
    for (let i = ev.resultIndex; i < ev.results.length; i++) {
      if (ev.results[i].isFinal) {
        const text = ev.results[i][0].transcript.trim();
        if (text && !state.speaking) sendChat(text, "mic");
      }
    }
  };
  r.onend = () => {
    if ($("micbtn").classList.contains("live")) {
      try { r.start(); } catch (_) { /* restart race */ }
    }
  };
  return r;
}

$("micbtn").addEventListener("click", () => {
  if (!recog) recog = setupRecognition();
  if (!recog) {
    addChat("cam", "This browser has no speech recognition — Chrome/Safari have it. You can still type.", "Cam");
    return;
  }
  const live = $("micbtn").classList.toggle("live");
  if (live) {
    try { recog.start(); } catch (_) {}
    $("pill-ears").textContent = "ears: listening";
    $("pill-ears").classList.add("on");
  } else {
    recog.stop();
    $("pill-ears").textContent = "ears: on";
  }
});

/* ---------------- vision ---------------- */

async function tryLoadDetector() {
  if (state.detectorTried) return state.detector;
  state.detectorTried = true;
  const scripts = [
    "https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.17.0/dist/tf.min.js",
    "https://cdn.jsdelivr.net/npm/@tensorflow-models/coco-ssd@2.2.3/dist/coco-ssd.min.js",
  ];
  try {
    for (const src of scripts) {
      await new Promise((ok, bad) => {
        const s = document.createElement("script");
        s.src = src;
        s.onload = ok;
        s.onerror = bad;
        setTimeout(bad, 12000);
        document.head.appendChild(s);
      });
    }
    state.detector = await window.cocoSsd.load();
    $("vision-mode").textContent = "· live detector (coco-ssd, 80 classes)";
  } catch (_) {
    state.detector = null;
    $("vision-mode").textContent = "· local visual cortex (offline mode)";
  }
  return state.detector;
}

$("cambtn").addEventListener("click", async () => {
  if (state.camera) {
    state.camera.getTracks().forEach((t) => t.stop());
    state.camera = null;
    $("video").srcObject = null;
    $("cambtn").textContent = "Start camera";
    $("snapbtn").disabled = true;
    $("pill-eyes").textContent = "eyes: off";
    $("pill-eyes").classList.remove("on");
    stopLive();
    return;
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    state.camera = stream;
    $("video").srcObject = stream;
    await $("video").play();
    $("cambtn").textContent = "Stop camera";
    $("snapbtn").disabled = false;
    $("pill-eyes").textContent = "eyes: open";
    $("pill-eyes").classList.add("on");
    tryLoadDetector();
  } catch (e) {
    $("visionout").textContent = `Camera unavailable: ${e.message}. Use "Analyze image…" instead.`;
  }
});

function drawBoxes(objects, w, h, normalized) {
  const cv = $("overlay");
  cv.width = w; cv.height = h;
  const ctx = cv.getContext("2d");
  ctx.clearRect(0, 0, w, h);
  ctx.font = "13px sans-serif";
  for (const o of objects) {
    if (!o.bbox) continue;
    let [x, y, bw, bh] = o.bbox;
    if (normalized) { x *= w; y *= h; bw *= w; bh *= h; }
    ctx.strokeStyle = "#7aa2ff";
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, bw, bh);
    const label = `${o.label || o.class} ${(o.score * 100) | 0}%`;
    const tw = ctx.measureText(label).width + 8;
    ctx.fillStyle = "rgba(11,14,20,.8)";
    ctx.fillRect(x, Math.max(0, y - 18), tw, 18);
    ctx.fillStyle = "#e8ecf4";
    ctx.fillText(label, x + 4, Math.max(12, y - 5));
  }
}

function showDetections(objects, source) {
  const out = objects.length
    ? objects.map((o) => `<div class="det"><b>${o.label || o.class}</b> — ${(o.score * 100) | 0}%${o.position ? ` · ${o.position}` : ""}</div>`).join("")
    : "<div class='det'>nothing salient detected</div>";
  $("visionout").innerHTML = `<div class="det sub">source: ${source} · ${new Date().toLocaleTimeString()}</div>` + out;
}

async function identifyFrom(el, w, h) {
  // 1) best path: in-browser real object detection
  const det = state.detector || (await tryLoadDetector());
  if (det) {
    const preds = await det.detect(el);
    const objects = preds.map((p) => ({ label: p.class, score: p.score, bbox: p.bbox }));
    drawBoxes(objects, w, h, false);
    showDetections(objects, "coco-ssd (live)");
    await api("/api/vision/detections", { method: "POST", body: { objects, source: "cocossd" } });
    return;
  }
  // 2) offline path: raw pixels → server numpy cortex
  const cw = 160, ch = Math.round((160 * h) / w) || 120;
  const c = document.createElement("canvas");
  c.width = cw; c.height = ch;
  c.getContext("2d").drawImage(el, 0, 0, cw, ch);
  const data = c.getContext("2d").getImageData(0, 0, cw, ch).data;
  let bin = "";
  for (let i = 0; i < data.length; i += 8192) {
    bin += String.fromCharCode.apply(null, data.subarray(i, Math.min(i + 8192, data.length)));
  }
  const res = await api("/api/vision/frame", {
    method: "POST",
    body: { rgba_b64: btoa(bin), width: cw, height: ch },
  });
  if (res.ok) {
    drawBoxes(res.objects, w, h, true);
    showDetections(res.objects, "local visual cortex");
  } else {
    $("visionout").textContent = `analysis failed: ${res.error}`;
  }
}

$("snapbtn").addEventListener("click", () => {
  const v = $("video");
  if (v.videoWidth) identifyFrom(v, v.videoWidth, v.videoHeight);
});

function stopLive() {
  if (state.liveTimer) { clearInterval(state.liveTimer); state.liveTimer = null; }
  $("livebox").checked = false;
}
$("livebox").addEventListener("change", () => {
  if ($("livebox").checked && state.camera) {
    state.liveTimer = setInterval(() => {
      const v = $("video");
      if (v.videoWidth) identifyFrom(v, v.videoWidth, v.videoHeight);
    }, 1500);
  } else stopLive();
});

$("filepick").addEventListener("change", async (ev) => {
  const file = ev.target.files[0];
  if (!file) return;
  const img = new Image();
  img.onload = async () => {
    // paint it on the stage so boxes land on something visible
    const cv = $("overlay");
    const stageW = $("stage").clientWidth || 480;
    const scale = stageW / img.width;
    const w = Math.round(img.width * scale), h = Math.round(img.height * scale);
    $("video").style.display = "none";
    let bg = $("stage").querySelector("img.bg");
    if (!bg) {
      bg = document.createElement("img");
      bg.className = "bg";
      bg.style.width = "100%";
      $("stage").insertBefore(bg, cv);
    }
    bg.src = img.src;
    await identifyFrom(img, w, h);
    URL.revokeObjectURL(img.src);
  };
  img.src = URL.createObjectURL(file);
});

/* ---------------- tasks ---------------- */

$("taskform").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const goal = $("taskinput").value.trim();
  if (!goal) return;
  $("taskinput").value = "";
  await api("/api/tasks", { method: "POST", body: { goal } });
  refreshTasks();
});

function renderTask(t) {
  const subs = (t.subtasks || [])
    .map((s) => `<span class="sa ${s.status}">${s.agent} · ${s.status}${s.elapsed_ms != null ? ` · ${s.elapsed_ms}ms` : ""}</span>`)
    .join("");
  const speed = t.parallel_speedup ? ` · parallel speedup ×${t.parallel_speedup}` : "";
  const result = t.result ? `<div class="result">${escapeHtml(t.result)}</div>` : "";
  return `<div class="task">
    <div class="goal">${escapeHtml(t.goal)}</div>
    <div class="meta">${t.team_name} · lead: ${t.lead} · ${t.status}${speed}</div>
    <div class="subagents">${subs}</div>${result}
  </div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function refreshTasks() {
  try {
    const doc = await api("/api/tasks");
    $("tasklist").innerHTML = (doc.tasks || []).slice().reverse().map(renderTask).join("") ||
      "<div class='sub'>No tasks yet — dispatch one above, or tell Cam “task: …” in chat.</div>";
  } catch (_) {}
}

/* ---------------- inbox ---------------- */

async function refreshInbox() {
  try {
    const doc = await api("/api/messages");
    const msgs = (doc.messages || []).slice().reverse();
    $("inbox").innerHTML = msgs.map((m) => `
      <div class="mail ${m.read ? "" : "unread"}">
        <div class="subj">${escapeHtml(m.subject)} <span class="when">· ${m.at.replace("T", " ").replace("Z", " UTC")}</span></div>
        <div class="body">${escapeHtml(m.body)}</div>
      </div>`).join("") || "<div class='sub'>No messages yet.</div>";
    $("pill-unread").textContent = `✉ ${doc.unread}`;
    $("pill-unread").classList.toggle("warn", doc.unread > 0);
    // browser notifications + spoken alert for new arrivals
    for (const m of msgs) {
      if (!state.seenMsgIds.has(m.id)) {
        state.seenMsgIds.add(m.id);
        if (state.lastMsgAt && m.at > state.lastMsgAt && !m.read) {
          notify(`Cam · ${m.subject}`, m.body);
          if (m.kind === "reminder") speak(m.body, {});
        }
      }
      if (m.at > state.lastMsgAt) state.lastMsgAt = m.at;
    }
  } catch (_) {}
}

function notify(title, body) {
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") {
    new Notification(title, { body });
  } else if (Notification.permission !== "denied") {
    Notification.requestPermission();
  }
}

$("readall").addEventListener("click", async () => {
  await api("/api/messages/read", { method: "POST", body: {} });
  refreshInbox();
});

/* ---------------- status ---------------- */

async function refreshState() {
  try {
    const st = await api("/api/state");
    const b = st.brain || {};
    $("pill-brain").textContent = `brain: ${b.live_llm ? b.backend : "local cortex"}`;
    $("pill-brain").classList.toggle("on", !!b.live_llm);
    if (!$("micbtn").classList.contains("live")) {
      $("pill-ears").textContent = "ears: on";
      $("pill-ears").classList.add("on");
    }
    $("statusline").textContent =
      `online since ${st.started.replace("T", " ").replace("Z", "")} UTC · ` +
      `${b.memory_facts} memories · ${st.reminders_pending} reminders · ` +
      `${st.tasks.running} tasks running`;
  } catch (_) {
    $("statusline").textContent = "server unreachable — is cam-live-server.py running?";
  }
}

function refreshAll() {
  refreshState();
  refreshInbox();
  refreshTasks();
}

refreshAll();
setInterval(refreshAll, 3000);
if ("Notification" in window && Notification.permission === "default") {
  setTimeout(() => Notification.requestPermission(), 4000);
}
