"""Module-scope model bootstrap and synthesis dispatch for Breeze TTS 2.

Spec: .icm/stages/03-engine-and-model-lifecycle/output/engine-and-model-lifecycle.md

Set BREEZE_TEST_MOCK_ENGINE=1 to bootstrap a mock runtime instead of loading
the real model -- used by the CPU-only, network-free test suite.
"""
from __future__ import annotations

import io
import os
import sys
import traceback
import wave
from pathlib import Path

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
    return ckpt_dir.is_dir() and (ckpt_dir / "audio_tokenizer").is_dir()


def resolve_checkpoint() -> Path:
    """/runpod-volume/breeze-tts-2 cache -> hf_transfer download -> plain
    huggingface_hub fallback."""
    if _checkpoint_is_complete(CHECKPOINT_DIR):
        return CHECKPOINT_DIR

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


_TEMPLATE_BY_HAS_REFERENCE = {True: "ref_edit_tata", False: "tts_instruction"}


def synthesize(request) -> bytes:
    """request: schema_validator.NormalizedRequest -> WAV bytes, 24 kHz mono
    16-bit PCM. Reads the module-level warm runtime only; never re-bootstraps."""
    if _MOCK_MODE:
        return _silence_wav(seconds=0.1)

    from breeze_infer.templates import get_template, prepare_inputs

    has_reference = bool(request.reference_audio_bytes)
    template_name = _TEMPLATE_BY_HAS_REFERENCE[has_reference]

    job = {
        "id": "job",
        "text": request.text,
        "instruction": request.instruct or "Speak clearly and naturally.",
        "speaker": "S0",
    }
    if has_reference:
        job["ref_audio_bytes"] = request.reference_audio_bytes[0]
        job["ref_text"] = request.reference_text

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
