"""Module-scope model bootstrap and synthesis dispatch for Breeze TTS 2.

Spec: .icm/stages/03-engine-and-model-lifecycle/output/engine-and-model-lifecycle.md

Set BREEZE_TEST_MOCK_ENGINE=1 to bootstrap a mock runtime instead of loading
the real model -- used by the CPU-only, network-free test suite.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import traceback
import wave
from pathlib import Path
from typing import Any

SAMPLE_RATE = 24000
VOLUME_ROOT = Path(os.environ.get("RUNPOD_VOLUME_PATH", "/runpod-volume"))
CHECKPOINT_DIR = VOLUME_ROOT / "breeze-tts-2"
CHECKPOINT_REPO_ID = "BreezeBlue/Breeze-TTS-2"

_MOCK_MODE = os.environ.get("BREEZE_TEST_MOCK_ENGINE") == "1"
_FAST_ALL = os.environ.get("BREEZE_FAST_ALL", "").strip().lower() in ("1", "true", "yes")


class EngineBootstrapError(RuntimeError):
    """Raised when module-scope bootstrap fails; the process is expected to
    exit after this (a worker that cannot bootstrap must not accept jobs)."""


def _checkpoint_is_complete(ckpt_dir: Path) -> bool:
    """config.json alone proves nothing: it downloads first, so a partial
    (init-timeout-killed) download leaves it behind. Require weights too."""
    if not ckpt_dir.is_dir():
        return False
    has_manifest = (ckpt_dir / "config.json").is_file() or (
        ckpt_dir / "audio_tokenizer"
    ).is_dir()
    return has_manifest and bool(
        any(ckpt_dir.glob("*.safetensors"))
        or (ckpt_dir / "audio_tokenizer" / "model.safetensors").is_file()
    )


def _find_cached_snapshot(hub_dir: Path, repo_id: str) -> Path | None:
    """Check a Hugging Face hub cache directory for a cached model snapshot (RunPod model caching)."""
    if not hub_dir.is_dir():
        return None

    if "/" in repo_id:
        org, name = repo_id.split("/", 1)
        model_dir_name = f"models--{org}--{name}"
    else:
        model_dir_name = f"models--{repo_id}"

    model_root = hub_dir / model_dir_name
    if not model_root.is_dir():
        return None

    snapshots_dir = model_root / "snapshots"
    if not snapshots_dir.is_dir():
        return None

    # 1. Check snapshot hash in refs/main
    refs_main = model_root / "refs" / "main"
    if refs_main.is_file():
        try:
            snapshot_hash = refs_main.read_text().strip()
            candidate = snapshots_dir / snapshot_hash
            if _checkpoint_is_complete(candidate):
                print(f"[ModelCache] Using cached snapshot from refs/main: {candidate}", flush=True)
                return candidate
        except Exception:
            pass

    # 2. Check any available snapshot directory
    try:
        snapshots = [p for p in snapshots_dir.iterdir() if p.is_dir() and _checkpoint_is_complete(p)]
        if snapshots:
            snapshots.sort(reverse=True)
            candidate = snapshots[0]
            print(f"[ModelCache] Using cached snapshot: {candidate}", flush=True)
            return candidate
    except Exception:
        pass

    return None


def resolve_checkpoint() -> Path:
    """Resolve model checkpoint location in priority order:
    1. BREEZE_CHECKPOINT_DIR or MODEL_PATH environment override
    2. RunPod Serverless Model Cache (/runpod-volume/huggingface-cache/hub)
    3. Custom HF_HOME hub cache (/runpod-volume/hf-cache/hub)
    4. Dedicated volume path (/runpod-volume/breeze-tts-2)
    5. User home Hugging Face cache (~/.cache/huggingface/hub)
    6. Download via hf_transfer / huggingface_hub snapshot_download
    """
    # 1. Explicit environment override
    env_override = os.environ.get("BREEZE_CHECKPOINT_DIR") or os.environ.get("MODEL_PATH")
    if env_override:
        override_path = Path(env_override)
        if _checkpoint_is_complete(override_path):
            print(f"[ModelCache] Using environment override path: {override_path}", flush=True)
            return override_path

    # 2. RunPod Official Serverless Model Cache location
    runpod_cache_hub = VOLUME_ROOT / "huggingface-cache" / "hub"
    cached = _find_cached_snapshot(runpod_cache_hub, CHECKPOINT_REPO_ID)
    if cached is not None:
        return cached

    # Also check /runpod-volume/huggingface-cache/hub if VOLUME_ROOT is customized
    std_runpod_cache = Path("/runpod-volume/huggingface-cache/hub")
    if std_runpod_cache != runpod_cache_hub:
        cached = _find_cached_snapshot(std_runpod_cache, CHECKPOINT_REPO_ID)
        if cached is not None:
            return cached

    # 3. Custom HF_HOME cache
    hf_home = Path(os.environ.get("HF_HOME", "/runpod-volume/hf-cache"))
    hf_home_hub = hf_home / "hub"
    cached = _find_cached_snapshot(hf_home_hub, CHECKPOINT_REPO_ID)
    if cached is not None:
        return cached

    # 4. Dedicated volume directory (/runpod-volume/breeze-tts-2)
    if _checkpoint_is_complete(CHECKPOINT_DIR):
        print(f"[ModelCache] Using dedicated volume path: {CHECKPOINT_DIR}", flush=True)
        return CHECKPOINT_DIR

    # 5. User home cache (~/.cache/huggingface/hub)
    user_cache_hub = Path.home() / ".cache" / "huggingface" / "hub"
    cached = _find_cached_snapshot(user_cache_hub, CHECKPOINT_REPO_ID)
    if cached is not None:
        return cached

    # 6. Fallback to downloading
    print(f"[ModelCache] No cached snapshot found, downloading {CHECKPOINT_REPO_ID} to {CHECKPOINT_DIR}...", flush=True)
    from huggingface_hub import snapshot_download

    try:
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
        snapshot_download(repo_id=CHECKPOINT_REPO_ID, local_dir=str(CHECKPOINT_DIR))
    except Exception:
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
        snapshot_download(repo_id=CHECKPOINT_REPO_ID, local_dir=str(CHECKPOINT_DIR))

    return CHECKPOINT_DIR


def _silence_wav(seconds: float) -> bytes:
    n_frames = int(SAMPLE_RATE * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


class _MockRuntime:
    """Test-only stand-in for FastBreezeStreamingRuntime; no GPU/model."""

    sample_rate = SAMPLE_RATE
    fast_enabled = False


_TOKENIZER = None
_MODEL = None
_AUDIO_TOKENIZER = None
_RUNTIME = None


def _bootstrap() -> None:
    global _TOKENIZER, _MODEL, _AUDIO_TOKENIZER, _RUNTIME

    if _MOCK_MODE:
        _RUNTIME = _MockRuntime()
        return

    ckpt_dir = None
    device = None
    try:
        from breeze_infer.runtime import (
            load_runtime,
            resolve_device,
            update_generation_config_for_breeze,
        )
        from models.fast_streaming import FastBreezeStreamingRuntime, FastStreamingConfig
        from models.warmup_profile import load_warmup_profile

        ckpt_dir = resolve_checkpoint()
        device = resolve_device()
        _TOKENIZER, _MODEL, _AUDIO_TOKENIZER = load_runtime(
            ckpt_dir,
            device=device,
            attn_implementation="eager",
        )
        update_generation_config_for_breeze(_MODEL)

        config = FastStreamingConfig(fast_all=_FAST_ALL)
        _RUNTIME = FastBreezeStreamingRuntime(
            _MODEL, _AUDIO_TOKENIZER, config, tokenizer=_TOKENIZER
        )
        if _RUNTIME.fast_enabled:
            fast_config_path = Path(__file__).resolve().parent / "configs" / "fast.json"
            _RUNTIME.warmup_from_profile(load_warmup_profile(fast_config_path))
    except Exception:
        print("=== BreezeTTS engine bootstrap crash dump ===", file=sys.stdout)
        print(f"checkpoint_dir_attempted: {ckpt_dir}", file=sys.stdout)
        print(f"device: {device}", file=sys.stdout)
        print(f"fast_all: {_FAST_ALL}", file=sys.stdout)
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        raise EngineBootstrapError("Breeze TTS 2 engine bootstrap failed") from None


# Module scope: runs once at import time, before handler.py's
# runpod.serverless.start(...) call -- never inside a per-job code path.
_bootstrap()


def _build_job(request) -> tuple[dict[str, Any], Path | None]:
    has_reference = bool(request.reference_audio_bytes)
    job = {
        "id": "job",
        "text": request.text,
        "instruction": request.instruct or "Speak clearly and naturally.",
        "speaker": "S0",
    }
    ref_audio_path: Path | None = None
    if has_reference:
        with tempfile.NamedTemporaryFile(
            prefix="breeze_ref_", suffix=".wav", delete=False
        ) as tmp_file:
            tmp_file.write(request.reference_audio_bytes[0])
            ref_audio_path = Path(tmp_file.name)
        job["ref_audio_path"] = str(ref_audio_path)
        job["ref_text"] = request.reference_text
    return job, ref_audio_path


def synthesize(request) -> bytes:
    """request: schema_validator.NormalizedRequest -> WAV bytes, 24 kHz mono
    16-bit PCM. Reads the module-level warm runtime only; never re-bootstraps."""
    if _MOCK_MODE:
        return _silence_wav(seconds=0.1)

    from breeze_infer.templates import get_template, prepare_inputs

    has_reference = bool(request.reference_audio_bytes)
    template_name = "ref_edit_tata" if has_reference else "tts_instruction"

    ref_audio_path: Path | None = None
    try:
        job, ref_audio_path = _build_job(request)
        inputs = prepare_inputs(
            _TOKENIZER,
            _AUDIO_TOKENIZER,
            _MODEL,
            [job],
            get_template(template_name),
            guidance_scale=request.cfg_scale,
            guidance_scale_ref=None,
            guidance_scale_ins=None,
        )

        import soundfile as sf

        buf = io.BytesIO()
        with sf.SoundFile(
            buf, mode="w", samplerate=_RUNTIME.sample_rate, channels=1,
            subtype="PCM_16", format="WAV",
        ) as out:
            for chunk in _RUNTIME.iter_audio_chunks(inputs, request_id="job"):
                out.write(chunk.audio)
        return buf.getvalue()
    finally:
        if ref_audio_path is not None:
            ref_audio_path.unlink(missing_ok=True)
