/* Cam web companion — mic + camera + Aaron-only voice gate */
(() => {
  const VG = window.CamAaronVoiceGate;
  const $ = (id) => document.getElementById(id);
  const statusEl = $("status");
  const partialEl = $("partial");
  const transcriptEl = $("transcript");
  const micLevel = $("micLevel");
  const voiceScoreEl = $("voiceScore");
  const video = $("camPreview");
  const btnMic = $("btnMic");
  const btnCam = $("btnCam");
  const btnStop = $("btnStop");
  const btnEnroll = $("btnEnroll");
  const textForm = $("textForm");
  const textIn = $("textIn");
  const hintEl = $("hint");

  let recognizing = false;
  let recognition = null;
  let audioCtx = null;
  let analyser = null;
  let micStream = null;
  let camStream = null;
  let raf = 0;
  let mode = "on_device";
  let history = [];
  let gateCfg = VG.mergeConfig();
  let profile = VG.loadProfile();
  let utter = null;
  let enroll = null;
  let enrolling = false;

  const isIOS =
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

  function setStatus(msg, kind) {
    statusEl.textContent = msg;
    statusEl.className = "status" + (kind ? " " + kind : "");
  }

  function addBubble(who, text) {
    const div = document.createElement("div");
    div.className = "bubble " + who;
    const label = who === "aaron" ? "Aaron" : who === "cam" ? "Cam" : "Gate";
    div.innerHTML = `<div class="who">${label}</div><div></div>`;
    div.lastChild.textContent = text;
    transcriptEl.appendChild(div);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  function camReplyLocal(aaronText) {
    const t = (aaronText || "").trim();
    const low = t.toLowerCase();
    if (!t) return "I'm here, Aaron. Whenever you're ready — I'm listening.";
    if (/hello|hi cam|hey cam|^hi\b|^hey\b/.test(low)) {
      return "Hi Aaron. Soft and clear on this device. Aaron-only voice filter is on.";
    }
    if (/mic|microphone|hear me|working/.test(low)) {
      return "Yes — I listen for your voice only. Surrounding conversation is ignored once you're enrolled.";
    }
    if (/only my voice|my voice only|ignore.*(other|people|room|noise|surround)/.test(low)) {
      return "Aaron-only mode is active. Enroll once if needed, then I'll filter other speakers.";
    }
    if (/camera|face|see me/.test(low)) {
      return "Camera is available here too. I already know your face from the photos you shared.";
    }
    if (/who are you|your name/.test(low)) {
      return "I'm Cam — thirty-two, from Argentina, soft airy English. You're Aaron, my only task-giver.";
    }
    if (/thank/.test(low)) return "Of course. I'm right here.";
    if (/ipad|iphone|tailscale/.test(low)) {
      return "We're set for iPhone and iPad over Tailscale. On-device mode works without a Mac.";
    }
    const short = t.length < 120 ? t : t.slice(0, 117) + "…";
    return `I heard you: “${short}”. Tell me the next step and I'll take it from there.`;
  }

  function speakCam(text, opts) {
    opts = opts || {};
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = opts.lang || "en-US";
    u.rate = opts.rate ?? 0.95;
    u.pitch = opts.pitch ?? 1.05;
    const voices = window.speechSynthesis.getVoices();
    const prefer =
      voices.find((v) =>
        /female|samantha|karen|moira|tessa|fiona|victoria|zira/i.test(v.name)
      ) || voices.find((v) => v.lang && v.lang.startsWith("en"));
    if (prefer) u.voice = prefer;
    window.speechSynthesis.speak(u);
  }

  async function postJSON(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.cam || data.error || res.statusText);
      err.status = res.status;
      err.body = data;
      throw err;
    }
    return data;
  }

  function gateUtterance(source) {
    let score = source === "text" ? 1 : 0;
    let multi = false;
    if (source !== "text" && profile && utter && utter.ready()) {
      score = utter.scoreAgainst(profile);
      const live = utter.toProfile();
      multi = VG.multiSpeakerHint(live ? live.bands : profile.bands, profile, score);
    }
    if (utter) utter.reset();
    const decision = VG.decide(score, gateCfg, {
      enrolled: !!profile,
      multiSpeakerHint: multi,
      source: source,
    });
    if (voiceScoreEl) {
      voiceScoreEl.textContent = profile
        ? `Aaron match ${(score * 100).toFixed(0)}%`
        : "Not enrolled";
    }
    return { score: score, multi: multi, decision: decision };
  }

  async function sendTurn(text, source) {
    if (!text.trim()) return;
    const gated = gateUtterance(source);
    if (!gated.decision.accept) {
      const msg =
        gated.decision.reason === "enrollment_required"
          ? "Enroll your voice first (quiet ~10s) so Cam can ignore other people."
          : gated.decision.reason === "rejected_surrounding_speech"
            ? "Heard other voices nearby — ignored. Speak again when it’s you."
            : `Not matched as Aaron (${(gated.score * 100).toFixed(0)}%). Ignored surrounding speech.`;
      addBubble("system", msg);
      setStatus(msg, "warn");
      return;
    }

    addBubble("aaron", text);
    partialEl.textContent = "";
    history.push({ role: "aaron", text: text });
    setStatus("Cam is listening…");
    try {
      let reply;
      let speak = { rate: 0.95, pitch: 1.05, lang: "en-US" };
      if (mode === "server") {
        try {
          await postJSON("/api/spike/aaron.voice", {
            score: gated.score,
            enrolled: !!profile,
            multi_speaker_hint: gated.multi,
            device_id: "web-companion",
          });
          await postJSON("/api/spike/mic", {
            purpose: "conversation",
            transcript: text,
            aaron_voice_score: gated.score,
          });
          const turn = await postJSON("/api/turn", {
            text: text,
            transcript: text,
            source: source,
            aaron_voice_score: gated.score,
            enrolled: !!profile,
            multi_speaker_hint: gated.multi,
          });
          reply = turn.cam;
          speak = turn.speak || speak;
        } catch (e) {
          if (e.status === 403 && e.body && e.body.cam) {
            addBubble("system", e.body.cam);
            setStatus("Filtered non-Aaron speech", "warn");
            return;
          }
          mode = "on_device";
          reply = camReplyLocal(text);
          setStatus("Server unreachable — on-device Cam", "warn");
        }
      } else {
        reply = camReplyLocal(text);
      }
      history.push({ role: "cam", text: reply });
      addBubble("cam", reply);
      speakCam(reply, speak);
      setStatus(
        mode === "server"
          ? "Listening — Aaron only (server)"
          : "Listening — Aaron only (on-device)",
        "ok"
      );
    } catch (e) {
      setStatus("Turn failed: " + e.message, "warn");
    }
  }

  function meterLoop() {
    if (!analyser || !audioCtx) return;
    const frame = VG.extractVoiceFrame(analyser, audioCtx.sampleRate, gateCfg);
    micLevel.style.width = Math.min(100, Math.round(frame.rms * 400)) + "%";

    if (enrolling && enroll) {
      enroll.push(frame);
      const need = gateCfg.enroll_seconds;
      const pct = Math.min(100, Math.round((enroll.elapsedSeconds() / need) * 100));
      partialEl.textContent = `Enrolling Aaron’s voice… ${pct}% — speak alone`;
      if (enroll.elapsedSeconds() >= need && enroll.ready()) {
        const p = enroll.toProfile();
        if (p) {
          VG.saveProfile(p, gateCfg.storage_key);
          profile = p;
          enrolling = false;
          enroll = null;
          addBubble(
            "system",
            "Aaron voice enrolled. Cam will only accept your voice in noisy rooms."
          );
          setStatus("Enrolled — Aaron-only listening", "ok");
          if (btnEnroll) btnEnroll.textContent = "Re-enroll my voice";
        }
      }
    } else if (utter && frame.voiced) {
      utter.push(frame);
      if (profile && utter.ready() && voiceScoreEl) {
        voiceScoreEl.textContent =
          "Aaron match " + (utter.scoreAgainst(profile) * 100).toFixed(0) + "%";
      }
    }
    raf = requestAnimationFrame(meterLoop);
  }

  async function ensureAudio() {
    if (micStream && analyser && audioCtx) return;
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      video: false,
    });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") await audioCtx.resume();
    const src = audioCtx.createMediaStreamSource(micStream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    src.connect(analyser);
    if (!raf) meterLoop();
  }

  async function startEnroll() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("This browser cannot access the microphone.", "warn");
      return;
    }
    await ensureAudio();
    enroll = new VG.Accumulator(gateCfg);
    enrolling = true;
    btnStop.disabled = false;
    addBubble(
      "system",
      "Speak alone for ~" + gateCfg.enroll_seconds + "s so Cam learns only your voice."
    );
    setStatus("Enrolling Aaron’s voice…", "ok");
  }

  async function enableMic() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("This browser cannot access the microphone.", "warn");
      return;
    }
    await ensureAudio();
    utter = new VG.Accumulator(gateCfg);

    if (!profile && gateCfg.require_enrollment_for_mic) {
      await startEnroll();
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setStatus("Mic on — Safari speech unsupported here; type below.", "warn");
      btnStop.disabled = false;
      return;
    }
    recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (ev) => {
      if (enrolling) {
        partialEl.textContent = "Enrolling… keep talking alone";
        return;
      }
      let interim = "";
      let finalText = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interim += r[0].transcript;
      }
      partialEl.textContent = interim || "…";
      if (finalText.trim()) sendTurn(finalText.trim(), "mic");
    };
    recognition.onerror = (ev) => {
      if (ev.error !== "no-speech") setStatus("Speech: " + ev.error, "warn");
    };
    recognition.onend = () => {
      if (recognizing) {
        try {
          recognition.start();
        } catch (_) {}
      }
    };
    recognizing = true;
    recognition.start();
    btnMic.disabled = true;
    btnStop.disabled = false;
    setStatus(
      profile ? "Mic live — Aaron only" : "Mic live — enroll your voice to filter others",
      "ok"
    );
  }

  async function enableCam() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Camera API missing in this browser.", "warn");
      return;
    }
    camStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false,
    });
    video.srcObject = camStream;
    video.setAttribute("playsinline", "true");
    await video.play().catch(() => {});
    if (mode === "server") {
      try {
        await postJSON("/api/spike/camera", {
          purpose: "presence",
          aaron_face_hint: true,
        });
      } catch (_) {}
    }
    btnCam.disabled = true;
    btnStop.disabled = false;
    setStatus("Camera on", "ok");
  }

  function stopAll() {
    recognizing = false;
    enrolling = false;
    try {
      recognition && recognition.stop();
    } catch (_) {}
    recognition = null;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    if (micStream) micStream.getTracks().forEach((t) => t.stop());
    if (camStream) camStream.getTracks().forEach((t) => t.stop());
    micStream = null;
    camStream = null;
    if (audioCtx) audioCtx.close();
    audioCtx = null;
    analyser = null;
    utter = null;
    enroll = null;
    video.srcObject = null;
    micLevel.style.width = "0%";
    btnMic.disabled = false;
    btnCam.disabled = false;
    btnStop.disabled = true;
    setStatus("Stopped. Enable mic or enroll voice to continue.");
  }

  btnMic.addEventListener("click", () =>
    enableMic().catch((e) => setStatus(e.message, "warn"))
  );
  btnCam.addEventListener("click", () =>
    enableCam().catch((e) => setStatus(e.message, "warn"))
  );
  btnStop.addEventListener("click", stopAll);
  if (btnEnroll) {
    btnEnroll.addEventListener("click", () =>
      startEnroll().catch((e) => setStatus(e.message, "warn"))
    );
    if (profile) btnEnroll.textContent = "Re-enroll my voice";
  }
  textForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const v = textIn.value;
    textIn.value = "";
    sendTurn(v, "text");
  });

  if (isIOS) {
    hintEl.textContent =
      "iPhone/iPad: Add to Home Screen, enroll your voice once in quiet, then talk — Cam ignores other people.";
  } else {
    hintEl.textContent =
      "Aaron-only: enroll your voice (~10s quiet), then enable mic. Surrounding conversation is filtered out.";
  }

  fetch("/api/health")
    .then((r) => r.json())
    .then((h) => {
      if (h && h.ok) {
        mode = "server";
        if (h.voice_gate) gateCfg = VG.mergeConfig(h.voice_gate);
        const net = h.network || {};
        const via = net.tailscale_enabled
          ? "tailscale · " + (net.iphone_open || net.url || "")
          : "local server";
        setStatus("Cam online · Aaron-only voice · " + via, "ok");
      } else {
        mode = "on_device";
        setStatus("On-device Cam — enroll voice, then mic", "ok");
      }
    })
    .catch(() => {
      mode = "on_device";
      setStatus("On-device Cam — enroll voice, then Enable mic & talk", "ok");
    });

  fetch("/config/identity/aaron-voice-gate.json")
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null)
    .then((cfg) => {
      if (cfg) gateCfg = VG.mergeConfig(cfg);
    });

  if (voiceScoreEl) {
    voiceScoreEl.textContent = profile ? "Aaron enrolled" : "Not enrolled";
  }

  if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
  }
})();
