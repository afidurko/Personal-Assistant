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
  const hintEl = $("hint");

  let recognizing = false;
  let recognition = null;
  let audioCtx = null;
  let analyser = null;
  let micStream = null;
  let camStream = null;
  let raf = 0;
  let mode = "on_device"; // on_device | server
  let history = [];

  const isIOS =
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

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

  function camReplyLocal(aaronText) {
    const t = (aaronText || "").trim();
    const low = t.toLowerCase();
    if (!t) return "I'm here, Aaron. Whenever you're ready — I'm listening.";
    if (/hello|hi cam|hey cam|^hi\b|^hey\b/.test(low)) {
      return "Hi Aaron. Soft and clear on this device. Mic path is on — say what you need.";
    }
    if (/mic|microphone|hear me|working/.test(low)) {
      return "Yes — I can hear you in on-device mode on your iPhone or iPad. Keep talking.";
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

  function speakCam(text, opts = {}) {
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
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }

  async function sendTurn(text, source) {
    if (!text.trim()) return;
    addBubble("aaron", text);
    partialEl.textContent = "";
    history.push({ role: "aaron", text });
    setStatus("Cam is listening…");
    try {
      let reply;
      let speak = { rate: 0.95, pitch: 1.05, lang: "en-US" };
      if (mode === "server") {
        try {
          await postJSON("/api/spike/mic", {
            purpose: "conversation",
            transcript: text,
          });
          const turn = await postJSON("/api/turn", {
            text,
            transcript: text,
            source,
          });
          reply = turn.cam;
          speak = turn.speak || speak;
        } catch (_) {
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
        mode === "server" ? "Listening — server mode" : "Listening — on-device (iOS)",
        "ok"
      );
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
    if (audioCtx.state === "suspended") await audioCtx.resume();
    const src = audioCtx.createMediaStreamSource(micStream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    src.connect(analyser);
    meterLoop();

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
    try {
      recognition?.stop();
    } catch (_) {}
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

  btnMic.addEventListener("click", () =>
    enableMic().catch((e) => setStatus(e.message, "warn"))
  );
  btnCam.addEventListener("click", () =>
    enableCam().catch((e) => setStatus(e.message, "warn"))
  );
  btnStop.addEventListener("click", stopAll);
  textForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const v = textIn.value;
    textIn.value = "";
    sendTurn(v, "text");
  });

  if (isIOS) {
    hintEl.textContent =
      "iPhone/iPad: use Safari → Share → Add to Home Screen, then open Cam and tap Enable mic & talk.";
  }

  // Prefer server if present; else on-device
  fetch("/api/health")
    .then((r) => r.json())
    .then((h) => {
      if (h && h.ok) {
        mode = "server";
        const net = h.network || {};
        const via = net.tailscale_enabled
          ? `tailscale · ${net.iphone_open || net.url || ""}`
          : "local server";
        setStatus(`Cam online · ENABLED · ${via}`, "ok");
      } else {
        mode = "on_device";
        setStatus("On-device Cam (no server) — ready for mic", "ok");
      }
    })
    .catch(() => {
      mode = "on_device";
      setStatus("On-device Cam for iPhone/iPad — tap Enable mic & talk", "ok");
    });

  if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () =>
      window.speechSynthesis.getVoices();
  }
})();
