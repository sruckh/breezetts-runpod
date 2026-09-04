<p align="center">
  <img src="./assets/readme/hero.svg" width="100%"
       alt="BreezeTTS — a RunPod serverless worker for zero-shot voice cloning, voice design, and voice direction, with Backblaze B2 delivery or base64 fallback">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-FF6A3D?labelColor=0B0D0E" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/platform-runpod%20serverless-FF6A3D?labelColor=0B0D0E" alt="RunPod Serverless">
  <img src="https://img.shields.io/badge/audio-24kHz%20·%2016--bit%20·%20mono-FF6A3D?labelColor=0B0D0E" alt="24kHz 16-bit mono PCM WAV">
  <img src="https://img.shields.io/badge/tests-57%20passing-FF6A3D?labelColor=0B0D0E" alt="57 tests passing">
</p>

A [RunPod serverless](https://docs.runpod.io/serverless/overview) worker that wraps
[Breeze TTS 2](https://github.com/breezeblue-ai/breeze-tts) — a bilingual (EN/ZH), open-weight
text-to-speech model — behind a single JSON handler. Send text and it comes back as a
24 kHz mono 16-bit WAV, delivered either as a Backblaze B2 presigned URL or inline base64.
The model loads once, at process start; every request after that hits an already-warm engine.

## How a request moves through the worker

<p align="center">
  <img src="./assets/readme/architecture.svg" width="100%"
       alt="Request lifecycle: JSON request flows through schema_validator.py, a module-scope Breeze TTS 2 engine that loads once at import time, then storage.py, which delivers via a Backblaze B2 presigned URL or an inline base64 fallback">
</p>

1. **`schema_validator.py`** decodes every `reference_audio` clip exactly once, enforces the
   4 MB per-clip / 6 MB total decoded-bytes limits, resolves the synthesis mode, and returns a
   `NormalizedRequest` or a structured `ValidationError` — no request reaches the model unvalidated.
2. **`engine.py`** bootstraps the model at *import time* — never inside a request — and exposes
   one function, `synthesize(request) -> bytes`. A cold start never happens mid-job.
3. **`storage.py`** uploads the WAV to Backblaze B2 and returns a 24-hour presigned URL, or
   inlines it as base64 when no credentials are configured.
4. **`handler.py`** wires the three together under `runpod.serverless.start(...)`, catches every
   failure mode (validation, synthesis, delivery) as a structured error, and dumps a full
   traceback to stdout on crash — never a credential, never raw reference audio.

## Three ways to give it a voice

| Mode | `mode` | `reference_audio` | `reference_text` | `instruct` | Description |
|---|:---:|:---:|:---:|:---:|---|
| **Voice Clone** | `"clone"` (or omitted) | **Required** (base64 WAV) | **Required** (exact transcript) | Forbidden | Zero-shot clone of the reference speaker |
| **Voice Design** | `"design"` (or omitted) | Forbidden | — | **Required** | Builds a voice from a natural-language description |
| **Voice Direction** | `"direction"` (or omitted) | **Required** (base64 WAV) | **Required** (exact transcript) | **Required** | Clones reference speaker, then steers tone/emotion/pace |

### Mode Inference & Field Requirements

Mode is inferred automatically from the payload fields if you omit the `mode` parameter:
- `reference_audio` + `reference_text` (without `instruct`) &rarr; **`clone`**
- `instruct` alone (without `reference_audio`) &rarr; **`design`**
- `reference_audio` + `reference_text` + `instruct` &rarr; **`direction`**

> **Important for Voice Cloning:**
> 1. `reference_audio`: A base64-encoded audio clip (WAV recommended, mono or stereo, 16-bit or 24-bit PCM; 3–10 seconds is optimal). Maximum 4 MB per clip, 6 MB total decoded.
> 2. `reference_text`: Exact transcript of what the speaker says in `reference_audio`. The model uses this audio-text pair as prompt tokens for speech conditioning.
> 3. `instruct`: Omit `instruct` for pure voice cloning (`clone` mode). If you provide both `reference_audio` and `instruct`, the worker operates in `direction` mode (steered clone).

Inline vocal events pass straight through to the model, untouched, in either language:

```text
EN:  (laugh)  (cough)  (clears throat)  (sigh)
ZH:  [笑]     [咳嗽]    [清嗓子]          [叹气]
```

## Quickstart

### 1. Run with cURL (RunPod Serverless Endpoint)

#### Voice Clone (Zero-Shot Clone from Reference Audio)
Encode your reference audio file (e.g., a 5-second WAV recording) to base64, provide its exact transcript in `reference_text`, and specify your target `text`:

```bash
# Prepare base64 reference audio
REF_B64=$(base64 -w 0 reference.wav)

# Send voice clone request to RunPod
curl -s -X POST "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Hello world! This audio was generated using zero-shot voice cloning.",
      "reference_audio": "'"${REF_B64}"'",
      "reference_text": "This is the exact spoken text in the reference audio clip."
    }
  }' | jq -r '.output.audio_base64' | base64 -d > cloned_output.wav
```

#### Voice Design (Natural Language Voice Prompt)
```bash
curl -s -X POST "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "Hello world! BreezeTTS is now working on RunPod Serverless with GPU acceleration.",
      "instruct": "A calm, natural, and expressive voice."
    }
  }' | jq -r '.output.audio_base64' | base64 -d > designed_output.wav
```

#### Voice Direction (Cloned Voice with Tone/Emotion Steering)
```bash
REF_B64=$(base64 -w 0 reference.wav)

curl -s -X POST "https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/runsync" \
  -H "Authorization: Bearer ${RUNPOD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "text": "(sigh) I cannot believe we finally made it here today.",
      "reference_audio": "'"${REF_B64}"'",
      "reference_text": "This is the exact spoken text in the reference audio clip.",
      "instruct": "Whispering softly, sounding tired but relieved."
    }
  }' | jq -r '.output.audio_base64' | base64 -d > directed_output.wav
```

### 2. Run Locally with RunPod Test Harness

```bash
git clone <this-repo>
cd breezetts
pip install -r requirements.txt
```

Run one job locally with RunPod's own test harness — no deployment needed:

```bash
python3 handler.py --test_input '{
  "input": {
    "text": "(sigh) It is good to hear your voice again.",
    "reference_audio": "<base64 wav>",
    "reference_text": "exact transcript of the reference clip"
  }
}'
```

```json
{ "delivery": "s3", "audio_url": "https://…tts.wav", "bucket": "your-bucket",
  "key": "2026/09/02/local_test-<uuid4>.wav", "size_bytes": 154032,
  "url_expires_in": 86400, "url_expires_at": "2026-09-03T09:38:00+00:00",
  "mode": "clone", "cfg_scale": 4.0, "sample_rate": 24000, "duration_seconds": 3.21 }
```

With no B2 credentials configured, the same call returns `"delivery": "base64"` and an inline
`audio_base64` field instead — same request, no code change.

## Request & response reference

**Request** (`job["input"]`)

| Field | Type | Notes |
|---|---|---|
| `text` | string | synthesis text; may contain inline vocal events |
| `mode` | string | optional `clone` / `design` / `direction`; inferred when omitted |
| `reference_audio` | string or array of strings | base64 clip(s); a single string is treated as one clip |
| `reference_text` | string | exact transcript of the reference; required with `reference_audio` |
| `instruct` | string | natural-language instruction; required for design/direction |
| `cfg_scale` | number | optional, default `4` |
| `response_delivery` | string | optional `auto` / `s3` / `base64`, default `auto` |

**Response** — delivery fields plus synthesis metadata, merged into one object:

| Field | Present when |
|---|---|
| `delivery`, `size_bytes` | always |
| `audio_url`, `bucket`, `key`, `url_expires_in`, `url_expires_at` | `delivery: "s3"` |
| `audio_base64` | `delivery: "base64"` |
| `mode`, `cfg_scale`, `sample_rate`, `duration_seconds` | always, on success |

Failures return `{"error": {"code", "message", "field"}}` — a stable, machine-readable code,
never a stack trace or credential in the payload.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `AUDIO_DELIVERY` | `auto` | `auto` \| `s3` \| `base64` — deployment-level delivery default |
| `B2_ACCESS_KEY_ID`, `B2_SECRET_ACCESS_KEY` | — | wrapped in a `Secret` container; never logged, never in a crash dump |
| `B2_ENDPOINT_URL`, `B2_BUCKET` | — | Backblaze B2 target |
| `B2_REGION` | from endpoint URL | S3 signing region; inferred from `s3.<region>.backblazeb2.com` when unset |
| `B2_KEY_PREFIX` | `""` | prepended to every object key |
| `B2_URL_EXPIRES_IN` | `86400` | presigned URL lifetime, seconds |
| `BREEZE_FAST_ALL` | unset | enable `--fast-all` CUDA Graph warmup (~14.4 GiB VRAM vs ~7.7 GiB eager); request shapes outside the warmup profile run eager instead of failing |
| `RUNPOD_INIT_TIMEOUT` | `1200` | seconds RunPod allows for model download + warmup before marking the worker unhealthy |

Object keys follow `{prefix}{YYYY}/{MM}/{DD}/{sanitized_job_id}-{uuid4}.wav`. The B2 client is
built with `botocore.config.Config(signature_version="s3v4",
request_checksum_calculation="when_required",
response_checksum_validation="when_required")` — without these, B2 rejects uploads
(`InvalidArgument: Unsupported header`) or mis-signs presigned URLs.

## Testing

```bash
BREEZE_TEST_MOCK_ENGINE=1 python3 -m pytest tests/ -q
```

57 tests, all CPU-only and network-free: the model never loads (`BREEZE_TEST_MOCK_ENGINE=1` swaps
in a silent-WAV stub at the same call boundary), and every S3 call is a stubbed or monkeypatched
`boto3` client. Coverage includes golden payloads for all three modes, all 8 vocal cues, the
4 MB / 6 MB boundary (accepted at the bound, rejected one byte over), reference audio temp-file
creation and safe cleanup in the engine, the checkpoint completeness guard (manifest AND
weights), the B2 checksum config and key template, the base64
fallback path, `--test_input` per mode, and every crash-dump path checked for leaked secrets or
reference audio.

## Container

Built on `nvidia/cuda:12.8.0-cudnn-devel-ubuntu24.04` (Python 3.12 in `/opt/venv`) with
PyTorch 2.9.1 (cu128) and `flash-attn==2.8.3` installed as a prebuilt Dao-AILab binary wheel
pinned to torch 2.9 / cu12 — nothing compiles at image build. `ENTRYPOINT []` stays empty so
RunPod's command injection works, and the process runs unbuffered:

```dockerfile
ENTRYPOINT []
CMD ["python3", "-u", "handler.py"]
```

The checkpoint is not baked into the image — at boot `resolve_checkpoint()` checks, in order:
an explicit `BREEZE_CHECKPOINT_DIR`/`MODEL_PATH` override, RunPod's model-cache layout
(`/runpod-volume/huggingface-cache/hub`), `${HF_HOME}/hub`, the dedicated volume directory
(`/runpod-volume/breeze-tts-2`), and the user hub cache. A directory counts as complete only
with a manifest AND weights (`config.json` downloads first, so manifest-only can be a partial
download); otherwise it downloads via `hf_transfer` with a plain `huggingface_hub` fallback,
all inside the `RUNPOD_INIT_TIMEOUT` budget.

## Project layout

```text
schema_validator.py   request validation, single-pass decode, size limits
engine.py              module-scope model bootstrap + synthesis dispatch
storage.py              B2 upload/presign, base64 fallback, Secret wrapping
handler.py              runpod.serverless.start(...) + crash dumps
breeze_infer/           vendored Breeze TTS 2 inference runtime (upstream parity)
models/                 vendored model definitions + fast CUDA-graph streaming runtime
configs/fast.json       warmup profile: the CUDA graph shapes --fast-all captures
Dockerfile              CUDA build, package pins, launch contract
tests/                  57 tests — see Testing above
.icm/                   the full spec this worker was built from, stage by stage
```

Every behavior above is pinned in `.icm/references/` and specified stage by stage in
`.icm/stages/*/output/` before it was implemented — that's the source of truth if this README
and the code ever disagree.

## Model license

Breeze TTS 2's inference code is Apache-2.0; the model weights are released under the
[BreezeBlue Research and Non-Commercial License](https://huggingface.co/BreezeBlue/Breeze-TTS-2) —
commercial use requires authorization from BreezeBlue AI. This repository is a technical
integration and does not change that.
