"""RunPod serverless handler for the BreezeTTS worker.

Spec: .icm/stages/04-handler-and-storage/output/handler-and-storage.md
"""
from __future__ import annotations

import sys
import traceback

import runpod

import engine
import storage
from schema_validator import ValidationError, validate

SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2  # 16-bit mono PCM


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
    runpod.serverless.start({"handler": handler})
