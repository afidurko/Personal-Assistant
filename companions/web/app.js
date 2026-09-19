/* Cam web companion — mic + camera + converse + Aaron voice gate */
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
  let pcmChunks = [];
  let pcmSampleRate = 16000;
  let processor = null;
  let voiceGate = { enrolled: false, require: true };

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
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.reason || data.error || (await res.text?.()) || res.statusText);
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    return data;
  }

  function floatTo16BitPCM(float32) {
    const out = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out;
  }

  function encodeWavMono(float32, sampleRate) {
    const pcm = floatTo16BitPCM(float32);
    const buffer = new ArrayBuffer(44 + pcm.length * 2);
    const view = new DataView(buffer);
    const writeStr = (offset, str) => {
      for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
    };
    writeStr(0, "RIFF");
    view.setUint32(4, 36 + pcm.length * 2, true);
    writeStr(8, "WAVE");
    writeStr(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeStr(36, "data");
    view.setUint32(40, pcm.length * 2, true);
    let off = 44;
    for (let i = 0; i < pcm.length; i++, off += 2) view.setInt16(off, pcm[i], true);
    return buffer;
  }

  function bytesToBase64(buf) {
    const bytes = new Uint8Array(buf);
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  function downsampleBuffer(buffer, fromRate, toRate) {
    if (fromRate === toRate) return buffer;
    const ratio = fromRate / toRate;
    const newLen = Math.max(1, Math.round(buffer.length / ratio));
    const result = new Float32Array(newLen);
    for (let i = 0; i < newLen; i++) {
      const idx = Math.min(buffer.length - 1, Math.floor(i * ratio));
      result[i] = buffer[idx];
    }
    return result;
  }

  function recentPcmSeconds(seconds = 4) {
    if (!pcmChunks.length) return null;
    const need = Math.floor(pcmSampleRate * seconds);
    let total = 0;
    for (let i = pcmChunks.length - 1; i >= 0; i--) total += pcmChunks[i].length;
    const merged = new Float32Array(total);
    let off = 0;
    for (const c of pcmChunks) {
      merged.set(c, off);
      off += c.length;
    }
    if (merged.length <= need) return merged;
    return merged.slice(merged.length - need);
  }

  function captureWavB64(seconds = 4) {
    const pcm = recentPcmSeconds(seconds);
    if (!pcm || pcm.length < pcmSampleRate * 0.25) return null;
    const wav = encodeWavMono(pcm, pcmSampleRate);
    return bytesToBase64(wav);
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
          const audio_wav_b64 =
            source === "mic" || source === "speech" ? captureWavB64(4) : null;
          await postJSON("/api/spike/mic", {
            purpose: "conversation",
            transcript: text,
          });
          const body = {
            text,
            transcript: text,
            source,
          };
          if (audio_wav_b64) body.audio_wav_b64 = audio_wav_b64;
          const turn = await postJSON("/api/turn", body);
          if (turn.accepted === false) {
            setStatus(
              "Ignored non-Aaron voice (" + (turn.reason || "gated") + ")",
              "warn"
            );
            return;
          }
          reply = turn.cam;
          speak = turn.speak || speak;
          if (turn.voice_gate && turn.voice_gate.aaron_score != null) {
            setStatus(
              `Aaron voice · score ${Number(turn.voice_gate.aaron_score).toFixed(2)}`,
              "ok"
            );
          }
        } catch (e) {
          if (e.status === 403) {
            const reason = (e.payload && e.payload.reason) || "non_aaron_voice";
            if (reason === "not_enrolled") {
              setStatus(
                "Aaron voice not enrolled yet — type below, or run aaron-voice-enroll.py",
                "warn"
              );
            } else {
              setStatus("Surrounding voice ignored — Aaron only (" + reason + ")", "warn");
            }
            return;
          }
          mode = "on_device";
          reply = camReplyLocal(text);
          setStatus("Server unreachable — on-device Cam", "warn");
        }
      } else {
        reply = camReplyLocal(text);
      }
      if (!reply) return;
      history.push({ role: "cam", text: reply });
      addBubble("cam", reply);
      speakCam(reply, speak);
      if (mode === "server" && !(statusEl.className || "").includes("ok")) {
        setStatus("Listening — Aaron-only gate on server", "ok");
      } else if (mode !== "server") {
        setStatus("Listening — on-device (iOS)", "ok");
      }
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

    // Rolling PCM for Aaron voice gate (16 kHz mono WAV → server)
    pcmChunks = [];
    pcmSampleRate = 16000;
    const bufferSize = 4096;
    processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
    src.connect(processor);
    processor.connect(audioCtx.destination);
    processor.onaudioprocess = (ev) => {
      const input = ev.inputBuffer.getChannelData(0);
      const down = downsampleBuffer(input, audioCtx.sampleRate, pcmSampleRate);
      pcmChunks.push(new Float32Array(down));
      // Keep ~8s
      let total = 0;
      for (let i = pcmChunks.length - 1; i >= 0; i--) {
        total += pcmChunks[i].length;
        if (total > pcmSampleRate * 8) {
          pcmChunks = pcmChunks.slice(i);
          break;
        }
      }
      // Mute processor output
      const out = ev.outputBuffer.getChannelData(0);
      out.fill(0);
    };

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
    if (mode === "server" && voiceGate && voiceGate.enrolled === false) {
      setStatus(
        "Mic live — enroll Aaron voice on host for Aaron-only listen",
        "warn"
      );
    } else {
      setStatus("Mic live — Aaron-only when server gate is enrolled", "ok");
    }
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
    try {
      processor?.disconnect();
    } catch (_) {}
    processor = null;
    pcmChunks = [];
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
      "iPhone/iPad: Safari → Share → Add to Home Screen. Server mode gates mic to Aaron’s voice only.";
  }

  fetch("/api/health")
    .then((r) => r.json())
    .then((h) => {
      if (h && h.ok) {
        mode = "server";
        const net = h.network || {};
        const vg = (h.capabilities && h.capabilities.aaron_voice_gate) || {};
        voiceGate = vg;
        const via = net.tailscale_enabled
          ? `tailscale · ${net.iphone_open || net.url || ""}`
          : "local server";
        if (vg.enrolled) {
          setStatus(`Cam online · Aaron voice enrolled · ${via}`, "ok");
        } else {
          setStatus(
            `Cam online · voice gate waiting for enrollment · ${via}`,
            "warn"
          );
        }
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
