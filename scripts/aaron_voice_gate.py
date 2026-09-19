#!/usr/bin/env python3
"""Aaron-only voice gate for Cam.

FunASR (CAM++ / ERes2Net) can extract speaker embeddings. This module owns the
Cam identity contract:

  enroll Aaron voice samples → store templates locally → score live audio →
  accept only segments that match Aaron above threshold.

Surrounding conversation is dropped before ASR / converse turns.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import struct
import wave
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "identity" / "aaron-voice.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_config(path: Path | None = None) -> dict:
    cfg_path = path or DEFAULT_CONFIG
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["_config_path"] = str(cfg_path)
    return cfg


def resolve_path(rel_or_abs: str | Path) -> Path:
    p = Path(rel_or_abs)
    return p if p.is_absolute() else (ROOT / p)


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    v = np.asarray(vec, dtype=np.float64).reshape(-1)
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        return v
    return v / n


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    aa = l2_normalize(a)
    bb = l2_normalize(b)
    return float(np.clip(np.dot(aa, bb), -1.0, 1.0))


def pcm16_mono_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    """Encode float32 mono [-1,1] as 16-bit PCM WAV bytes."""
    clipped = np.clip(samples.astype(np.float64), -1.0, 1.0)
    ints = (clipped * 32767.0).astype(np.int16)
    buf = bytearray()
    # Minimal WAV writer without soundfile dependency
    import io

    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(ints.tobytes())
    return bio.getvalue()


def read_wav_mono_16k(path: Path, target_sr: int = 16000) -> tuple[np.ndarray, int]:
    """Read WAV to mono float32; resample to target_sr if needed (linear)."""
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sr = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)
    if sampwidth == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sampwidth == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    if sr != target_sr and len(data) > 1:
        duration = len(data) / float(sr)
        target_n = max(1, int(round(duration * target_sr)))
        x_old = np.linspace(0.0, 1.0, num=len(data), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=target_n, endpoint=False)
        data = np.interp(x_new, x_old, data).astype(np.float32)
        sr = target_sr
    return data.astype(np.float32), sr


def decode_wav_bytes(data: bytes, target_sr: int = 16000) -> tuple[np.ndarray, int]:
    import io
    import tempfile

    # wave module needs a file-like with seek
    bio = io.BytesIO(data)
    try:
        with wave.open(bio, "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sr = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
    except wave.Error:
        # Fallback: write temp and let ffmpeg convert via subprocess if needed
        import subprocess
        import tempfile as _tempfile

        tmp_path = Path(_tempfile.mkstemp(suffix=".bin")[1])
        out_path = Path(_tempfile.mkstemp(suffix=".wav")[1])
        try:
            tmp_path.write_bytes(data)
            subprocess.check_call(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(tmp_path),
                    "-ac",
                    "1",
                    "-ar",
                    str(target_sr),
                    "-f",
                    "wav",
                    str(out_path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return read_wav_mono_16k(out_path, target_sr=target_sr)
        finally:
            tmp_path.unlink(missing_ok=True)
            out_path.unlink(missing_ok=True)

    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if sr != target_sr and len(samples) > 1:
        duration = len(samples) / float(sr)
        target_n = max(1, int(round(duration * target_sr)))
        x_old = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=target_n, endpoint=False)
        samples = np.interp(x_new, x_old, samples).astype(np.float32)
        sr = target_sr
    return samples.astype(np.float32), sr


def energy_vad_segments(
    samples: np.ndarray,
    sample_rate: int,
    *,
    frame_ms: int = 30,
    hop_ms: int = 10,
    min_segment_ms: int = 400,
    silence_ms: int = 200,
    energy_ratio: float = 0.35,
) -> list[tuple[int, int]]:
    """Simple energy VAD → list of (start_sample, end_sample) speech regions."""
    if len(samples) == 0:
        return []
    frame = max(1, int(sample_rate * frame_ms / 1000))
    hop = max(1, int(sample_rate * hop_ms / 1000))
    energies: list[float] = []
    for i in range(0, max(1, len(samples) - frame + 1), hop):
        chunk = samples[i : i + frame]
        energies.append(float(np.sqrt(np.mean(chunk * chunk) + 1e-12)))
    if not energies:
        return [(0, len(samples))]
    peak = max(energies) or 1.0
    thr = peak * energy_ratio
    speech = [e >= thr for e in energies]
    # Merge into segments with silence tolerance
    silence_frames = max(1, int(silence_ms / hop_ms))
    min_frames = max(1, int(min_segment_ms / hop_ms))
    segments: list[tuple[int, int]] = []
    start: int | None = None
    silent_run = 0
    for idx, is_speech in enumerate(speech):
        if is_speech:
            if start is None:
                start = idx
            silent_run = 0
        elif start is not None:
            silent_run += 1
            if silent_run >= silence_frames:
                end = idx - silent_run + 1
                if end - start >= min_frames:
                    segments.append((start * hop, min(len(samples), end * hop + frame)))
                start = None
                silent_run = 0
    if start is not None:
        end = len(speech)
        if end - start >= min_frames:
            segments.append((start * hop, len(samples)))
    if not segments and float(np.sqrt(np.mean(samples * samples) + 1e-12)) > 1e-4:
        # Whole clip as one segment if energy exists but VAD was too strict
        if len(samples) >= int(sample_rate * min_segment_ms / 1000):
            return [(0, len(samples))]
    return segments


class EmbeddingBackend(Protocol):
    name: str

    def embed(self, samples: np.ndarray, sample_rate: int) -> np.ndarray: ...


class HashEmbeddingBackend:
    """Deterministic non-biometric backend for tests and dry-run bring-up.

    NOT a speaker verifier. Produces stable vectors from audio content so the
    gate pipeline (segment → score → threshold) can be tested without FunASR.
    """

    name = "hash_dev"
    dim = 192

    def embed(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        # Trim near-silence so VAD edge jitter does not dominate this toy backend.
        energy = np.abs(samples)
        thr = max(1e-3, float(np.max(energy)) * 0.05) if len(energy) else 1e-3
        idx = np.where(energy >= thr)[0]
        window = samples[idx[0] : idx[-1] + 1] if len(idx) else samples
        window = window[: min(len(window), sample_rate * 2)]
        if len(window) < 64:
            window = np.pad(window, (0, 64 - len(window)))

        # Dry-run identity proxy: dominant frequency + spectral centroid.
        # Real deployments must use FunASR CAM++; this only exercises the gate.
        tapered = window * np.hanning(len(window))
        spec = np.abs(np.fft.rfft(tapered)) + 1e-12
        freqs = np.fft.rfftfreq(len(window), d=1.0 / float(sample_rate))
        peak_f = float(freqs[int(np.argmax(spec))])
        centroid = float(np.sum(freqs * spec) / float(np.sum(spec)))

        vec = np.zeros(self.dim, dtype=np.float64)
        peak_bin = int(np.clip((peak_f / 4000.0) * (self.dim - 1), 0, self.dim - 1))
        cent_bin = int(np.clip((centroid / 4000.0) * (self.dim - 1), 0, self.dim - 1))
        vec[peak_bin] = 1.0
        vec[(peak_bin + 1) % self.dim] = 0.6
        vec[(peak_bin - 1) % self.dim] = 0.6
        vec[cent_bin] += 0.8
        # Stable micro-texture from rounded peak Hz so identical tones match.
        rng = np.random.default_rng(int(round(peak_f * 10.0)) & 0xFFFFFFFF)
        vec = vec + 0.04 * rng.standard_normal(self.dim)
        return l2_normalize(vec).astype(np.float64)


class FunASREmbeddingBackend:
    """CAM++ / FunASR speaker embedding backend (optional dependency)."""

    name = "funasr_campplus"

    def __init__(self, model_id: str) -> None:
        from funasr import AutoModel  # type: ignore

        self.model_id = model_id
        self._model = AutoModel(
            model=model_id,
            device="cpu",
            disable_update=True,
            vad_model=None,
            punc_model=None,
            spk_model=None,
        )

    def embed(self, samples: np.ndarray, sample_rate: int) -> np.ndarray:
        result = self._model.generate(input=samples, fs=sample_rate, batch_size=1)
        if not result:
            raise RuntimeError("FunASR returned empty embedding result")
        vector = result[0]["spk_embedding"]
        arr = np.asarray(vector)
        if hasattr(arr, "detach"):
            arr = arr.detach().cpu().numpy()
        arr = np.asarray(arr, dtype=np.float64).reshape(-1)
        if arr.size == 0:
            raise RuntimeError("FunASR returned empty spk_embedding")
        return l2_normalize(arr)


def select_backend(cfg: dict, *, force: str | None = None) -> EmbeddingBackend:
    choice = (force or cfg.get("backend") or "auto").lower()
    allow_dev = os.environ.get("AARON_VOICE_ALLOW_DEV_BACKEND", "").strip() in {
        "1",
        "true",
        "yes",
    }
    if choice in {"hash", "hash_dev", "dev"}:
        if not allow_dev and not os.environ.get("AARON_VOICE_TEST"):
            raise RuntimeError(
                "hash_dev backend refused without AARON_VOICE_ALLOW_DEV_BACKEND=1 "
                "(not for production Aaron identity)"
            )
        return HashEmbeddingBackend()

    if choice in {"funasr", "funasr_campplus", "auto"}:
        model = cfg.get("funasr_model") or "iic/speech_campplus_sv_zh-cn_16k-common"
        try:
            return FunASREmbeddingBackend(model)
        except Exception as exc:
            if choice != "auto":
                raise RuntimeError(f"FunASR backend unavailable: {exc}") from exc
            if allow_dev or os.environ.get("AARON_VOICE_TEST"):
                return HashEmbeddingBackend()
            raise RuntimeError(
                "FunASR not installed; install funasr for production Aaron voice gate, "
                "or set AARON_VOICE_ALLOW_DEV_BACKEND=1 for dry-run only"
            ) from exc

    raise ValueError(f"Unknown backend: {choice}")


@dataclass
class SegmentScore:
    start_ms: int
    end_ms: int
    score: float
    is_aaron: bool


@dataclass
class GateResult:
    accepted: bool
    aaron_score: float
    is_aaron: bool
    reason: str
    backend: str
    enrolled: bool
    threshold: float
    segments: list[SegmentScore] = field(default_factory=list)
    aaron_speech_ms: int = 0
    device_id: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class VoiceStore:
    path: Path
    subject: str = "Aaron"
    version: int = 1
    backend: str = ""
    model_id: str = ""
    threshold: float = 0.85
    updated_at: str = ""
    templates: list[dict] = field(default_factory=list)
    centroid: list[float] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "VoiceStore":
        if not path.exists():
            return cls(path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            path=path,
            subject=data.get("subject", "Aaron"),
            version=int(data.get("version", 1)),
            backend=data.get("backend", ""),
            model_id=data.get("model_id", ""),
            threshold=float(data.get("threshold", 0.85)),
            updated_at=data.get("updated_at", ""),
            templates=list(data.get("templates") or []),
            centroid=list(data.get("centroid") or []),
        )

    @property
    def enrolled(self) -> bool:
        return len(self.templates) > 0 and bool(self.centroid)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.updated_at = utc_now()
        payload = {
            "subject": self.subject,
            "version": self.version,
            "backend": self.backend,
            "model_id": self.model_id,
            "threshold": self.threshold,
            "updated_at": self.updated_at,
            "templates": self.templates,
            "centroid": self.centroid,
            "counts": {"templates": len(self.templates)},
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def recompute_centroid(self) -> None:
        if not self.templates:
            self.centroid = []
            return
        mat = np.stack(
            [l2_normalize(np.asarray(t["embedding"], dtype=np.float64)) for t in self.templates]
        )
        self.centroid = l2_normalize(mat.mean(axis=0)).tolist()


class AaronVoiceGate:
    """Enroll + verify Aaron; drop non-Aaron speech segments."""

    def __init__(
        self,
        cfg: dict | None = None,
        *,
        backend: EmbeddingBackend | None = None,
        store: VoiceStore | None = None,
    ) -> None:
        self.cfg = cfg or load_config()
        self.threshold = float(self.cfg.get("threshold", 0.85))
        self.min_segment_ms = int(self.cfg.get("min_segment_ms", 400))
        self.min_aaron_speech_ms = int(self.cfg.get("min_aaron_speech_ms", 300))
        self.sample_rate = int(self.cfg.get("sample_rate", 16000))
        self.fail_closed = bool(self.cfg.get("fail_closed", True))
        store_path = resolve_path(self.cfg.get("store_path"))
        self.store = store or VoiceStore.load(store_path)
        if backend is not None:
            self.backend = backend
        else:
            # Lazy: only construct when first needed if store already has backend note
            self._backend: EmbeddingBackend | None = None
            self.backend = None  # type: ignore

    def _ensure_backend(self) -> EmbeddingBackend:
        if getattr(self, "backend", None) is not None and self.backend is not None:
            return self.backend
        if getattr(self, "_backend", None) is not None:
            self.backend = self._backend
            return self.backend
        self._backend = select_backend(self.cfg)
        self.backend = self._backend
        return self.backend

    def status(self) -> dict:
        self.reload_store()
        enrolled = self.store.enrolled
        return {
            "enabled": bool(self.cfg.get("enabled", True)),
            "enrolled": enrolled,
            "templates": len(self.store.templates),
            "threshold": self.threshold,
            "backend_configured": self.cfg.get("backend", "auto"),
            "backend_store": self.store.backend or None,
            "fail_closed": self.fail_closed,
            "store_path": str(self.store.path),
            "converse_require_voice_match_for_mic": bool(
                self.cfg.get("converse_require_voice_match_for_mic", True)
            ),
            "ready_for_production": enrolled and self.store.backend.startswith("funasr"),
        }

    def reload_store(self) -> None:
        """Pick up new enrollments written by the CLI without restarting."""
        path = self.store.path
        self.store = VoiceStore.load(path)

    def enroll_file(
        self,
        wav_path: Path,
        *,
        template_id: str | None = None,
        replace: bool = False,
    ) -> dict:
        samples, sr = read_wav_mono_16k(wav_path, target_sr=self.sample_rate)
        return self.enroll_samples(
            samples,
            sr,
            source=str(wav_path),
            template_id=template_id,
            replace=replace,
        )

    def enroll_samples(
        self,
        samples: np.ndarray,
        sample_rate: int,
        *,
        source: str = "",
        template_id: str | None = None,
        replace: bool = False,
    ) -> dict:
        backend = self._ensure_backend()
        if self.store.enrolled and self.store.backend and self.store.backend != backend.name:
            raise RuntimeError(
                f"Store backend {self.store.backend} != live backend {backend.name}; "
                "re-enroll with --replace after switching backends"
            )
        vec = backend.embed(samples, sample_rate)
        tid = template_id or f"aaron-voice-{len(self.store.templates) + 1:02d}"
        source_hash = hashlib.sha256(
            (source or samples.tobytes()[:4096]).encode("utf-8", errors="ignore")
            if isinstance(source, str)
            else samples.tobytes()[:4096]
        ).hexdigest()[:16]
        if isinstance(source, str) and source:
            try:
                source_hash = hashlib.sha256(Path(source).read_bytes()).hexdigest()[:16]
            except OSError:
                pass
        entry = {
            "id": tid,
            "source": source,
            "source_hash": source_hash,
            "embedding": l2_normalize(vec).tolist(),
            "duration_s": round(len(samples) / float(sample_rate), 3),
            "created_at": utc_now(),
            "dim": int(vec.size),
        }
        if replace:
            self.store.templates = [entry]
        else:
            # Replace same id if re-enrolling
            self.store.templates = [t for t in self.store.templates if t.get("id") != tid]
            self.store.templates.append(entry)
        self.store.backend = backend.name
        self.store.model_id = getattr(backend, "model_id", backend.name)
        self.store.threshold = self.threshold
        self.store.recompute_centroid()
        self.store.save()
        return {
            "ok": True,
            "template_id": tid,
            "templates": len(self.store.templates),
            "backend": backend.name,
            "store_path": str(self.store.path),
        }

    def score_embedding(self, vec: np.ndarray) -> float:
        if not self.store.enrolled:
            return 0.0
        scores = [
            cosine_similarity(vec, np.asarray(t["embedding"], dtype=np.float64))
            for t in self.store.templates
        ]
        if self.store.centroid:
            scores.append(cosine_similarity(vec, np.asarray(self.store.centroid, dtype=np.float64)))
        return float(max(scores)) if scores else 0.0

    def gate_samples(
        self,
        samples: np.ndarray,
        sample_rate: int | None = None,
        *,
        device_id: str = "",
    ) -> GateResult:
        sr = sample_rate or self.sample_rate
        if not bool(self.cfg.get("enabled", True)):
            return GateResult(
                accepted=True,
                aaron_score=1.0,
                is_aaron=True,
                reason="gate_disabled",
                backend="none",
                enrolled=self.store.enrolled,
                threshold=self.threshold,
                device_id=device_id,
            )
        self.reload_store()
        if not self.store.enrolled:
            return GateResult(
                accepted=False if self.fail_closed else True,
                aaron_score=0.0,
                is_aaron=False,
                reason="not_enrolled",
                backend=self.store.backend or "none",
                enrolled=False,
                threshold=self.threshold,
                device_id=device_id,
            )
        try:
            backend = self._ensure_backend()
        except Exception as exc:
            return GateResult(
                accepted=False if self.fail_closed else True,
                aaron_score=0.0,
                is_aaron=False,
                reason=f"backend_unavailable:{exc}",
                backend="unavailable",
                enrolled=True,
                threshold=self.threshold,
                device_id=device_id,
            )
        if self.store.backend and self.store.backend != backend.name:
            return GateResult(
                accepted=False,
                aaron_score=0.0,
                is_aaron=False,
                reason=f"backend_mismatch:store={self.store.backend},live={backend.name}",
                backend=backend.name,
                enrolled=True,
                threshold=self.threshold,
                device_id=device_id,
            )

        segments = energy_vad_segments(
            samples,
            sr,
            min_segment_ms=self.min_segment_ms,
        )
        if not segments:
            return GateResult(
                accepted=False,
                aaron_score=0.0,
                is_aaron=False,
                reason="no_speech",
                backend=backend.name,
                enrolled=True,
                threshold=self.threshold,
                device_id=device_id,
            )

        scored: list[SegmentScore] = []
        aaron_ms = 0
        best = 0.0
        for start, end in segments:
            chunk = samples[start:end]
            if len(chunk) < int(sr * self.min_segment_ms / 1000):
                continue
            vec = backend.embed(chunk, sr)
            score = self.score_embedding(vec)
            is_aaron = score >= self.threshold
            start_ms = int(1000 * start / sr)
            end_ms = int(1000 * end / sr)
            scored.append(
                SegmentScore(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    score=round(score, 4),
                    is_aaron=is_aaron,
                )
            )
            best = max(best, score)
            if is_aaron:
                aaron_ms += end_ms - start_ms

        is_aaron = best >= self.threshold and aaron_ms >= self.min_aaron_speech_ms
        if not scored:
            return GateResult(
                accepted=False,
                aaron_score=0.0,
                is_aaron=False,
                reason="segments_too_short",
                backend=backend.name,
                enrolled=True,
                threshold=self.threshold,
                device_id=device_id,
            )
        reason = "aaron_match" if is_aaron else "non_aaron_or_below_threshold"
        if is_aaron and any(not s.is_aaron for s in scored):
            reason = "aaron_match_with_surrounding_dropped"
        return GateResult(
            accepted=is_aaron,
            aaron_score=round(best, 4),
            is_aaron=is_aaron,
            reason=reason,
            backend=backend.name,
            enrolled=True,
            threshold=self.threshold,
            segments=scored,
            aaron_speech_ms=aaron_ms,
            device_id=device_id,
        )

    def gate_wav_bytes(self, data: bytes, *, device_id: str = "") -> GateResult:
        samples, sr = decode_wav_bytes(data, target_sr=self.sample_rate)
        return self.gate_samples(samples, sr, device_id=device_id)

    def gate_wav_file(self, path: Path, *, device_id: str = "") -> GateResult:
        samples, sr = read_wav_mono_16k(path, target_sr=self.sample_rate)
        return self.gate_samples(samples, sr, device_id=device_id)

    def extract_aaron_audio(
        self, samples: np.ndarray, sample_rate: int, result: GateResult
    ) -> np.ndarray | None:
        """Concatenate only Aaron-positive segments for downstream ASR."""
        if not result.segments:
            return None
        parts = []
        for seg in result.segments:
            if not seg.is_aaron:
                continue
            start = int(seg.start_ms * sample_rate / 1000)
            end = int(seg.end_ms * sample_rate / 1000)
            parts.append(samples[start:end])
        if not parts:
            return None
        return np.concatenate(parts)


def update_enroll_index(templates: list[dict]) -> None:
    """Refresh voice refs in identity/aaron/enroll-index.json (no embeddings)."""
    index_path = ROOT / "identity" / "aaron" / "enroll-index.json"
    data = json.loads(index_path.read_text(encoding="utf-8"))
    voices = []
    for t in templates:
        voices.append(
            {
                "id": t.get("id"),
                "source": t.get("source"),
                "source_hash": t.get("source_hash"),
                "duration_s": t.get("duration_s"),
                "created_at": t.get("created_at"),
                "label": "Aaron",
            }
        )
    data["voices"] = voices
    data["updated_at"] = utc_now()
    data["status"] = (
        "face_enrollment_complete_4_photos_voice_enrolled"
        if voices
        else data.get("status", "face_enrollment_complete_4_photos")
    )
    index_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def synthesize_tone(
    seconds: float,
    *,
    sample_rate: int = 16000,
    freq: float = 220.0,
    seed: int = 0,
) -> np.ndarray:
    """Test helper: unique-ish tone+noise clip (hash backend separates by content)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sample_rate), dtype=np.float64) / sample_rate
    sig = 0.4 * np.sin(2 * math.pi * freq * t)
    sig += 0.05 * rng.standard_normal(len(t))
    return sig.astype(np.float32)
