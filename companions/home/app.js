/* Cam Home Live — mission control client (no dependencies). */

const $ = (id) => document.getElementById(id);

function li(cls, text, sub) {
  const el = document.createElement("li");
  const dot = document.createElement("span");
  dot.className = `dot ${cls}`;
  el.appendChild(dot);
  const body = document.createElement("span");
  body.textContent = text;
  el.appendChild(body);
  if (sub) {
    const s = document.createElement("span");
    s.className = "sub";
    s.textContent = sub;
    el.appendChild(s);
  }
  return el;
}

function fill(listEl, items) {
  listEl.replaceChildren(...items);
}

function renderSystem(status) {
  const sys = status.system?.data || {};
  const pieces = sys.pieces || [];
  $("systemMeta").textContent = sys.ok
    ? `${pieces.length} pieces on the bus · overall ${sys.overall}`
    : "system report unavailable";
  fill(
    $("systemList"),
    pieces.map((p) =>
      li(
        p.status === "healthy" ? "ok" : p.status === "warning" ? "warn" : "bad",
        `${p.title || p.id}`,
        `${p.layer} · ${p.status}`
      )
    )
  );
}

function renderPlan(status) {
  const plan = status.build_plan?.data || {};
  $("planMeta").textContent = plan.ok
    ? `plan OK · priorities ${((plan.priority_order || []).length)} · phases ${plan.phase_count}`
    : "plan check failed";
  const rows = [];
  (plan.priority_order || []).forEach((p, i) => rows.push(li("info", `P${i + 1} ${p}`)));
  (plan.warnings || []).forEach((w) => rows.push(li("warn", w)));
  (plan.failures || []).forEach((f) => rows.push(li("bad", f)));
  fill($("planList"), rows);
}

function renderSync(status) {
  const sync = status.auto_sync?.data || {};
  const home = sync.home || {};
  const drift = home.fetched
    ? `ahead ${home.ahead} / behind ${home.behind} of origin/main`
    : "offline — no fetch";
  $("syncMeta").textContent = `branch ${home.branch || "?"} · ${drift}`;
  const rows = [];
  (sync.submodules || [])
    .filter((s) => s.state !== "in_sync")
    .forEach((s) => rows.push(li("warn", s.path, s.state)));
  const reg = sync.registry || {};
  rows.push(
    li(
      "info",
      `${reg.integrations_registered ?? "?"} integrations · ${reg.coding_workspaces ?? "?"} coding workspaces`
    )
  );
  (reg.missing_paths || []).forEach((m) => rows.push(li("bad", `missing ${m}`)));
  fill($("syncList"), rows);
}

function renderAttention(status) {
  const na = status.needs_attention?.data || {};
  const items = na.attention_items || [];
  $("attentionMeta").textContent = items.length
    ? `${items.length} items · ${na.connected ?? "?"} connected / ${na.disconnected ?? "?"} disconnected workspaces`
    : "nothing needs help right now";
  fill(
    $("attentionList"),
    items
      .slice(0, 12)
      .map((it) =>
        li(
          (it.severity || "").match(/high|critical/i) ? "bad" : "warn",
          it.title || it.detail || it.id,
          `${it.severity || ""}${it.auto_clearable ? " · auto-clearable" : ""}`
        )
      )
  );
}

function renderAvatar(status) {
  const av = status.avatar?.data || {};
  $("avatarMeta").textContent = av.ok
    ? `contract OK · tiers: ${(av.tier_ids || []).join(" → ")}`
    : "avatar contract failing";
  const rows = [];
  (av.models_cached || []).forEach((m) => rows.push(li("ok", m)));
  (av.warnings || []).forEach((w) => rows.push(li("warn", w)));
  (av.failures || []).forEach((f) => rows.push(li("bad", f)));
  fill($("avatarList"), rows);
}

function renderEvents(status) {
  const events = status.recent_events || [];
  $("eventsMeta").textContent = events.length
    ? `last ${events.length} bus events`
    : "no recorded events yet";
  fill(
    $("eventsList"),
    events
      .slice(-14)
      .reverse()
      .map((e) =>
        li(
          "info",
          e.title || e.kind || e.event || JSON.stringify(e).slice(0, 90),
          e.at || e.ts || ""
        )
      )
  );
}

async function loadStatus() {
  $("footNote").textContent = "loading status…";
  try {
    const r = await fetch("/api/home/status");
    const status = await r.json();
    renderSystem(status);
    renderPlan(status);
    renderSync(status);
    renderAttention(status);
    renderAvatar(status);
    renderEvents(status);
    $("footNote").textContent = `status as of ${status.at} · Cam home live · Aaron has ultimate say`;
  } catch (e) {
    $("footNote").textContent = `status error: ${e}`;
  }
}

