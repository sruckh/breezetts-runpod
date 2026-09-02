Human check: agent-verified — pending human

# Stage 01 output — discovery-and-contracts

## Upstream identity
Pinned in full in `../../references/breezetts-architecture.md#upstream-identity`:
model weights at `BreezeBlue/Breeze-TTS-2`, inference code at
`github.com/breezeblue-ai/breeze-tts` (Apache-2.0 source; weights under the
separate BreezeBlue Research and Non-Commercial License — this worker is a
technical integration and does not resolve that licensing question, it is
recorded so the constraint is visible before deployment), the
`qwen_tts.Qwen3TTSTokenizer` audio tokenizer, the
`models.breeze.BreezeForConditionalGeneration` backbone, and the
`breeze_infer.runtime` API (`load_runtime`,
`update_generation_config_for_breeze`, `resolve_device`, `set_all_seeds`).

## Audio format (pinned)
Every delivery path (S3 object or base64 payload) carries exactly:
**24 kHz, mono, 16-bit PCM WAV** — confirmed against the upstream streaming
API response headers (`X-Sample-Rate`, `X-Sample-Format: s16le`) and
`infer.py`'s `sf.SoundFile(..., samplerate=runtime.sample_rate, channels=1,
subtype="PCM_16")`. See `../../references/breezetts-architecture.md`.

## Synthesis modes (closed set of 3)
| Mode | Reference audio | Instruction text | CFG scale |
|------|-----------------|------------------|-----------|
| Voice Clone | required (base64 + exact transcript) | no | default |
| Voice Design | none (reference-free) | required | `--cfg-scale 4` baseline |
| Voice Direction | required (identity preserved) | required | tuned |

Mode inference: reference audio present ⇒ Clone or Direction (instruction
present ⇒ Direction); no reference audio ⇒ Design. See
`../../references/breezetts-architecture.md`.

Upstream CLI confirms the field pairing: `--ref-audio` and `--ref-text`
must be supplied together or both omitted; `--instruction` defaults to `"Speak clearly and naturally."` when
absent; upstream's own `--cfg-scale` default is `1.0` — our contract's `4`
Voice Design baseline is a request-level override this worker applies, not a
change to the upstream default.

## Inline vocal events (both syntaxes pinned)
- English, parentheses: `(laugh)`, `(cough)`, `(clears throat)`, `(sigh)`
- Chinese, square brackets: `[笑]`, `[咳嗽]`, `[清嗓子]`, `[叹气]`

Parsed inline in the synthesis text; never stripped by validation. See
`../../references/breezetts-architecture.md`.

## Inference profiles (VRAM budgets pinned)
| Profile | Flag | VRAM | Min GPU |
|---------|------|------|---------|
| Eager | (default) | ~7.7 GiB | 12 GB |
| Fast | `--fast-all` | ~14.4 GiB | 24 GB |

`--fast-all` also has five independently togglable stage flags (profiling
only): `--[no-]fast-text-encoder`, `--[no-]fast-backbone-prefill`,
`--[no-]fast-backbone-decode`, `--[no-]fast-depth-decoder`,
`--[no-]fast-codec`. `flash-attn` is compiled into the image for the
fast-path CUDA Graph modules above — not the top-level model's
`attn_implementation`, which upstream always sets to `"eager"` in both
profiles (see stage 03's output for the bootstrap call). CUDA build
targets **sm90** (default, Hopper/H100) and **sm80** (A100, via
`FLASH_ATTN_CUDA_ARCHS=80`). See `../../references/breezetts-architecture.md`.

## Payload limits (pinned)
- `MAX_REFERENCE_AUDIO_BYTES = 4 MB` per decoded clip.
- `MAX_TOTAL_REFERENCE_AUDIO_BYTES = 6 MB` total decoded reference audio per
  request. Limits apply to decoded bytes, not base64 length. See
  `../../references/payload-contracts.md`.

## Backblaze B2 S3 delivery (pinned verbatim)
- `AUDIO_DELIVERY = auto | s3 | base64`, default `auto`.
- S3 response fields: `delivery`, `audio_url`, `bucket`, `key`, `size_bytes`,
  `url_expires_in`, `url_expires_at` (default 24 h = 86400 s).
- Key template: `{prefix}{YYYY}/{MM}/{DD}/{sanitized_job_id}-{uuid4}.wav`.
- B2 checksum fix (mandatory, requires `botocore>=1.36`):
  ```python
  botocore.config.Config(
      request_checksum_calculation="when_required",
      response_checksum_validation="when_required",
  )
  ```
  See `../../references/s3-storage.md`.

## RunPod invariants (pinned)
- Module-scope model bootstrap: model loads at import time, never inside the
  job handler.
- Static scanner compliance: literal `import runpod` and a top-level
  `runpod.serverless.start(...)` call.
- `ENTRYPOINT []` in the Dockerfile; `CMD ["python3", "-u", "handler.py"]`
  (unbuffered).
- `RUNPOD_INIT_TIMEOUT=1200` — 20-minute init budget for model download and
  warmup; extends RunPod's platform default (unhealthy after 7 min / 420 s
  cold start). See `../../references/runpod-invariants.md`.
- HF cache on the network volume at `/runpod-volume`.
- Local test harness: `python3 handler.py --test_input '<json>'`.
- Crash dumps: full traceback + context to stdout before exit; never silent.
  See `../../references/runpod-invariants.md`.

## Container build stack
Pinned in full in
`../../references/breezetts-architecture.md#container-build-stack-upstream-dockerdockerfile`:
base image `pytorch/pytorch:2.9.1-cuda12.8-cudnn9-devel`, `flash-attn==2.8.3`
built via `FLASH_ATTN_CUDA_ARCHS` (`90` default, `80` for A100), and
upstream's `requirements.txt` pins (`torch==2.9.1`, `torchaudio==2.9.1`,
`qwen-tts==0.1.1`, `transformers==4.57.3`, `numpy>=2.0`, `soundfile>=0.13`).
This worker adds `runpod`, `boto3`, `botocore>=1.36` (B2 checksum fix floor,
see `../../references/s3-storage.md`), and `hf_transfer` — pinned in stage
05's output.

## Response envelope
Success: audio fields per the S3 section above (or base64 payload) plus
synthesis metadata. Failure: structured error, machine-readable code, human
message, no credential material. See
`../../references/payload-contracts.md`.
