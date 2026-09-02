"""RunPod serverless handler for the BreezeTTS worker.

Spec: .icm/stages/04-handler-and-storage/output/handler-and-storage.md
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import traceback

import runpod

import engine
import storage
from schema_validator import ValidationError, validate

SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2  # 16-bit mono PCM


def _log_system_info() -> None:
    """Print system diagnostics on worker startup (CUDA, PyTorch, FFmpeg, Flash-Attn)."""
    print("=== BreezeTTS Worker System Diagnostics ===", flush=True)
    print(f"Python: {sys.version.split()[0]} ({sys.executable})", flush=True)

    try:
        import torch

        print(f"PyTorch: {torch.__version__} (compiled CUDA: {torch.version.cuda})", flush=True)
        cuda_avail = torch.cuda.is_available()
        print(f"CUDA Available: {cuda_avail}", flush=True)
        if cuda_avail:
            device_count = torch.cuda.device_count()
            device_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            print(f"GPU: {device_name} (Count: {device_count}, Total VRAM: {vram_gb:.2f} GB)", flush=True)
    except ImportError:
        print("PyTorch: not installed (mock test environment)", flush=True)
    except Exception as exc:
        print(f"PyTorch/CUDA check error: {exc}", flush=True)

    try:
        import flash_attn

        v = getattr(flash_attn, "__version__", "available")
        print(f"Flash Attention: {v}", flush=True)
    except ImportError:
        print("Flash Attention: not installed / CPU mock mode", flush=True)
    except Exception as exc:
        print(f"Flash Attention check error: {exc}", flush=True)

    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        try:
            res = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            first_line = res.stdout.splitlines()[0] if res.stdout else "available"
            print(f"FFmpeg: {first_line}", flush=True)
        except Exception as exc:
            print(f"FFmpeg: {ffmpeg_bin} (version check error: {exc})", flush=True)
    else:
        print("FFmpeg: not found in PATH", flush=True)

    try:
        import runpod

        v = getattr(runpod, "__version__", "available")
        print(f"RunPod SDK: {v}", flush=True)
    except ImportError:
        pass

    delivery_mode = os.environ.get("AUDIO_DELIVERY", "base64")
    b2_bucket = os.environ.get("B2_BUCKET", "not configured")
    hf_home = os.environ.get("HF_HOME", "/runpod-volume/hf-cache")
    hf_transfer = os.environ.get("HF_HUB_ENABLE_HF_TRANSFER", "0")
    print(f"Default Delivery: {delivery_mode} (B2 Bucket: {b2_bucket})", flush=True)
    print(f"HF_HOME: {hf_home} (HF_HUB_ENABLE_HF_TRANSFER: {hf_transfer})", flush=True)
    print(f"RUNPOD_LOG_LEVEL: {os.environ.get('RUNPOD_LOG_LEVEL', 'INFO')}", flush=True)
    print("===========================================", flush=True)


def _crash_dump(context: dict) -> None:
    """Full traceback + job context to stdout before returning a structured
    error. Never includes reference-audio bytes, reference_text, or any
    credential material."""
    print("=== BreezeTTS worker crash dump ===", file=sys.stdout)
    for key, value in context.items():
        print(f"{key}: {value}", file=sys.stdout)
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()


def _synthesis_metadata(normalized_request, size_bytes: int) -> dict:
    return {
        "mode": normalized_request.mode,
        "cfg_scale": normalized_request.cfg_scale,
        "sample_rate": SAMPLE_RATE,
        "duration_seconds": size_bytes / (SAMPLE_RATE * BYTES_PER_SAMPLE),
    }


def handler(job):
    job_id = job.get("id", "unknown")
    job_input = job.get("input", {})

    try:
        normalized_request = validate(job_input)
    except ValidationError as exc:
        return exc.to_dict()

    try:
        wav_bytes = engine.synthesize(normalized_request)
    except Exception:
        _crash_dump(
            {
                "job_id": job_id,
                "mode": normalized_request.mode,
                "reference_audio_present": bool(job_input.get("reference_audio")),
            }
        )
        return {"error": {"code": "synthesis_failed", "message": "synthesis failed"}}

    try:
        delivery = storage.deliver(wav_bytes, job_id, normalized_request.response_delivery)
    except storage.DeliveryError as exc:
        _crash_dump(
            {
                "job_id": job_id,
                "mode": normalized_request.mode,
                "reference_audio_present": bool(job_input.get("reference_audio")),
            }
        )
        return exc.to_dict()
    except Exception:
        _crash_dump(
            {
                "job_id": job_id,
                "mode": normalized_request.mode,
                "reference_audio_present": bool(job_input.get("reference_audio")),
            }
        )
        return {"error": {"code": "delivery_failed", "message": "delivery failed"}}

    metadata = _synthesis_metadata(normalized_request, delivery["size_bytes"])
    return {**delivery, **metadata}


if __name__ == "__main__":
    _log_system_info()
    runpod.serverless.start(
        {
            "handler": handler,
            "rp_log_level": os.environ.get("RUNPOD_LOG_LEVEL", "INFO"),
        }
    )
