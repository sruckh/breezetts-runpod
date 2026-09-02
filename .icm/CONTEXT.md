# Context — breeze-tts-runpod

> Layer 1 · "Where do I go?"

The flow in one line: _pin the contracts, specify the validator, the engine,
the handler + storage, the container, then prove it all with tests_.

Stable specs live in `references/` (BreezeTTS architecture, B2 S3 storage,
RunPod invariants, payload contracts); rules live in `_config/`.

<!-- icm:sync:begin -->
## Stages
| # | Stage | Job | Output | Status |
|---|---|---|---|---|
| 01 | discovery-and-contracts | Pin Breeze TTS 2 architecture, upstream APIs, audio format, Backblaze B2 S3 delivery schemas, and RunPod payload limits into stable contracts. | `stages/01-discovery-and-contracts/output/` | COMPLETE |
| 02 | schema-and-validation | Specify schema_validator.py: multi-mode validation, single-pass base64 decode with 4MB/6MB bounds, inline vocal events, response_delivery parameter. | `stages/02-schema-and-validation/output/` | COMPLETE |
| 03 | engine-and-model-lifecycle | Define module-scope model bootstrap, Hugging Face checkpoint resolution (volume cache + hf_transfer fallback), eager vs --fast-all CUDA Graph warmup, and diagnostic error trapping. | `stages/03-engine-and-model-lifecycle/output/` | COMPLETE |
| 04 | handler-and-storage | Specify handler.py and storage.py: RunPod serverless lifecycle, Backblaze B2 S3 presigned URL delivery, base64 fallback, and crash dumps. | `stages/04-handler-and-storage/output/` | COMPLETE |
| 05 | container-and-dockerfile | Specify the Dockerfile: ENTRYPOINT [], unbuffered CMD, RUNPOD_INIT_TIMEOUT=1200, CUDA sm90/sm80 build configuration, and explicit package pinning. | `stages/05-container-and-dockerfile/output/` | COMPLETE |
| 06 | verification-and-test-suite | Define the test suite: all 3 modes, vocal events, S3 presigned URL upload mocking, base64 fallback, payload limit enforcement, and RunPod local mock testing. | `stages/06-verification-and-test-suite/output/` | COMPLETE |
<!-- icm:sync:end -->

## Factory / product
- **Factory** (stable every run): `_config/`, `shared/`
- **Product** (new every run): each `stages/NN-*/output/`

Status is whatever exists: a stage is COMPLETE when its `output/` holds a file
other than `.gitkeep`. Nothing moves forward until a person has read the last
output.
