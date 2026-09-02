Human check: agent-verified — pending human

# Stage 04 output — handler-and-storage (`handler.py` + `storage.py`, repo root)

## `handler.py` — RunPod serverless lifecycle
Static-scanner-compliant, literal and top-level (per
`../../references/runpod-invariants.md`):
```python
import runpod
# ... module-scope engine bootstrap already ran (stage 03, imported above)

def handler(job):
    ...

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
```
The `if __name__ == "__main__":` guard (upstream RunPod's own quickstart
pattern) keeps the call at true module top-level — not inside `handler(job)`
— while making `handler.py` safely importable by unit tests (importing the
module does not block on `runpod.serverless.start`'s job-polling loop);
running it as a script (`python3 handler.py` / `--test_input`) still
executes the call, satisfying the static scanner's literal-grep check for
both `import runpod` and `runpod.serverless.start(`.
Per-job flow inside `handler(job)`:
1. **Validate** — `job_input = job["input"]`; call
   `schema_validator.validate(job_input)` (stage 02) →
   `NormalizedRequest`. On `ValidationError`, return the structured error
   envelope from stage 02 immediately — no synthesis attempted.
2. **Synthesize** — call `engine.synthesize(normalized_request)` (stage 03)
   → WAV bytes. On exception, dump the full traceback + job context (job
   id, mode, whether reference audio was present — never its bytes or
   `reference_text`) to stdout via `traceback.print_exc()`, then return a
   structured error envelope; the process does not exit.
3. **Deliver** — call `storage.deliver(wav_bytes, job_id, response_delivery)`
   (below) → the `audio` fields (S3 field set or base64 payload). Wrapped in
   the same try/except as step 2: `storage.deliver(...)` raising (e.g. `s3`
   mode failing loudly on missing credentials, per the S3 upload section
   below) is caught here, dumped to stdout the same way as a synthesis
   failure (traceback + job context, no credential material — credentials
   are never unwrapped outside `storage.py` so there is nothing to leak),
   and returned as the same structured error envelope.
4. **Attach synthesis metadata** — `handler.py`, not `storage.py`, builds
   the four-field synthesis-metadata object per
   `../../references/payload-contracts.md#synthesis-metadata-fixed-field-set-always-present-on-success`
   (`mode` and `cfg_scale` from the `NormalizedRequest`, `sample_rate =
   24000`, `duration_seconds = size_bytes / (sample_rate * 2)` using the
   `size_bytes` storage returned) and merges it with step 3's envelope into
   one top-level response dict — this is the full success response
   contract from `../../references/payload-contracts.md`.
5. Return the merged envelope from step 4 (or the error envelope from step
   1, 2, or 3 — validation, synthesis, and delivery failures all
   short-circuit to the identical structured-error return path) as the
   handler's return value.

Local-mock entry point: the file runs unmodified under
`python3 handler.py --test_input '<json>'` (RunPod's local test harness,
confirmed against docs.runpod.io — see
`../../references/runpod-invariants.md`) because `runpod.serverless.start`
handles `--test_input` internally; `handler.py` adds no custom argument
parsing of its own.

## `storage.py` (repo root) — `AUDIO_DELIVERY` resolution
```python
def deliver(wav_bytes: bytes, job_id: str, response_delivery: str) -> dict: ...
```
- Enum: `AUDIO_DELIVERY` env var, `auto | s3 | base64`, default `auto` — this
  is the deployment-level default; `response_delivery` (per-request, from
  stage 02) overrides it for that request when set to `s3` or `base64`
  explicitly, and defers to the env default when `auto`.
- `auto` semantics: prefer S3 when B2 credentials (see Secrets below) are
  present and non-empty; otherwise fall back to base64 — never raises for
  missing credentials under `auto`.
- `s3` semantics: require credentials; raise (surfaced as a structured
  error, not a crash) if missing — "fail loudly," per
  `../../references/s3-storage.md`.
- `base64` semantics: always inline the WAV, regardless of credential
  presence.

### S3 upload + presign (all 7 fields, verbatim)
```python
client = boto3.client(
    "s3",
    endpoint_url=B2_ENDPOINT_URL,
    aws_access_key_id=secret_access_key_id.reveal(),
    aws_secret_access_key=secret_secret_access_key.reveal(),
    config=botocore.config.Config(
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    ),
)
```
The `when_required` config above is the mandatory B2 fix — without it B2
rejects uploads/presigns with `InvalidArgument: Unsupported header`;
requires `botocore>=1.36` (pinned in stage 05). See
`../../references/s3-storage.md`.

1. Build the key from the template
   `{prefix}{YYYY}/{MM}/{DD}/{sanitized_job_id}-{uuid4}.wav` — `prefix` from
   config/env, `YYYY/MM/DD` from the upload time in UTC,
   `sanitized_job_id` = `job_id` with path-unsafe characters stripped,
   `uuid4` freshly generated per upload (guarantees uniqueness on retries).
2. `client.put_object(Bucket=bucket, Key=key, Body=wav_bytes,
   ContentType="audio/wav")`.
3. `url = client.generate_presigned_url("get_object", Params={"Bucket":
   bucket, "Key": key}, ExpiresIn=url_expires_in)` — `url_expires_in`
   defaults to `86400` (24 h).
4. Response object, all 7 fields per
   `../../references/s3-storage.md`:

| Field | Value |
|-------|-------|
| `delivery` | `"s3"` |
| `audio_url` | the presigned GET URL from step 3 |
| `bucket` | B2 bucket name |
| `key` | the object key from step 1 |
| `size_bytes` | `len(wav_bytes)` |
| `url_expires_in` | seconds until expiry (default `86400`) |
| `url_expires_at` | upload time (UTC) + `url_expires_in`, as an absolute
  ISO-8601 timestamp |

### Base64 fallback response
```json
{"delivery": "base64", "audio_base64": "<base64 WAV bytes>", "size_bytes": N}
```
Carries `delivery: "base64"` and the inline payload instead of the S3 field
set, per `../../references/s3-storage.md`.

### Secrets discipline
- B2 access key id and secret access key are read from env vars at module
  scope and immediately wrapped in a `Secret` container (per
  `../../_config/conventions.md`); the container's `__repr__`/`__str__`
  never renders the wrapped value, and code only calls `.reveal()` at the
  point of use (building the `boto3.client(...)` call above) — never stored
  unwrapped, never logged, never included in a crash dump. The B2 endpoint
  URL (`B2_ENDPOINT_URL`) is a hostname, not a credential, and is read and
  used as a plain string — not `Secret`-wrapped, matching the code block
  above (`endpoint_url=B2_ENDPOINT_URL` unwrapped,
  `aws_access_key_id=secret_access_key_id.reveal()` /
  `aws_secret_access_key=secret_secret_access_key.reveal()` wrapped).
- The crash-dump paths in `handler.py` (step 2 above) and any exception
  raised inside `storage.deliver(...)` only interpolate `job_id`, `mode`,
  bucket/key (non-secret), and the exception message/traceback — which by
  construction never contains a `Secret`-wrapped value since credentials are
  only ever passed as `Secret` objects, never as raw strings, into any
  function that could echo them.