async function loadSuggestions() {
  try {
    const r = await fetch("/api/home/suggestions");
    const { suggestions } = await r.json();
    fill(
      $("suggestList"),
      (suggestions || [])
        .slice(-10)
        .reverse()
        .map((s) => li(s.status === "queued" ? "info" : "ok", s.text, `${s.at} · ${s.status}`))
    );
  } catch {
    /* panel stays empty */
  }
}

$("suggestForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = $("suggestText").value.trim();
  if (!text) return;
  $("suggestNote").textContent = "queuing…";
  const r = await fetch("/api/home/suggest", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text, author: "Aaron" }),
  });
  const out = await r.json();
  $("suggestNote").textContent = out.ok ? `queued as ${out.suggestion.id}` : out.error;
  if (out.ok) {
    $("suggestText").value = "";
    loadSuggestions();
  }
});

$("refreshBtn").addEventListener("click", async () => {
  await fetch("/api/home/refresh", { method: "POST" });
  $("footNote").textContent = "refreshing in background — reload shortly";
  setTimeout(loadStatus, 8000);
});

/* ---- Cortex: live thinking (SSE with polling fallback) ---- */

const RING_C = 226.2;

function thoughtRow(th) {
  const el = document.createElement("li");
  el.className = `st-${th.stage}`;
  const chip = document.createElement("span");
  chip.className = `stagechip ${th.stage}`;
  chip.textContent = th.stage;
  el.appendChild(chip);
  const body = document.createElement("span");
  body.textContent = th.text;
  el.appendChild(body);
  const t = document.createElement("span");
  t.className = "t";
  t.textContent = (th.at || "").slice(11, 19);
  el.appendChild(t);
  return el;
}

const STAGE_REGION = {
  observe: "visual + Wernicke intake",
  analyze: "temporal + ACC comparison",
  reflect: "MTL memory loop",
  predict: "DLPFC + aPFC planning",
  act: "premotor + M1 output",
  speech: "Broca + auditory speech loop",
  input: "Wernicke + MTL (Aaron's words arriving)",
};

function pushThought(th) {
  const feed = $("thoughtFeed");
  feed.appendChild(thoughtRow(th));
  while (feed.children.length > 60) feed.removeChild(feed.firstChild);
  feed.scrollTop = feed.scrollHeight;
  const region = STAGE_REGION[th.stage];
  if (region) {
    const cap = $("vizCaption");
    cap.textContent = `firing now → ${region}`;
    cap.className = `meta st-${th.stage}`;
  }
}

