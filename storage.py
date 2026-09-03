"""Audio delivery (Backblaze B2 S3 presigned URL, base64 fallback) for the
BreezeTTS RunPod worker.

Spec: .icm/stages/04-handler-and-storage/output/handler-and-storage.md
"""
from __future__ import annotations

import base64
import os
import re
import uuid
from datetime import datetime, timezone

import boto3
import botocore.config

AUDIO_CONTENT_TYPE = "audio/wav"
DEFAULT_URL_EXPIRES_IN = 86400
_UNSAFE_JOB_ID_CHARS = re.compile(r"[^A-Za-z0-9_-]")


class Secret:
    """Wraps a credential so the raw value never renders via repr/str, so it
    can never leak into a log line, crash dump, or f-string by accident."""

    __slots__ = ("_value",)

    def __init__(self, value: str | None):
        self._value = value

    def reveal(self) -> str | None:
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return "Secret(***)"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return "Secret(***)"


class DeliveryError(Exception):
    """Structured delivery failure (e.g. 's3' mode requested without B2
    credentials). Never carries credential material."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": {"code": self.code, "message": self.message}}


def _env_secret(name: str) -> Secret:
    return Secret(os.environ.get(name) or None)


def _credentials_present() -> bool:
    return bool(
        os.environ.get("B2_ACCESS_KEY_ID")
        and os.environ.get("B2_SECRET_ACCESS_KEY")
        and os.environ.get("B2_ENDPOINT_URL")
        and os.environ.get("B2_BUCKET")
    )


def _sanitize_job_id(job_id: str) -> str:
    return _UNSAFE_JOB_ID_CHARS.sub("_", job_id)


def _build_key(job_id: str) -> str:
    """{prefix}{YYYY}/{MM}/{DD}/{sanitized_job_id}-{uuid4}.wav"""
    prefix = os.environ.get("B2_KEY_PREFIX", "")
    now = datetime.now(timezone.utc)
    sanitized = _sanitize_job_id(job_id)
    return f"{prefix}{now:%Y}/{now:%m}/{now:%d}/{sanitized}-{uuid.uuid4()}.wav"


def _build_client():
    access_key_id = _env_secret("B2_ACCESS_KEY_ID")
    secret_access_key = _env_secret("B2_SECRET_ACCESS_KEY")
    endpoint_url = os.environ.get("B2_ENDPOINT_URL")  # not a credential
    region_name = os.environ.get("B2_REGION")
    if not region_name and endpoint_url:
        match = re.search(r"s3\.([a-z0-9-]+)\.backblazeb2\.com", endpoint_url)
        if match:
            region_name = match.group(1)

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key_id.reveal(),
        aws_secret_access_key=secret_access_key.reveal(),
        region_name=region_name,
        config=botocore.config.Config(
            signature_version="s3v4",
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def _deliver_s3(wav_bytes: bytes, job_id: str, client=None) -> dict:
    bucket = os.environ.get("B2_BUCKET")
    if not bucket or not _credentials_present():
        raise DeliveryError(
            "s3_credentials_missing",
            "S3 delivery requested but B2 credentials are not configured",
        )

    client = client or _build_client()
    key = _build_key(job_id)
    url_expires_in = int(os.environ.get("B2_URL_EXPIRES_IN", DEFAULT_URL_EXPIRES_IN))

    client.put_object(Bucket=bucket, Key=key, Body=wav_bytes, ContentType=AUDIO_CONTENT_TYPE)
    audio_url = client.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=url_expires_in,
    )
    expires_at = datetime.now(timezone.utc).timestamp() + url_expires_in

    return {
        "delivery": "s3",
        "audio_url": audio_url,
        "bucket": bucket,
        "key": key,
        "size_bytes": len(wav_bytes),
        "url_expires_in": url_expires_in,
        "url_expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
    }


def _deliver_base64(wav_bytes: bytes) -> dict:
    return {
        "delivery": "base64",
        "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
        "size_bytes": len(wav_bytes),
    }


def _effective_delivery(response_delivery: str) -> str:
    """Per-request 's3'/'base64' overrides the deployment default; a
    per-request 'auto' defers to the AUDIO_DELIVERY env var (itself
    auto|s3|base64, default 'auto')."""
    if response_delivery in ("s3", "base64"):
        return response_delivery
    return os.environ.get("AUDIO_DELIVERY", "auto")


def deliver(wav_bytes: bytes, job_id: str, response_delivery: str, client=None) -> dict:
    effective = _effective_delivery(response_delivery)
    if effective == "base64":
        return _deliver_base64(wav_bytes)
    if effective == "s3":
        return _deliver_s3(wav_bytes, job_id, client=client)
    # effective == "auto": prefer S3 when credentials exist, else base64.
    if _credentials_present():
        return _deliver_s3(wav_bytes, job_id, client=client)
    return _deliver_base64(wav_bytes)
