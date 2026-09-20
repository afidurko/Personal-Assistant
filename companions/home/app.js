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
setInterval(loadStatus, 90000);
