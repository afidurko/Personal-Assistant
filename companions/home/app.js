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

loadStatus();
loadSuggestions();
setInterval(loadStatus, 90000);
