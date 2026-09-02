# Reference — Backblaze B2 S3 storage (`storage.py`, repo root)

> Layer 3 · factory. The audio-delivery contract; stage 04 implements to this.

## Delivery modes
`AUDIO_DELIVERY = auto | s3 | base64` (env-configurable, default `auto`).
- `auto`: use S3 when credentials exist, else base64.
- `s3`: require S3; fail loudly if credentials are missing.
- `base64`: always inline the WAV in the response payload.

## S3 response fields (when `delivery == "s3"`)
| Field | Value |
|-------|-------|
| `delivery` | `"s3"` |
| `audio_url` | presigned GET URL |
| `bucket` | B2 bucket name |
| `key` | object key (template below) |
| `size_bytes` | WAV size in bytes |
| `url_expires_in` | seconds until expiry (default 24 h = 86400) |
| `url_expires_at` | absolute expiry timestamp |

Base64 fallback responses carry `delivery: "base64"` and the inline payload
instead of the URL fields.

## Backblaze B2 compatibility fix (mandatory)
```python
botocore.config.Config(
    request_checksum_calculation="when_required",
    response_checksum_validation="when_required",
)
```
Without this, B2 rejects uploads/presigns with
`InvalidArgument: Unsupported header`. Requires `botocore>=1.36` (hard
floor) and `boto3==1.43.86` (current release, PyPI, checked 2026-09-01;
`botocore==1.43.86` satisfies the floor) — pinned in the Dockerfile, stage
05.

## Object key template
```
{prefix}{YYYY}/{MM}/{DD}/{sanitized_job_id}-{uuid4}.wav
```
- `prefix` from env/config, date from upload time (UTC).
- `sanitized_job_id`: job id stripped of path-unsafe characters.
- `uuid4` guarantees uniqueness on retries.

## Secrets discipline
- Credentials are wrapped in a `Secret` container so they never appear in
  logs, tracebacks, or `repr()`.
- Crash dumps (see `runpod-invariants.md`) must not leak credential material.
