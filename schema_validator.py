"""Request validation for the BreezeTTS RunPod worker.

Spec: .icm/stages/02-schema-and-validation/output/schema-and-validation.md
"""
from __future__ import annotations

import base64
from dataclasses import dataclass

MAX_REFERENCE_AUDIO_BYTES = 4 * 1024 * 1024
MAX_TOTAL_REFERENCE_AUDIO_BYTES = 6 * 1024 * 1024

VALID_MODES = ("clone", "design", "direction")
VALID_RESPONSE_DELIVERY = ("auto", "s3", "base64")
DEFAULT_CFG_SCALE = 4.0
DEFAULT_RESPONSE_DELIVERY = "auto"


class ValidationError(Exception):
    """Structured, machine-readable validation failure. Never carries
    credential material or raw payload bytes."""

    code: str
    message: str
    field: str | None

    def __init__(self, code: str, message: str, field: str | None = None):
        self.code = code
        self.message = message
        self.field = field
        super().__init__(message)

    def to_dict(self) -> dict[str, object]:
        error: dict[str, object] = {"code": self.code, "message": self.message}
        if self.field is not None:
            error["field"] = self.field
        return {"error": error}


@dataclass
class NormalizedRequest:
    text: str
    mode: str
    reference_audio_bytes: list[bytes]
    reference_text: str | None
    instruct: str | None
    cfg_scale: float
    response_delivery: str


def _normalize_reference_audio(value) -> list[str]:
    """string or array of strings -> list[str] (0, 1) is a one-element list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        if not all(isinstance(item, str) for item in value):
            raise ValidationError(
                "invalid_base64",
                "reference_audio array must contain only base64 strings",
                field="reference_audio",
            )
        return value
    raise ValidationError(
        "invalid_base64",
        "reference_audio must be a base64 string or an array of base64 strings",
        field="reference_audio",
    )


def _decode_reference_audio(clips: list[str]) -> list[bytes]:
    """Single-pass decode: each clip is base64-decoded exactly once here;
    the resulting bytes are what every downstream consumer reuses."""
    decoded: list[bytes] = []
    total = 0
    for clip in clips:
        try:
            raw = base64.b64decode(clip, validate=True)
        except Exception as exc:
            raise ValidationError(
                "invalid_base64",
                "reference_audio clip is not valid base64",
                field="reference_audio",
            ) from exc
        if len(raw) > MAX_REFERENCE_AUDIO_BYTES:
            raise ValidationError(
                "reference_audio_too_large",
                f"reference_audio clip exceeds {MAX_REFERENCE_AUDIO_BYTES} decoded bytes",
                field="reference_audio",
            )
        total += len(raw)
        if total > MAX_TOTAL_REFERENCE_AUDIO_BYTES:
            raise ValidationError(
                "reference_audio_total_too_large",
                f"total reference_audio exceeds {MAX_TOTAL_REFERENCE_AUDIO_BYTES} decoded bytes",
                field="reference_audio",
            )
        decoded.append(raw)
    return decoded


def _resolve_mode(payload: dict, has_reference_audio: bool, has_instruct: bool) -> str:
    explicit_mode = payload.get("mode")
    if explicit_mode is not None:
        if explicit_mode not in VALID_MODES:
            raise ValidationError(
                "invalid_mode",
                f"mode must be one of {list(VALID_MODES)}",
                field="mode",
            )
        return explicit_mode
    if has_reference_audio and has_instruct:
        return "direction"
    if has_reference_audio:
        return "clone"
    return "design"


def _check_mode_matrix(mode: str, has_reference_audio: bool, reference_text, has_instruct: bool) -> None:
    if mode == "clone":
        if not has_reference_audio:
            raise ValidationError(
                "missing_required_field", "clone mode requires reference_audio", field="reference_audio"
            )
        if not reference_text:
            raise ValidationError(
                "missing_required_field", "clone mode requires reference_text", field="reference_text"
            )
    elif mode == "design":
        if has_reference_audio:
            raise ValidationError(
                "forbidden_field_for_mode", "design mode forbids reference_audio", field="reference_audio"
            )
        if not has_instruct:
            raise ValidationError(
                "missing_required_field", "design mode requires instruct", field="instruct"
            )
    else:  # direction
        if not has_reference_audio:
            raise ValidationError(
                "missing_required_field", "direction mode requires reference_audio", field="reference_audio"
            )
        if not reference_text:
            raise ValidationError(
                "missing_required_field", "direction mode requires reference_text", field="reference_text"
            )
        if not has_instruct:
            raise ValidationError(
                "missing_required_field", "direction mode requires instruct", field="instruct"
            )


def validate(payload: dict) -> NormalizedRequest:
    if not isinstance(payload, dict):
        raise ValidationError("invalid_payload", "payload must be an object")

    text = payload.get("text")
    if not isinstance(text, str) or not text:
        raise ValidationError("missing_required_field", "text is required", field="text")

    reference_text = payload.get("reference_text")
    instruct = payload.get("instruct")

    normalized_clips = _normalize_reference_audio(payload.get("reference_audio"))
    has_reference_audio = len(normalized_clips) > 0
    has_instruct = bool(instruct)

    mode = _resolve_mode(payload, has_reference_audio, has_instruct)
    _check_mode_matrix(mode, has_reference_audio, reference_text, has_instruct)

    reference_audio_bytes = _decode_reference_audio(normalized_clips)

    cfg_scale_raw = payload.get("cfg_scale", DEFAULT_CFG_SCALE)
    try:
        cfg_scale = float(cfg_scale_raw)
    except (TypeError, ValueError):
        raise ValidationError("invalid_cfg_scale", "cfg_scale must be a number", field="cfg_scale")

    response_delivery = payload.get("response_delivery", DEFAULT_RESPONSE_DELIVERY)
    if response_delivery not in VALID_RESPONSE_DELIVERY:
        raise ValidationError(
            "invalid_response_delivery",
            f"response_delivery must be one of {list(VALID_RESPONSE_DELIVERY)}",
            field="response_delivery",
        )

    return NormalizedRequest(
        text=text,
        mode=mode,
        reference_audio_bytes=reference_audio_bytes,
        reference_text=reference_text,
        instruct=instruct,
        cfg_scale=cfg_scale,
        response_delivery=response_delivery,
    )