const counters = {};
function countUp(el, target, suffix = "") {
  const from = counters[el.id] ?? target;
  counters[el.id] = target;
  if (from === target) {
    el.textContent = `${target}${suffix}`;
    return;
  }
  const t0 = performance.now();
  const dur = 700;
  function step(now) {
    const k = Math.min(1, (now - t0) / dur);
    const eased = 1 - Math.pow(1 - k, 3);
    el.textContent = `${Math.round(from + (target - from) * eased)}${suffix}`;
    if (k < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function renderSparkline(history) {
  const svg = $("sparkline");
  svg.replaceChildren();
  if (!history || history.length < 2) return;
  const min = Math.min(...history) - 3;
  const max = Math.max(...history) + 3;
  const coords = history.map((h, i) => [
    (i / (history.length - 1)) * 118 + 1,
    38 - ((h - min) / Math.max(1, max - min)) * 34,
  ]);
  const pts = coords.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`);
  const area = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
  area.setAttribute("class", "area");
  area.setAttribute("points", `1,39 ${pts.join(" ")} 119,39`);
  svg.appendChild(area);
  const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  line.setAttribute("points", pts.join(" "));
  svg.appendChild(line);
  const [lx, ly] = coords[coords.length - 1];
  const dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  dot.setAttribute("class", "spark-dot");
  dot.setAttribute("cx", lx.toFixed(1));
  dot.setAttribute("cy", ly.toFixed(1));
  dot.setAttribute("r", "2.4");
  svg.appendChild(dot);
}

function renderBrain(state) {
  const m = state.metrics || {};
  $("brainMeta").textContent =
    `cycle ${state.tick} · ${state.at} · derived from live checks — nothing invented`;
  if (m.health != null) {
    countUp($("healthNum"), m.health);
    const ring = $("healthRing");
    const color = m.health >= 75 ? "#7dbe98" : m.health >= 50 ? "#d4a017" : "#d47a6a";
    ring.style.strokeDashoffset = (RING_C * (1 - m.health / 100)).toFixed(1);
    ring.style.stroke = color;
    ring.style.filter = `drop-shadow(0 0 5px ${color})`;
    $("pillHealth").innerHTML = `brain <strong>${m.health}</strong> · ${m.trend}`;
    $("brainPill").className =
      `brainpill ${m.health >= 75 ? "ok" : m.health >= 50 ? "warn" : "bad"}`;
    const panel = $("panelBrain");
    panel.classList.remove("ticked");
    void panel.offsetWidth; // restart the tick glow
    panel.classList.add("ticked");
  }
  $("trendWord").textContent = m.trend || "—";
  renderSparkline(m.history);
  if (m.prediction_accuracy != null) countUp($("calibNum"), m.prediction_accuracy, "%");
  else $("calibNum").textContent = "—";
  $("calibSub").textContent = m.predictions_scored
    ? `${m.predictions_scored} scored so far`
    : "no samples yet";

  const focus = state.focus || {};
  $("focusPriority").textContent = focus.priority || "—";
  $("focusDetail").textContent = focus.detail || "";

  fill(
    $("predList"),
    (state.predictions || []).slice(0, 5).map((p) => {
      const el = document.createElement("li");
      const txt = document.createElement("span");
      txt.textContent = p.statement;
      el.appendChild(txt);
      const bar = document.createElement("div");
      bar.className = "pbar";
      const fillEl = document.createElement("span");
      fillEl.style.width = `${Math.round(p.probability * 100)}%`;
      bar.appendChild(fillEl);
      el.appendChild(bar);
      const meta = document.createElement("div");
      meta.className = "pmeta";
      meta.innerHTML = `<span>p=${p.probability} · ${p.horizon}</span><span>${p.evidence}</span>`;
      el.appendChild(meta);
      return el;
    })
  );

  fill(
    $("actionList"),
    (state.actions || []).slice(0, 5).map((a) => {
      const el = document.createElement("li");
      const t = document.createElement("span");
      t.textContent = `${a.title} — `;
      el.appendChild(t);
      const g = document.createElement("span");
      g.className = "gate";
      g.textContent = a.gate;
      el.appendChild(g);
      const c = document.createElement("span");
      c.className = "cmd";
      c.textContent = a.command;
      el.appendChild(c);
      return el;
    })
  );
}

let brainSeq = 0;

function connectBrain() {
  try {
    const es = new EventSource("/api/brain/stream");
    es.addEventListener("state", (ev) => {
      const state = JSON.parse(ev.data);
      renderBrain(state);
      (state.thoughts || []).forEach((th) => {
        if (th.seq > brainSeq) {
          pushThought(th);
          brainSeq = th.seq;
        }
      });
    });
    es.addEventListener("thought", (ev) => {
      const th = JSON.parse(ev.data);
      if (th.seq > brainSeq) {
        pushThought(th);
        brainSeq = th.seq;
      }
    });
    es.onerror = () => {
      es.close();
      setTimeout(pollBrain, 4000);
    };
  } catch {
    pollBrain();
  }
}

async function pollBrain() {
  try {
    const r = await fetch("/api/brain/state");
    const state = await r.json();
    renderBrain(state);
    (state.thoughts || []).forEach((th) => {
      if (th.seq > brainSeq) {
        pushThought(th);
        brainSeq = th.seq;
      }
    });
  } catch {
    /* retry on next interval */
  }
  setTimeout(pollBrain, 15000);
}

/* ---- quick access: dock + keyboard shortcuts ---- */

function focusSpeak() {
  $("speakText").focus();
  $("speakText").scrollIntoView({ behavior: "smooth", block: "center" });
}
function focusSuggest() {
  $("suggestText").focus();
  $("suggestText").scrollIntoView({ behavior: "smooth", block: "center" });
}

$("vizExpand").addEventListener("click", () => {
  const viz = $("brainViz");
  viz.classList.toggle("expanded");
  $("vizExpand").firstChild.textContent = viz.classList.contains("expanded") ? "shrink " : "expand ";
});

$("dockSpeak").addEventListener("click", focusSpeak);
$("dockSuggest").addEventListener("click", focusSuggest);
$("dockHelp").addEventListener("click", () => {
  $("helpOverlay").hidden = !$("helpOverlay").hidden;
});
$("helpOverlay").addEventListener("click", (ev) => {
  if (ev.target === $("helpOverlay")) $("helpOverlay").hidden = true;
});

document.addEventListener("keydown", (ev) => {
  const typing = ["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName);
  if (ev.key === "Escape") {
    $("helpOverlay").hidden = true;
    if (typing) document.activeElement.blur();
    return;
  }
  if (typing || ev.metaKey || ev.ctrlKey || ev.altKey) return;
  switch (ev.key) {
    case "c": window.location.href = "/converse/"; break;
    case "x": window.location.href = "/connectome/"; break;
    case "s": ev.preventDefault(); focusSpeak(); break;
    case "g": ev.preventDefault(); focusSuggest(); break;
    case "r": $("refreshBtn").click(); break;
    case "b": $("panelBrain").scrollIntoView({ behavior: "smooth" }); break;
    case "v": $("vizExpand").click(); break;
    case "?": $("helpOverlay").hidden = !$("helpOverlay").hidden; break;
  }
});

/* ---- AvatarFrame rig (tier 0 procedural) ---- */

const rig = {
  browL: $("browL"), browR: $("browR"),
  lidL: $("lidL"), lidR: $("lidR"),
  irisL: $("irisL"), irisR: $("irisR"),
  mouth: $("mouth"), teeth: $("teeth"),
  caption: $("rigCaption"),
};
let speaking = false;

function applyFrame(bs) {
  const g = (k) => bs[k] || 0;
  const blink = Math.max(g("eyeBlinkLeft"), g("eyeBlinkRight"));
  rig.lidL.setAttribute("transform", `scale(1,${blink})`);
  rig.lidR.setAttribute("transform", `scale(1,${blink})`);
  const browUp = g("browInnerUp") * 3.2 - Math.max(g("browDownLeft"), g("browDownRight")) * 2.2;
  rig.browL.setAttribute("transform", `translate(0,${-browUp})`);
  rig.browR.setAttribute("transform", `translate(0,${-browUp})`);
  const gaze = (g("eyeLookOutRight") - g("eyeLookOutLeft")) * 10;
  rig.irisL.setAttribute("cx", 35 + gaze);
  rig.irisR.setAttribute("cx", 65 + gaze);
  const jaw = g("jawOpen");
  const pucker = g("mouthPucker") + g("mouthFunnel") * 0.6;
  const stretch = Math.max(g("mouthStretchLeft"), g("mouthStretchRight"));
  const smile = Math.max(g("mouthSmileLeft"), g("mouthSmileRight"));
  rig.mouth.setAttribute("ry", (2.2 + jaw * 14).toFixed(2));
  rig.mouth.setAttribute("rx", (11 - pucker * 4.5 + stretch * 3 + smile * 1.5).toFixed(2));
  rig.mouth.setAttribute("cy", (80 + jaw * 2.5).toFixed(2));
  rig.teeth.setAttribute("opacity", jaw > 0.3 ? "0.9" : "0");
}

function playTimeline(tl) {
  speaking = true;
  $("portrait").classList.add("speaking");
  rig.caption.textContent = `speaking · ${tl.fps} fps · ${tl.duration_s}s`;
  const t0 = performance.now();
  function step(now) {
    const idx = Math.min(Math.floor(((now - t0) / 1000) * tl.fps), tl.frames.length - 1);
    applyFrame(tl.frames[idx].blendshapes);
    if (idx < tl.frames.length - 1) requestAnimationFrame(step);
    else {
      speaking = false;
      $("portrait").classList.remove("speaking");
      rig.caption.textContent = "idle";
      applyFrame({});
    }
  }
  requestAnimationFrame(step);
}

const sayParam = new URLSearchParams(location.search).get("say");
if (sayParam) $("speakText").value = sayParam;

$("speakForm").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = $("speakText").value.trim();
  if (!text || speaking) return;
  const r = await fetch("/api/avatar/speak", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ text, emotion: "warm" }),
  });
  const tl = await r.json();
  if (tl.frames) playTimeline(tl);
});

/* idle micro-life: blink every 3–5 s when not speaking */
(function idleBlink() {
  if (!speaking) {
    applyFrame({ eyeBlinkLeft: 1, eyeBlinkRight: 1 });
    setTimeout(() => { if (!speaking) applyFrame({}); }, 130);
  }
  setTimeout(idleBlink, 3000 + Math.random() * 2000);
})();

loadStatus();
loadSuggestions();
connectBrain();
setInterval(loadStatus, 90000);
