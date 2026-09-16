/* Cam web companion — mic + camera + converse */
(() => {
  const $ = (id) => document.getElementById(id);
  const statusEl = $("status");
  const partialEl = $("partial");
  const transcriptEl = $("transcript");
  const micLevel = $("micLevel");
  const video = $("camPreview");
  const btnMic = $("btnMic");
  const btnCam = $("btnCam");
  const btnStop = $("btnStop");
  const textForm = $("textForm");
  const textIn = $("textIn");

  let recognizing = false;
  let recognition = null;
  let audioCtx = null;
  let analyser = null;
  let micStream = null;
  let camStream = null;
  let raf = 0;

  function setStatus(msg, kind = "") {
    statusEl.textContent = msg;
    statusEl.className = "status" + (kind ? " " + kind : "");
  }

  function addBubble(who, text) {
    const div = document.createElement("div");
    div.className = "bubble " + who;
    div.innerHTML = `<div class="who">${who === "aaron" ? "Aaron" : "Cam"}</div><div></div>`;
    div.lastChild.textContent = text;
    transcriptEl.appendChild(div);
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  function speakCam(text, opts = {}) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = opts.lang || "en-US";
    u.rate = opts.rate ?? 0.95;
    u.pitch = opts.pitch ?? 1.05;
    // Prefer a soft female English voice when available
    const voices = window.speechSynthesis.getVoices();
    const prefer = voices.find((v) =>
      /female|samantha|karen|moira|tessa|fiona|victoria|zira/i.test(v.name)
    ) || voices.find((v) => v.lang.startsWith("en"));
    if (prefer) u.voice = prefer;
    window.speechSynthesis.speak(u);
  }

  async function postJSON(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async function sendTurn(text, source) {
    if (!text.trim()) return;
    addBubble("aaron", text);
    partialEl.textContent = "";
    setStatus("Cam is thinking…");
    try {
      await postJSON("/api/spike/mic", {
        purpose: "conversation",
        transcript: text,
        duration_ms: null,
      });
      const turn = await postJSON("/api/turn", { text, transcript: text, source });
      addBubble("cam", turn.cam);
      speakCam(turn.cam, turn.speak || {});
      setStatus("Listening — mic ready", "ok");
    } catch (e) {
      setStatus("Turn failed: " + e.message, "warn");
    }
  }

  function meterLoop() {
    if (!analyser) return;
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / data.length);
    micLevel.style.width = Math.min(100, Math.round(rms * 400)) + "%";
    raf = requestAnimationFrame(meterLoop);
  }

  async function enableMic() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("This browser cannot access the microphone.", "warn");
      return;
    }
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
      video: false,
    });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const src = audioCtx.createMediaStreamSource(micStream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    src.connect(analyser);
    meterLoop();

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setStatus("Mic on, but speech recognition unsupported — type below.", "warn");
      btnStop.disabled = false;
      return;
    }
    recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (ev) => {
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
    recognition.onerror = (ev) => setStatus("Speech error: " + ev.error, "warn");
    recognition.onend = () => {
      if (recognizing) {
        try { recognition.start(); } catch (_) {}
      }
    };
    recognizing = true;
    recognition.start();
    btnMic.disabled = true;
    btnStop.disabled = false;
    setStatus("Mic live — speak to Cam", "ok");
  }

  async function enableCam() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus("Camera API missing in this browser.", "warn");
      return;
    }
    camStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "user" },
      audio: false,
    });
    video.srcObject = camStream;
    await postJSON("/api/spike/camera", {
      purpose: "presence",
      aaron_face_hint: true,
      frame_bytes: null,
    });
    btnCam.disabled = true;
    btnStop.disabled = false;
    setStatus("Camera on — face path spiked", "ok");
  }

  function stopAll() {
    recognizing = false;
    try { recognition?.stop(); } catch (_) {}
    recognition = null;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    micStream?.getTracks().forEach((t) => t.stop());
    camStream?.getTracks().forEach((t) => t.stop());
    micStream = null;
    camStream = null;
    audioCtx?.close();
    audioCtx = null;
    analyser = null;
    video.srcObject = null;
    micLevel.style.width = "0%";
    btnMic.disabled = false;
    btnCam.disabled = false;
    btnStop.disabled = true;
    setStatus("Stopped. Enable mic or camera to continue.");
  }

  btnMic.addEventListener("click", () => enableMic().catch((e) => setStatus(e.message, "warn")));
  btnCam.addEventListener("click", () => enableCam().catch((e) => setStatus(e.message, "warn")));
  btnStop.addEventListener("click", stopAll);
  textForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const v = textIn.value;
    textIn.value = "";
    sendTurn(v, "text");
  });

  fetch("/api/health")
    .then((r) => r.json())
    .then((h) => {
      const net = h.network || {};
      const via = net.tailscale_enabled ? `tailscale · ${net.iphone_open || net.url || ""}` : "local";
      setStatus(
        h.ok
          ? `Cam online · ENABLED · ${via} · tap Enable mic & talk`
          : "Cam health failed",
        h.ok ? "ok" : "warn"
      );
    })
    .catch(() => setStatus("Cannot reach Cam server", "warn"));

  // Warm voices for TTS
  if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
  }
})();
