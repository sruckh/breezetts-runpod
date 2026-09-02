import base64

import handler
import storage


def _job(input_payload, job_id="job-1"):
    return {"id": job_id, "input": input_payload}


def test_handler_validation_failure_returns_structured_error():
    result = handler.handler(_job({"text": "hi", "reference_audio": "AAAA"}))
    assert "error" in result
    assert result["error"]["code"] == "missing_required_field"


def test_response_includes_synthesis_metadata(monkeypatch):
    monkeypatch.setattr(
        storage, "deliver",
        lambda wav_bytes, job_id, response_delivery, client=None: {
            "delivery": "base64",
            "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
            "size_bytes": len(wav_bytes),
        },
    )
    monkeypatch.setattr(handler, "storage", storage)

    result = handler.handler(_job({"text": "hi", "instruct": "calm"}))
    assert result["mode"] == "design"
    assert result["cfg_scale"] == 4.0
    assert result["sample_rate"] == 24000
    assert result["duration_seconds"] > 0
    assert result["delivery"] == "base64"


def test_synthesis_crash_dumps_traceback_no_secrets(monkeypatch, capsys):
    def boom(request):
        raise RuntimeError("synthesis exploded")

    monkeypatch.setattr(handler.engine, "synthesize", boom)

    result = handler.handler(_job({
        "text": "hi",
        "reference_audio": "AAAA",
        "reference_text": "super-secret-transcript",
    }))
    assert result["error"]["code"] == "synthesis_failed"

    captured = capsys.readouterr().out
    assert "synthesis exploded" in captured
    assert "Traceback" in captured
    assert "super-secret-transcript" not in captured


def test_delivery_failure_returns_structured_error(monkeypatch):
    def boom(wav_bytes, job_id, response_delivery, client=None):
        raise storage.DeliveryError("s3_credentials_missing", "no creds")

    monkeypatch.setattr(handler, "storage", storage)
    monkeypatch.setattr(storage, "deliver", boom)

    result = handler.handler(_job({"text": "hi", "instruct": "calm"}))
    assert result["error"]["code"] == "s3_credentials_missing"
