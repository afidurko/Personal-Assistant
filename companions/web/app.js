/* Cam web companion — mic + camera + converse + Aaron voice gate (spectral + FunASR) */
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
  const btnExport = $("btnExport");
  const btnImport = $("btnImport");
  const importFile = $("importFile");
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
  let adaptiveRaised = false;
  let multiSpeakerStreak = 0;
  let acceptsSinceRaise = 0;
  let pcmChunks = [];
  let pcmSampleRate = 16000;
  let processor = null;
  let mediaSource = null;
  let voiceGate = { enrolled: false, require: true };

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
    if (document.body.dataset.camMuted === "1") return;
    u.onstart = () => { document.body.dataset.camContext = "speaking"; };
    u.onend = u.onerror = () => { document.body.dataset.camContext = "home"; };
    window.speechSynthesis.speak(u);
  }

  // Gestures: Aaron's identity is fresh for 60 s after an accepted voice turn.
  let identityTimer = 0;
  function markAaronIdentity() {
    document.body.dataset.aaronIdentity = "1";
    if (identityTimer) clearTimeout(identityTimer);
    identityTimer = setTimeout(() => {
      document.body.dataset.aaronIdentity = "0";
    }, 60000);
  }

  async function postJSON(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(
        data.cam || data.reason || data.error || res.statusText
      );
      err.status = res.status;
      err.body = data;
      err.payload = data;
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
      adaptiveRaised: adaptiveRaised,
    });
    if (voiceScoreEl) {
      const base = profile
        ? "Aaron match " + (score * 100).toFixed(0) + "%"
        : "Not enrolled";
      voiceScoreEl.textContent = adaptiveRaised ? base + " · adaptive↑" : base;
    }
    return { score: score, multi: multi, decision: decision };
  }

  function syncProfileButtons() {
    if (btnExport) btnExport.hidden = !profile;
    if (btnImport) btnImport.hidden = false;
    if (btnEnroll) btnEnroll.textContent = profile ? "Re-enroll my voice" : "Enroll my voice (10s)";
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
      multiSpeakerStreak +=
        gated.multi || gated.decision.reason === "rejected_surrounding_speech" ? 1 : 0;
      if (multiSpeakerStreak >= (gateCfg.adaptive_streak_to_raise || 2)) {
        adaptiveRaised = true;
      }
      acceptsSinceRaise = 0;
      fetch("/api/voice/gate/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          score: gated.score,
          threshold: gated.decision.threshold,
          reason: gated.decision.reason,
          source: source,
          multi_speaker_hint: gated.multi,
          device_id: "web-companion",
        }),
      }).catch(function () {});
      return;
    }

    if (source !== "text") {
      acceptsSinceRaise += 1;
      if (adaptiveRaised && acceptsSinceRaise >= (gateCfg.adaptive_cooldown_accepts || 3)) {
        adaptiveRaised = false;
        multiSpeakerStreak = 0;
        acceptsSinceRaise = 0;
      }
      if (!gated.multi) multiSpeakerStreak = 0;
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
          const audio_wav_b64 =
            source === "mic" || source === "speech" ? captureWavB64(4) : null;
          await postJSON("/api/spike/aaron.voice", {
            score: gated.score,
            aaron_voice_score: gated.score,
            enrolled: !!profile,
            multi_speaker_hint: gated.multi,
            device_id: "web-companion",
            audio_wav_b64: audio_wav_b64 || undefined,
          });
          await postJSON("/api/spike/mic", {
            purpose: "conversation",
            transcript: text,
            aaron_voice_score: gated.score,
          });
          const turnBody = {
            text: text,
            transcript: text,
            source: source,
            aaron_voice_score: gated.score,
            enrolled: !!profile,
            multi_speaker_hint: gated.multi,
            device_id: "web-companion",
          };
          if (audio_wav_b64) turnBody.audio_wav_b64 = audio_wav_b64;
          const turn = await postJSON("/api/turn", turnBody);
          if (turn.accepted === false) {
            setStatus(
              "Ignored non-Aaron voice (" + (turn.reason || "gated") + ")",
              "warn"
            );
            return;
          }
          reply = turn.cam;
          speak = turn.speak || speak;
          markAaronIdentity();
          if (turn.voice_stats) {
            adaptiveRaised = !!turn.voice_stats.adaptive_raised;
            multiSpeakerStreak = turn.voice_stats.multi_speaker_streak || multiSpeakerStreak;
          }
          if (turn.voice_gate && turn.voice_gate.aaron_score != null) {
            setStatus(
              "Aaron voice · score " + Number(turn.voice_gate.aaron_score).toFixed(2) +
                (adaptiveRaised ? " · adaptive↑" : ""),
              "ok"
            );
          }
        } catch (e) {
          if (e.status === 403) {
            if (e.body && e.body.cam) {
              addBubble("system", e.body.cam);
              setStatus("Filtered non-Aaron speech", "warn");
            } else {
              const reason = (e.payload && e.payload.reason) || "non_aaron_voice";
              if (reason === "not_enrolled") {
                setStatus(
                  "Aaron voice not enrolled yet — type below, or run aaron-voice-enroll.py",
                  "warn"
                );
              } else {
                setStatus("Surrounding voice ignored — Aaron only (" + reason + ")", "warn");
              }
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
      history.push({ role: "cam", text: reply });
      addBubble("cam", reply);
      speakCam(reply, speak);
      setStatus(
        mode === "server"
          ? "Listening — Aaron only (server)" + (adaptiveRaised ? " · adaptive↑" : "")
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
          syncProfileButtons();
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
    if (micStream && analyser && audioCtx && mediaSource) return;
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      video: false,
    });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") await audioCtx.resume();
    mediaSource = audioCtx.createMediaStreamSource(micStream);
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 2048;
    mediaSource.connect(analyser);
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

    // Rolling PCM for FunASR CAM++ gate (16 kHz mono WAV → server)
    pcmChunks = [];
    pcmSampleRate = 16000;
    const bufferSize = 4096;
    try {
      processor && processor.disconnect();
    } catch (_) {}
    processor = audioCtx.createScriptProcessor(bufferSize, 1, 1);
    mediaSource.connect(processor);
    processor.connect(audioCtx.destination);
    processor.onaudioprocess = (ev) => {
      const input = ev.inputBuffer.getChannelData(0);
      const down = downsampleBuffer(input, audioCtx.sampleRate, pcmSampleRate);
      pcmChunks.push(new Float32Array(down));
      let total = 0;
      for (let i = pcmChunks.length - 1; i >= 0; i--) {
        total += pcmChunks[i].length;
        if (total > pcmSampleRate * 8) {
          pcmChunks = pcmChunks.slice(i);
          break;
        }
      }
      const outBuf = ev.outputBuffer.getChannelData(0);
      outBuf.fill(0);
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
    if (mode === "server" && voiceGate && voiceGate.enrolled === false && !profile) {
      setStatus(
        "Mic live — enroll Aaron voice (companion or aaron-voice-enroll.py)",
        "warn"
      );
    } else {
      setStatus(
        profile
          ? "Mic live — Aaron only" + (adaptiveRaised ? " · adaptive↑" : "")
          : "Mic live — enroll your voice to filter others",
        "ok"
      );
    }
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
    try {
      processor && processor.disconnect();
    } catch (_) {}
    processor = null;
    pcmChunks = [];
    mediaSource = null;
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
  }
  if (btnExport) {
    btnExport.addEventListener("click", () => {
      if (!profile) return;
      const blob = new Blob(
        [
          JSON.stringify(
            {
              subject: "Aaron",
              exported_at: new Date().toISOString(),
              source: "web_companion_export",
              profile: profile,
            },
            null,
            2
          ),
        ],
        { type: "application/json" }
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "aaron-voice-profile.json";
      a.click();
      URL.revokeObjectURL(url);
      postJSON("/api/voice/profile", { profile: profile }).catch(function () {});
      addBubble("system", "Aaron voice profile exported.");
    });
  }
  if (btnImport && importFile) {
    btnImport.addEventListener("click", () => importFile.click());
    importFile.addEventListener("change", () => {
      const file = importFile.files && importFile.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const parsed = JSON.parse(String(reader.result || ""));
          const p = parsed.profile && parsed.profile.version === 1 ? parsed.profile : parsed;
          if (!p || p.version !== 1 || p.subject !== "Aaron" || !Array.isArray(p.bands)) {
            setStatus("Invalid Aaron voice profile", "warn");
            return;
          }
          VG.saveProfile(p, gateCfg.storage_key);
          profile = p;
          syncProfileButtons();
          postJSON("/api/voice/profile", { profile: p }).catch(function () {});
          addBubble("system", "Aaron voice profile imported.");
          setStatus("Imported Aaron voice profile", "ok");
        } catch (e) {
          setStatus("Import failed: " + e.message, "warn");
        }
        importFile.value = "";
      };
      reader.readAsText(file);
    });
  }
  textForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const v = textIn.value;
    textIn.value = "";
    sendTurn(v, "text");
  });

  if (isIOS) {
    hintEl.textContent =
      "iPhone/iPad: Add to Home Screen, enroll your voice once in quiet, then talk — Cam ignores other people (spectral + FunASR gates).";
  } else {
    hintEl.textContent =
      "Aaron-only: enroll your voice (~10s quiet), then enable mic. Surrounding conversation is filtered (browser spectral + server FunASR).";
  }

  fetch("/api/health")
    .then((r) => r.json())
    .then((h) => {
      if (h && h.ok) {
        mode = "server";
        if (h.voice_gate) gateCfg = VG.mergeConfig(h.voice_gate);
        if (h.voice_gate_stats && h.voice_gate_stats.adaptive_raised) {
          adaptiveRaised = true;
        }
        const net = h.network || {};
        const vg = (h.capabilities && h.capabilities.aaron_voice_gate) || {};
        voiceGate = vg;
        const via = net.tailscale_enabled
          ? "tailscale · " + (net.iphone_open || net.url || "")
          : "local server";
        if (vg.enrolled) {
          setStatus("Cam online · Aaron voice enrolled · " + via, "ok");
        } else if (profile) {
          setStatus("Cam online · spectral enrolled · FunASR waiting · " + via, "ok");
        } else {
          setStatus("Cam online · voice gate waiting for enrollment · " + via, "warn");
        }
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
  syncProfileButtons();

  if (window.speechSynthesis) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
  }
})();
