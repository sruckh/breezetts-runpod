import base64

import pytest

from schema_validator import (
    MAX_REFERENCE_AUDIO_BYTES,
    MAX_TOTAL_REFERENCE_AUDIO_BYTES,
    ValidationError,
    validate,
)

VOCAL_EVENTS = [
    "(laugh)", "(cough)", "(clears throat)", "(sigh)",
    "[笑]", "[咳嗽]", "[清嗓子]", "[叹气]",
]


def _b64(n_bytes: int) -> str:
    return base64.b64encode(b"\x00" * n_bytes).decode("ascii")


def test_validate_clone_golden():
    req = validate({
        "text": "hello",
        "reference_audio": _b64(100),
        "reference_text": "hello reference transcript",
    })
    assert req.mode == "clone"
    assert req.reference_audio_bytes == [b"\x00" * 100]
    assert req.cfg_scale == 4.0


def test_validate_design_golden():
    req = validate({"text": "hello", "instruct": "a calm voice"})
    assert req.mode == "design"
    assert req.reference_audio_bytes == []
    assert req.cfg_scale == 4.0


def test_validate_direction_golden():
    req = validate({
        "text": "hello",
        "reference_audio": _b64(100),
        "reference_text": "transcript",
        "instruct": "speak slowly",
    })
    assert req.mode == "direction"


def test_validate_design_rejects_reference_audio():
    with pytest.raises(ValidationError) as exc_info:
        validate({
            "text": "hello",
            "mode": "design",
            "instruct": "a calm voice",
            "reference_audio": _b64(10),
        })
    assert exc_info.value.code == "forbidden_field_for_mode"


def test_validate_clone_missing_reference_text():
    with pytest.raises(ValidationError) as exc_info:
        validate({"text": "hello", "reference_audio": _b64(10)})
    assert exc_info.value.code == "missing_required_field"
    assert exc_info.value.field == "reference_text"


def test_validate_mode_inference_no_explicit_mode():
    design = validate({"text": "hi", "instruct": "calm"})
    assert design.mode == "design"

    clone = validate({"text": "hi", "reference_audio": _b64(10), "reference_text": "t"})
    assert clone.mode == "clone"

    direction = validate({
        "text": "hi", "reference_audio": _b64(10), "reference_text": "t", "instruct": "calm",
    })
    assert direction.mode == "direction"


@pytest.mark.parametrize("cue", VOCAL_EVENTS)
def test_vocal_events_passthrough(cue):
    text = f"hello {cue} world"
    req = validate({"text": text, "instruct": "calm"})
    assert cue in req.text
    assert req.text == text


def test_reference_audio_exactly_4mb_accepted():
    req = validate({
        "text": "hi",
        "reference_audio": _b64(MAX_REFERENCE_AUDIO_BYTES),
        "reference_text": "t",
    })
    assert len(req.reference_audio_bytes[0]) == MAX_REFERENCE_AUDIO_BYTES


def test_reference_audio_4mb_plus_one_byte_rejected():
    with pytest.raises(ValidationError) as exc_info:
        validate({
            "text": "hi",
            "reference_audio": _b64(MAX_REFERENCE_AUDIO_BYTES + 1),
            "reference_text": "t",
        })
    assert exc_info.value.code == "reference_audio_too_large"


def test_reference_audio_total_exactly_6mb_accepted():
    clip_size = MAX_TOTAL_REFERENCE_AUDIO_BYTES // 2
    req = validate({
        "text": "hi",
        "reference_audio": [_b64(clip_size), _b64(clip_size)],
        "reference_text": "t",
    })
    total = sum(len(c) for c in req.reference_audio_bytes)
    assert total == MAX_TOTAL_REFERENCE_AUDIO_BYTES


def test_reference_audio_total_6mb_plus_one_byte_rejected():
    clip_size = MAX_TOTAL_REFERENCE_AUDIO_BYTES // 2
    with pytest.raises(ValidationError) as exc_info:
        validate({
            "text": "hi",
            "reference_audio": [_b64(clip_size), _b64(clip_size + 1)],
            "reference_text": "t",
        })
    assert exc_info.value.code == "reference_audio_total_too_large"


def test_limits_apply_to_decoded_not_base64_length():
    # Base64-encoded length of a 4 MB clip is ~5.33 MB (> 4 MB), but the
    # decoded length is exactly 4 MB -- must be accepted.
    clip = _b64(MAX_REFERENCE_AUDIO_BYTES)
    assert len(clip) > MAX_REFERENCE_AUDIO_BYTES
    req = validate({"text": "hi", "reference_audio": clip, "reference_text": "t"})
    assert len(req.reference_audio_bytes[0]) == MAX_REFERENCE_AUDIO_BYTES


def test_response_delivery_default_and_enum():
    req = validate({"text": "hi", "instruct": "calm"})
    assert req.response_delivery == "auto"

    req = validate({"text": "hi", "instruct": "calm", "response_delivery": "s3"})
    assert req.response_delivery == "s3"

    with pytest.raises(ValidationError) as exc_info:
        validate({"text": "hi", "instruct": "calm", "response_delivery": "ftp"})
    assert exc_info.value.code == "invalid_response_delivery"


def test_error_envelope_has_no_credential_material():
    try:
        validate({"text": "hi", "reference_audio": _b64(10)})
    except ValidationError as exc:
        envelope = exc.to_dict()
        assert "credential" not in str(envelope).lower()
        assert "secret" not in str(envelope).lower()
        assert set(envelope["error"].keys()) <= {"code", "message", "field"}
