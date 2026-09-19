/**
 * Pupil / iris gaze control for the AR card battle.
 * MediaPipe Face Landmarker → iris centers → calibrated screen point → dwell select.
 * Falls back to pointer-as-gaze when the webcam is unavailable.
 */
(function () {
  var DWELL_MS = 750;
  var SMOOTH = 0.35;
  var state = {
    mode: 'idle', // idle | calibrating | tracking
    x: window.innerWidth / 2,
    y: window.innerHeight / 2,
    sx: window.innerWidth / 2,
    sy: window.innerHeight / 2,
    dwellTarget: null,
    dwellStarted: 0,
    calibration: null,
    samples: [],
    usingCamera: false,
    faceLandmarker: null,
    video: null,
    raf: 0
  };

  var cursor = document.getElementById('gaze-cursor');
  var ring = document.getElementById('gaze-dwell');
  var statusEl = document.getElementById('gaze-status');
  var calibOverlay = document.getElementById('gaze-calib');
  var preview = document.getElementById('gaze-preview');

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function smoothTo(x, y) {
    state.sx += (x - state.sx) * SMOOTH;
    state.sy += (y - state.sy) * SMOOTH;
    state.x = state.sx;
    state.y = state.sy;
    if (cursor) {
      cursor.style.transform = 'translate(' + state.x + 'px, ' + state.y + 'px)';
      cursor.classList.add('on');
    }
  }

  function hitTest() {
    var targets = document.querySelectorAll('[data-gaze-target]');
    var best = null;
    var bestDist = Infinity;
    var pad = 12;
    for (var i = 0; i < targets.length; i++) {
      var target = targets[i];
      if (target.hasAttribute('hidden')) continue;
      var host = target.closest('#moves');
      if (host && host.hidden) continue;
      var view = document.getElementById('ar-view');
      if (target.id === 'scan-btn' && view && view.classList.contains('mode-battle')) continue;
      var style = window.getComputedStyle(target);
      if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
      var r = target.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      var inside =
        state.x >= r.left - pad &&
        state.x <= r.right + pad &&
        state.y >= r.top - pad &&
        state.y <= r.bottom + pad;
      if (!inside) continue;
      var cx = (r.left + r.right) / 2;
      var cy = (r.top + r.bottom) / 2;
      var d = (state.x - cx) * (state.x - cx) + (state.y - cy) * (state.y - cy);
      if (d < bestDist) {
        bestDist = d;
        best = target;
      }
    }
    return best;
  }

  function activate(el) {
    if (!el) return;
    el.classList.remove('gaze-hot');
    // Prefer click so existing listeners fire
    el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    setStatus('Selected · ' + (el.getAttribute('aria-label') || el.textContent || el.id || 'target').trim().slice(0, 28));
  }

  function updateDwell(now) {
    var target = hitTest();
    document.querySelectorAll('.gaze-hot').forEach(function (n) {
      if (n !== target) n.classList.remove('gaze-hot');
    });

    if (!target) {
      state.dwellTarget = null;
      state.dwellStarted = 0;
      if (ring) {
        ring.style.strokeDashoffset = '94';
        ring.classList.remove('filling');
      }
      return;
    }

    target.classList.add('gaze-hot');
    if (state.dwellTarget !== target) {
      state.dwellTarget = target;
      state.dwellStarted = now;
    }
    var t = Math.min(1, (now - state.dwellStarted) / DWELL_MS);
    if (ring) {
      ring.classList.add('filling');
      ring.style.strokeDashoffset = String(94 * (1 - t));
    }
    if (t >= 1) {
      var chosen = state.dwellTarget;
      state.dwellTarget = null;
      state.dwellStarted = 0;
      activate(chosen);
    }
  }

  // —— Calibration: map raw iris UV → screen with affine fit ——
  function fitAffine(samples) {
    // samples: {u,v,x,y}  (u,v = raw gaze 0..1-ish)
    // Solve x = a*u + b*v + c ; y = d*u + e*v + f
    if (samples.length < 3) return null;
    function solve(rows) {
      // Gaussian elimination 3x3
      var m = rows.map(function (r) { return r.slice(); });
      for (var i = 0; i < 3; i++) {
        var pivot = i;
        for (var r = i + 1; r < 3; r++) if (Math.abs(m[r][i]) > Math.abs(m[pivot][i])) pivot = r;
        var tmp = m[i]; m[i] = m[pivot]; m[pivot] = tmp;
        var div = m[i][i] || 1e-6;
        for (var c = i; c < 4; c++) m[i][c] /= div;
        for (r = 0; r < 3; r++) {
          if (r === i) continue;
          var f = m[r][i];
          for (c = i; c < 4; c++) m[r][c] -= f * m[i][c];
        }
      }
      return [m[0][3], m[1][3], m[2][3]];
    }
    // Use first 3 well-spaced + average extras into them if more
    var pts = samples.slice(0, 5);
    var Ax = [], Ay = [];
    for (var i = 0; i < 3; i++) {
      var p = pts[i];
      Ax.push([p.u, p.v, 1, p.x]);
      Ay.push([p.u, p.v, 1, p.y]);
    }
    var cx = solve(Ax);
    var cy = solve(Ay);
    return { ax: cx[0], bx: cx[1], cx: cx[2], ay: cy[0], by: cy[1], cy: cy[2] };
  }

  function applyCalib(u, v) {
    var c = state.calibration;
    if (!c) {
      return {
        x: u * window.innerWidth,
        y: v * window.innerHeight
      };
    }
    return {
      x: c.ax * u + c.bx * v + c.cx,
      y: c.ay * u + c.by * v + c.cy
    };
  }

  function irisUV(landmarks) {
    // MediaPipe face mesh iris indices
    var L_IRIS = 468, R_IRIS = 473;
    var L_OUT = 33, L_IN = 133, L_TOP = 159, L_BOT = 145;
    var R_OUT = 263, R_IN = 362, R_TOP = 386, R_BOT = 374;
    if (!landmarks || landmarks.length < 478) return null;

    function eyeGaze(iris, outI, inI, topI, botI) {
      var irisP = landmarks[iris];
      var outP = landmarks[outI];
      var inP = landmarks[inI];
      var topP = landmarks[topI];
      var botP = landmarks[botI];
      var midX = (outP.x + inP.x) / 2;
      var midY = (topP.y + botP.y) / 2;
      var halfW = Math.max(1e-4, Math.abs(outP.x - inP.x) / 2);
      var halfH = Math.max(1e-4, Math.abs(botP.y - topP.y) / 2);
      // mirrored webcam: flip X so looking left → cursor left
      var gx = 0.5 - (irisP.x - midX) / (halfW * 2.2);
      var gy = 0.5 + (irisP.y - midY) / (halfH * 2.2);
      return { u: gx, v: gy };
    }

    var L = eyeGaze(L_IRIS, L_OUT, L_IN, L_TOP, L_BOT);
    var R = eyeGaze(R_IRIS, R_OUT, R_IN, R_TOP, R_BOT);
    return { u: (L.u + R.u) / 2, v: (L.v + R.v) / 2 };
  }

  async function initMediaPipe() {
    setStatus('Loading pupil tracker…');
    var vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/+esm');
    var fileset = await vision.FilesetResolver.forVisionTasks(
      'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm'
    );
    state.faceLandmarker = await vision.FaceLandmarker.createFromOptions(fileset, {
      baseOptions: {
        modelAssetPath:
          'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
        delegate: 'GPU'
      },
      runningMode: 'VIDEO',
      numFaces: 1,
      outputFaceBlendshapes: false,
      outputFacialTransformationMatrixes: false
    });

    state.video = document.createElement('video');
    state.video.setAttribute('playsinline', '');
    state.video.autoplay = true;
    state.video.muted = true;
    if (preview) {
      preview.srcObject = null;
      // attach after stream
    }

    var stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    });
    state.video.srcObject = stream;
    if (preview) {
      preview.srcObject = stream;
      preview.play().catch(function () {});
    }
    await state.video.play();
    state.usingCamera = true;
    setStatus('Pupils locked · calibrate gaze');
    startCalibration();
  }

  function trackFrame() {
    state.raf = requestAnimationFrame(trackFrame);
    var now = performance.now();
    if (state.usingCamera && state.faceLandmarker && state.video && state.video.readyState >= 2) {
      var res = state.faceLandmarker.detectForVideo(state.video, now);
      if (res.faceLandmarks && res.faceLandmarks[0]) {
        var uv = irisUV(res.faceLandmarks[0]);
        if (uv) {
          if (state.mode === 'calibrating' && state._calibCollect) {
            state._calibRaw = uv;
          } else if (state.mode === 'tracking') {
            var pt = applyCalib(uv.u, uv.v);
            smoothTo(
              Math.max(0, Math.min(window.innerWidth, pt.x)),
              Math.max(0, Math.min(window.innerHeight, pt.y))
            );
          }
        }
      }
    }
    if (state.mode === 'tracking') updateDwell(now);
  }

  function startCalibration() {
    state.mode = 'calibrating';
    state.samples = [];
    state.calibration = null;
    if (!calibOverlay) {
      state.mode = 'tracking';
      return;
    }
    calibOverlay.hidden = false;
    var points = [
      { x: 0.12, y: 0.15, label: '1' },
      { x: 0.88, y: 0.15, label: '2' },
      { x: 0.5, y: 0.5, label: '3' },
      { x: 0.12, y: 0.85, label: '4' },
      { x: 0.88, y: 0.85, label: '5' }
    ];
    var idx = 0;
    var dot = document.getElementById('calib-dot');
    var hint = document.getElementById('calib-hint');

    function place() {
      var p = points[idx];
      var x = p.x * window.innerWidth;
      var y = p.y * window.innerHeight;
      dot.style.left = x + 'px';
      dot.style.top = y + 'px';
      hint.textContent = state.usingCamera
        ? 'Look at the dot · dwell or press Space / click (' + (idx + 1) + '/5)'
        : 'Point at the dot · click (' + (idx + 1) + '/5)';
      state._calibCollect = true;
      state._calibScreen = { x: x, y: y };
    }

    function capture() {
      var raw = state._calibRaw || {
        u: state._calibScreen.x / window.innerWidth,
        v: state._calibScreen.y / window.innerHeight
      };
      // For pointer fallback during calib, use pointer position as raw
      if (!state.usingCamera) {
        raw = {
          u: state._calibScreen.x / window.innerWidth,
          v: state._calibScreen.y / window.innerHeight
        };
      }
      state.samples.push({
        u: raw.u,
        v: raw.v,
        x: state._calibScreen.x,
        y: state._calibScreen.y
      });
      idx += 1;
      if (idx >= points.length) {
        state.calibration = fitAffine(state.samples) || {
          ax: window.innerWidth, bx: 0, cx: 0,
          ay: 0, by: window.innerHeight, cy: 0
        };
        calibOverlay.hidden = true;
        state.mode = 'tracking';
        state._calibCollect = false;
        setStatus(state.usingCamera
          ? 'Pupil control on · dwell ' + (DWELL_MS / 1000) + 's to select'
          : 'Pointer-gaze demo · dwell to select');
        return;
      }
      place();
    }

    place();
    function onCalibInput(evt) {
      if (state.mode !== 'calibrating') return;
      if (evt.type === 'keydown' && evt.code !== 'Space' && evt.key !== ' ') return;
      evt.preventDefault();
      capture();
    }
    window.addEventListener('keydown', onCalibInput);
    dot.addEventListener('click', onCalibInput);
    // Auto-dwell capture when looking at calib dot with camera
    var calibDwellStart = 0;
    function calibWatch() {
      if (state.mode !== 'calibrating') return;
      requestAnimationFrame(calibWatch);
      if (!state.usingCamera || !state._calibRaw) return;
      var pt = {
        x: state._calibRaw.u * window.innerWidth,
        y: state._calibRaw.v * window.innerHeight
      };
      // During calib before fit, show raw for feedback
      smoothTo(pt.x, pt.y);
      var dx = pt.x - state._calibScreen.x;
      var dy = pt.y - state._calibScreen.y;
      if (dx * dx + dy * dy < 70 * 70) {
        if (!calibDwellStart) calibDwellStart = performance.now();
        if (performance.now() - calibDwellStart > 700) {
          calibDwellStart = 0;
          capture();
        }
      } else {
        calibDwellStart = 0;
      }
    }
    calibWatch();
  }

  function enablePointerFallback() {
    state.usingCamera = false;
    setStatus('No camera · pointer acts as pupil gaze');
    window.addEventListener('pointermove', function (evt) {
      if (state.mode === 'calibrating') {
        state._calibRaw = {
          u: evt.clientX / window.innerWidth,
          v: evt.clientY / window.innerHeight
        };
      }
      if (state.mode === 'tracking' || state.mode === 'idle') {
        // Snap for pointer demo so dwell hit-tests stay aligned with the cursor.
        state.sx = evt.clientX;
        state.sy = evt.clientY;
        state.x = evt.clientX;
        state.y = evt.clientY;
        if (cursor) {
          cursor.style.transform = 'translate(' + state.x + 'px, ' + state.y + 'px)';
          cursor.classList.add('on');
        }
        if (state.mode === 'idle') state.mode = 'tracking';
      }
    }, { passive: true });
    startCalibration();
  }

  async function start() {
    cursor.classList.add('on');
    requestAnimationFrame(trackFrame);
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      enablePointerFallback();
      return;
    }
    try {
      await initMediaPipe();
    } catch (err) {
      console.warn('[pupil-gaze] camera/mediapipe failed', err);
      setStatus('Camera blocked · using pointer gaze');
      enablePointerFallback();
    }
  }

  document.getElementById('gaze-start').addEventListener('click', function () {
    document.getElementById('gaze-gate').hidden = true;
    start();
  });
  document.getElementById('gaze-pointer').addEventListener('click', function () {
    document.getElementById('gaze-gate').hidden = true;
    requestAnimationFrame(trackFrame);
    enablePointerFallback();
  });
})();
