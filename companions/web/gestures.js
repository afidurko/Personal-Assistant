/* Cam web companion — hand gestures.
 *
 * On-device: MediaPipe tasks-vision GestureRecognizer (WASM) on the camera
 * preview → 21 landmarks + canned label per hand. Frames never leave the
 * device; only landmarks (no pixels) go to Cam's converse server over the
 * tailnet, where cam_gesture_engine (HaGRID labels + Kazuhito00 heads +
 * Ha0Tang key frames + Cam rules) segments and resolves them.
 *
 * Coordinates: MediaPipe runs on the raw selfie frame, so we send
 * mirror=true and the engine flips x into the screen space Aaron sees.
 *
 * Hooks for app.js:
 *   document.body.dataset.camContext   — "home" | "speaking" | "prompt" | "reading" | ...
 *   document.body.dataset.aaronIdentity — "1" while Aaron's voice/face gate is fresh
 *   window.addEventListener("cam-gesture-intent", (e) => e.detail)  — every resolved intent
 */
(() => {
  const $ = (id) => document.getElementById(id);
  const TASKS_VISION = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";
  const MODEL_URL =
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task";
  const TARGET_FPS = 30;
  const BATCH_MS = 200;

  const video = $("camPreview");
  const overlay = $("gestureOverlay");
  const btn = $("btnGestures");
  const statusEl = $("gestureStatus");
  const intentEl = $("gestureIntent");
  const glyph = $("gestureGlyph");
  if (!video || !btn) return;

  let recognizer = null;
  let running = false;
  let raf = 0;
  let lastFrameTs = 0;
  let batch = [];
  let batchTimer = 0;
  let t0 = 0;
  let localStream = null;
  let muted = false;
  const device = /iPad/.test(navigator.userAgent)
    ? "ipad"
    : /iPhone/.test(navigator.userAgent)
    ? "iphone"
    : "web";

  const status = (msg, kind) => {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.className = "gesture-status" + (kind ? " " + kind : "");
  };

  async function ensureCamera() {
    if (video.srcObject) return;
    localStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user", width: { ideal: 960 }, height: { ideal: 540 } },
      audio: false,
    });
    video.srcObject = localStream;
    video.setAttribute("playsinline", "true");
    await video.play().catch(() => {});
  }

  async function loadRecognizer() {
    if (recognizer) return recognizer;
    status("Loading hand model…");
    const vision = await import(TASKS_VISION);
    const fileset = await vision.FilesetResolver.forVisionTasks(TASKS_VISION + "/wasm");
    recognizer = await vision.GestureRecognizer.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
      runningMode: "VIDEO",
      numHands: 2,
      minHandDetectionConfidence: 0.6,
      minTrackingConfidence: 0.5,
    });
    return recognizer;
  }

  // ?gesture-demo=<name> plays synthetic landmark frames from the server through
  // the same overlay + POST path — Cam's eyes without a camera (dry run).
  const demoName = new URLSearchParams(location.search).get("gesture-demo");
  let demoTimer = 0;

  function drawLandmarks(result, mirrored = true) {
    if (!overlay) return;
    const ctx = overlay.getContext("2d");
    const w = (overlay.width = video.videoWidth || 960);
    const h = (overlay.height = video.videoHeight || 540);
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    if (mirrored) {
      // Mirror to match the selfie preview.
      ctx.translate(w, 0);
      ctx.scale(-1, 1);
    }
    ctx.lineWidth = 2;
    const chains = [
      [0, 1, 2, 3, 4],
      [0, 5, 6, 7, 8],
      [0, 9, 10, 11, 12],
      [0, 13, 14, 15, 16],
      [0, 17, 18, 19, 20],
      [5, 9, 13, 17],
    ];
    (result.landmarks || []).forEach((lm, i) => {
      ctx.strokeStyle = i === 0 ? "rgba(120, 220, 255, 0.9)" : "rgba(255, 200, 120, 0.9)";
      ctx.fillStyle = ctx.strokeStyle;
      chains.forEach((c) => {
        ctx.beginPath();
        c.forEach((k, j) => {
          const p = lm[k];
          if (j === 0) ctx.moveTo(p.x * w, p.y * h);
          else ctx.lineTo(p.x * w, p.y * h);
        });
        ctx.stroke();
      });
      lm.forEach((p) => {
        ctx.beginPath();
        ctx.arc(p.x * w, p.y * h, 3, 0, Math.PI * 2);
        ctx.fill();
      });
    });
    ctx.restore();
  }

  function toObservation(result, tMs) {
    const hands = (result.landmarks || []).map((lm, i) => {
      const hd = (result.handednesses || result.handedness || [])[i];
      const g = (result.gestures || [])[i];
      const hand = {
        handedness: hd && hd[0] ? hd[0].categoryName || hd[0].displayName || "Right" : "Right",
        score: hd && hd[0] ? Number(hd[0].score || 0.8) : 0.8,
        landmarks: lm.map((p) => [
          Number(p.x.toFixed(4)),
          Number(p.y.toFixed(4)),
          Number((p.z || 0).toFixed(4)),
        ]),
        labels: {},
      };
      if (g && g[0] && g[0].categoryName) {
        hand.labels.mediapipe = [g[0].categoryName, Number(g[0].score || 0.8)];
      }
      return hand;
    });
    return {
      t_ms: tMs,
      w: video.videoWidth || 960,
      h: video.videoHeight || 540,
      mirror: true,
      hands,
    };
  }

  function localHint(result) {
    const names = (result.gestures || [])
      .map((g) => (g[0] && g[0].categoryName) || "")
      .filter((n) => n && n !== "None");
    return names.length ? names.join(" + ") : (result.landmarks || []).length ? "hand" : "—";
  }

  async function flushBatch() {
    if (!batch.length) return;
    const frames = batch;
    batch = [];
    try {
      const res = await fetch("/api/spike/hand", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          frames,
          device,
          context: document.body.dataset.camContext || "home",
          aaron_identity: document.body.dataset.aaronIdentity === "1",
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        status(data.error || "gesture server error", "warn");
        return;
      }
      render(data);
    } catch (e) {
      status("Cam's server unreachable — gestures paused", "warn");
    }
  }

  function render(data) {
    const st = data.status || {};
    if (glyph) glyph.hidden = !st.engaged;
    (data.segments || []).forEach((s) => {
      status(`saw ${s.pose} · ${s.motion} · ${s.duration_ms} ms` + (s.hands === 2 ? " · two hands" : ""));
    });
    (data.intents || []).forEach((i) => {
      const mark = i.fired ? "→" : "⏸";
      if (intentEl) {
        intentEl.textContent = `${mark} ${i.name || i.gesture}: ${i.meaning} → ${i.action}` + (i.hold_reason ? ` (${i.hold_reason})` : "");
        intentEl.className = "gesture-intent " + (i.fired ? "fired" : "held");
      }
      window.dispatchEvent(new CustomEvent("cam-gesture-intent", { detail: i }));
      if (i.fired) applyIntent(i);
    });
  }

  // Minimal action bus for the reversible UI actions; the rest is logged and
  // surfaced for app.js via the cam-gesture-intent event.
  function applyIntent(i) {
    const body = document.body;
    switch (i.action) {
      case "ui.collapse":
        body.classList.add("collapsed");
        break;
      case "ui.expand":
        body.classList.remove("collapsed");
        break;
      case "converse.stop":
      case "presence.hold_all":
        if (window.speechSynthesis) window.speechSynthesis.cancel();
        break;
      case "converse.mute_toggle":
        muted = !muted;
        body.dataset.camMuted = muted ? "1" : "0";
        if (muted && window.speechSynthesis) window.speechSynthesis.cancel();
        break;
      case "ui.scroll_up":
        window.scrollBy({ top: -window.innerHeight * 0.6, behavior: "smooth" });
        break;
      case "ui.scroll_down":
        window.scrollBy({ top: window.innerHeight * 0.6, behavior: "smooth" });
        break;
      default:
        break;
    }
  }

  function loop() {
    if (!running || !recognizer) return;
    raf = requestAnimationFrame(loop);
    const now = performance.now();
    if (now - lastFrameTs < 1000 / TARGET_FPS) return;
    if (video.readyState < 2) return;
    lastFrameTs = now;
    let result;
    try {
      result = recognizer.recognizeForVideo(video, now);
    } catch (e) {
      return;
    }
    drawLandmarks(result);
    const tMs = Math.round(now - t0);
    batch.push(toObservation(result, tMs));
    if (statusEl && !statusEl.dataset.hold) {
      statusEl.dataset.local = localHint(result);
    }
  }

  async function startDemo(name) {
    const res = await fetch(`/api/gesture/demo?name=${encodeURIComponent(name)}&fps=30`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "demo unavailable");
    const frames = data.frames || [];
    running = true;
    batchTimer = setInterval(flushBatch, BATCH_MS);
    status(`Dry run: ${name} (${frames.length} synthetic frames, no camera)`, "ok");
    btn.textContent = "Stop gestures";
    let i = 0;
    const started = performance.now();
    const step = () => {
      if (!running) return;
      const now = performance.now() - started;
      while (i < frames.length && frames[i].t_ms <= now) {
        const f = frames[i++];
        // Synthetic frames are already in screen space: draw un-mirrored, send mirror=false.
        drawLandmarks(
          { landmarks: f.hands.map((h) => h.landmarks.map(([x, y, z]) => ({ x, y, z }))) },
          false
        );
        batch.push({ ...f, mirror: false });
      }
      if (i < frames.length) demoTimer = setTimeout(step, 16);
      else {
        // One empty frame closes any open run on the server, then flush.
        batch.push({ t_ms: frames.length ? frames[frames.length - 1].t_ms + 700 : 0, w: 960, h: 540, mirror: false, hands: [] });
        setTimeout(() => {
          flushBatch();
          status(`Dry run ${name} finished`, "ok");
        }, 250);
      }
    };
    step();
  }

  async function start() {
    try {
      btn.disabled = true;
      t0 = performance.now();
      if (demoName) {
        await startDemo(demoName);
        btn.disabled = false;
        return;
      }
      await ensureCamera();
      await loadRecognizer();
      running = true;
      batchTimer = setInterval(flushBatch, BATCH_MS);
      status("Watching your hands — hold an open palm to the screen to engage", "ok");
      btn.textContent = "Stop gestures";
      btn.disabled = false;
      loop();
    } catch (e) {
      btn.disabled = false;
      status("Gestures unavailable: " + (e && e.message ? e.message : e), "warn");
    }
  }

  function stop() {
    running = false;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    if (demoTimer) clearTimeout(demoTimer);
    demoTimer = 0;
    if (batchTimer) clearInterval(batchTimer);
    batchTimer = 0;
    flushBatch();
    if (localStream) {
      localStream.getTracks().forEach((t) => t.stop());
      localStream = null;
      video.srcObject = null;
    }
    if (overlay) overlay.getContext("2d").clearRect(0, 0, overlay.width, overlay.height);
    if (glyph) glyph.hidden = true;
    btn.textContent = "Enable gestures";
    status("Gestures off");
  }

  btn.addEventListener("click", () => (running ? stop() : start()));
  window.CamGestures = {
    start,
    stop,
    isRunning: () => running,
    isMuted: () => muted,
    setContext: (ctx) => {
      document.body.dataset.camContext = ctx || "home";
    },
    setIdentity: (ok) => {
      document.body.dataset.aaronIdentity = ok ? "1" : "0";
    },
  };
})();
