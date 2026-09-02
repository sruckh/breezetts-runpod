# Goal: Scaffold ICM Workspace for BreezeTTS RunPod Serverless with S3 Presigned URL Delivery

## Overview & Objective
Scaffold and fully populate a 5-layer ICM (Interpretable Context Methodology) pipeline workspace (`.icm/`) dedicated to building, optimizing, containerizing, and verifying an end-to-end **BreezeTTS RunPod Serverless Worker**. The worker features dual audio delivery: Backblaze B2 S3 presigned URL generation (primary) and inline base64 WAV payload delivery (fallback).

## Key Architectural & Feature Requirements
1. **BreezeTTS Multi-Mode Synthesis:**
   - **Voice Clone Mode:** Zero-shot speaker cloning via reference audio (base64) + exact reference transcript text.
   - **Voice Design Mode:** Reference-free voice synthesis via natural-language text instruction + CFG scale tuning (`--cfg-scale 4`).
   - **Voice Direction Mode:** Reference speaker identity preserved while steering tone, emotion, pace, and delivery via instructions + CFG scale.
   - **Inline Vocal Events:** English parentheses `(laugh)`, `(cough)`, `(clears throat)`, `(sigh)` and Chinese square brackets `[笑]`, `[咳嗽]`, `[清嗓子]`, `[叹气]`.
   - **Fast Inference Optimizations:** Support for eager mode (~7.7 GiB VRAM) and `--fast-all` modular CUDA Graphs (~14.4 GiB VRAM).
2. **Audio Delivery & Object Storage (Backblaze B2 S3):**
   - Implemented in `worker/storage.py` with `AUDIO_DELIVERY = auto | s3 | base64` (default `auto` -> uses S3 if credentials exist, else base64).
   - Response includes `delivery: "s3"`, `audio_url` (presigned GET URL, 24h default), `bucket`, `key`, `size_bytes`, `url_expires_in`, `url_expires_at`.
   - Backblaze B2 fix: `botocore.config.Config(request_checksum_calculation="when_required", response_checksum_validation="when_required")` to avoid B2 `InvalidArgument: Unsupported header` errors.
   - Object key template: `{prefix}{YYYY}/{MM}/{DD}/{sanitized_job_id}-{uuid4}.wav`.
   - Secrets wrapped in `Secret` container to avoid credential leaks in logs/repr.
3. **Input Audio & Payload Limits:**
   - Single-pass base64 decode in `schema_validator.py`.
   - Enforce 4MB per-clip limit (`MAX_REFERENCE_AUDIO_BYTES`) and 6MB total decoded audio limit (`MAX_TOTAL_REFERENCE_AUDIO_BYTES`).
4. **RunPod Serverless Invariants:**
   - Module-scope model bootstrap (never inside job handler).
   - Static scanner compliance (`import runpod` + `runpod.serverless.start(...)`).
   - Dockerfile clean entrypoint: `ENTRYPOINT []` and unbuffered execution `CMD ["python3", "-u", "handler.py"]`.
   - Timeout safety: `RUNPOD_INIT_TIMEOUT=1200`.
   - Volume caching at `/runpod-volume` with `hf_transfer` fallback download.
   - Full crash log dumping to stdout before exit.

---

## 5-Layer ICM Workspace Stages
The workspace at `.icm/` will contain 6 fully-contracted stages:
- **`01-discovery-and-contracts`**: Pin Breeze TTS 2 architecture, upstream APIs, audio format (24kHz mono 16-bit PCM WAV), Backblaze B2 S3 delivery schemas, and RunPod payload limits.
- **`02-schema-and-validation`**: Specify `schema_validator.py` with multi-mode validation, single-pass base64 audio decoding (4MB clip / 6MB total), inline vocal events parsing, and `response_delivery` parameter.
- **`03-engine-and-model-lifecycle`**: Define module-scope model bootstrapping, Hugging Face checkpoint resolution (volume cache + `hf_transfer` fallback), eager vs `--fast-all` CUDA Graph warmup, and diagnostic error trapping.
- **`04-handler-and-storage`**: Implement `handler.py` and `storage.py` with RunPod Serverless lifecycle, S3 presigned URL generation for Backblaze B2, base64 fallback, and crash dumps.
- **`05-container-and-dockerfile`**: Construct `Dockerfile` with `ENTRYPOINT []`, `CMD ["python3", "-u", "handler.py"]`, `RUNPOD_INIT_TIMEOUT=1200`, CUDA sm90/sm80 build configuration, and explicit package pinning (`boto3`, `botocore>=1.36`, `hf_transfer`, `flash-attn`).
- **`06-verification-and-test-suite`**: Define test suite covering all 3 modes, vocal events, S3 presigned URL upload mocking, base64 fallback, payload limit enforcement, and RunPod local mock testing (`--test_input`).

---

## Deterministic Success Criteria
1. Workspace initialized with `python3 /root/.claude/skills/icm/scripts/new .icm --domain "breeze-tts-runpod" --form pipeline`.
2. All 6 stage contracts (`stages/01-discovery-and-contracts/CONTEXT.md` through `stages/06-verification-and-test-suite/CONTEXT.md`) populated with valid Inputs/Process/Outputs tables and audit checks.
3. Stable reference files in `references/` and `_config/` contain the full BreezeTTS specs, Backblaze B2 S3 storage patterns, and RunPod invariants.
4. `python3 /root/.claude/skills/icm/scripts/audit .icm --strict` executes with **exit code 0** (zero warnings or errors).

---

## Command to Execute
```bash
/goal Scaffold a complete 5-layer ICM pipeline workspace at .icm/ for implementing BreezeTTS as a RunPod Serverless worker with Backblaze B2 S3 presigned URL delivery and base64 fallback. The workspace must contain 6 fully-contracted stages (01-discovery-and-contracts, 02-schema-and-validation, 03-engine-and-model-lifecycle, 04-handler-and-storage, 05-container-and-dockerfile, 06-verification-and-test-suite) supporting all BreezeTTS modes (Voice Clone, Voice Design, Voice Direction), inline vocal events, base64 input audio (4MB/6MB bounds), S3 presigned URL audio delivery with B2 botocore checksum fixes, --fast-all acceleration flags, and RunPod blueprint invariants (module-scope bootstrap, ENTRYPOINT [], RUNPOD_INIT_TIMEOUT=1200, unbuffered logs). References in Layer 3 must include full BreezeTTS architecture, S3 storage specifications, and payload contracts. Success condition: python3 /root/.claude/skills/icm/scripts/audit .icm --strict exits 0. Scope: .icm/, _config/, references/, stages/. Write all scratch notes, temporary test scripts, or logs to .goals/ — not the repo root. Stop after 6 tries. If still failing, stop, revert .icm/, and report the failure.
```
