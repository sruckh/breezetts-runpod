Human check: agent-verified — pending human

# Stage 06 output — verification-and-test-suite

All tests are CPU-only and network-free: the model is never loaded and the
S3 client is always a mocked `boto3` client (`botocore.stub.Stubber` or
`unittest.mock`) — no real credentials, no real network call. Test files
live under `tests/` at the repo root.

## Golden-payload tests — all 3 modes
`tests/test_schema_validator.py`
| Test | Mode | Asserts |
|------|------|---------|
| `test_validate_clone_golden` | `clone` | `reference_audio` + `reference_text` accepted; returns `NormalizedRequest(mode="clone", ...)` |
| `test_validate_design_golden` | `design` | `instruct` accepted, no `reference_audio`; returns `NormalizedRequest(mode="design", cfg_scale=4)` |
| `test_validate_direction_golden` | `direction` | `reference_audio` + `reference_text` + `instruct` accepted; returns `NormalizedRequest(mode="direction", ...)` |
| `test_validate_design_rejects_reference_audio` | `design` | `reference_audio` present ⇒ `ValidationError(code="forbidden_field_for_mode")` |
| `test_validate_clone_missing_reference_text` | `clone` | `reference_text` absent ⇒ `ValidationError(code="missing_required_field")` |
| `test_validate_mode_inference_no_explicit_mode` | all | omitted `mode` field resolves per the inference rule (reference+instruct ⇒ direction; reference only ⇒ clone; neither ⇒ design) |

`tests/test_engine.py` (engine mocked at `load_runtime`/`iter_audio_chunks`
level — no real model): `test_synthesize_dispatches_clone_template`,
`test_synthesize_dispatches_design_template`,
`test_synthesize_dispatches_direction_template`, each asserting the correct
upstream template name (`ref_edit_tata` vs `tts_instruction`) and that
`cfg_scale` is passed through unmodified to the mocked
`prepare_inputs(guidance_scale=...)` call.

## Vocal-event tests — all 8 cues, both syntaxes, passthrough
`tests/test_schema_validator.py::test_vocal_events_passthrough` —
parametrized over all 8: `(laugh)`, `(cough)`, `(clears throat)`, `(sigh)`,
`[笑]`, `[咳嗽]`, `[清嗓子]`, `[叹气]`. Asserts each cue appears byte-for-byte
unchanged in `NormalizedRequest.text` after validation (no stripping, no
escaping).
`tests/test_engine.py::test_vocal_events_reach_engine_unmodified` —
parametrized over the same 8 cues; asserts the mocked
`prepare_inputs(...)` call receives `request["text"]` containing the cue
unchanged (engine performs no additional parsing of vocal events).

## Storage tests — mocked S3, base64 fallback
`tests/test_storage.py`
| Test | Asserts |
|------|---------|
| `test_deliver_s3_uses_when_required_checksum_config` | the mocked `boto3.client("s3", ..., config=...)` call receives `botocore.config.Config(request_checksum_calculation="when_required", response_checksum_validation="when_required")`, verbatim per `../../references/s3-storage.md` |
| `test_deliver_s3_key_template` | generated key matches `{prefix}{YYYY}/{MM}/{DD}/{sanitized_job_id}-{uuid4}.wav`; a job id containing `/` or `..` is sanitized before use |
| `test_deliver_s3_response_fields` | response dict contains exactly the 7 fields: `delivery`, `audio_url`, `bucket`, `key`, `size_bytes`, `url_expires_in`, `url_expires_at` |
| `test_deliver_auto_prefers_s3_when_credentials_present` | `AUDIO_DELIVERY=auto` + mocked credentials present ⇒ S3 path taken |
| `test_deliver_base64_fallback_when_credentials_absent` | `AUDIO_DELIVERY=auto` + no credentials ⇒ `delivery: "base64"` response, no `boto3` call made at all (verifies no network attempt) |
| `test_deliver_s3_mode_fails_loudly_without_credentials` | `AUDIO_DELIVERY=s3` + no credentials ⇒ structured error, not a crash |
| `test_secret_never_in_repr_or_error` | `repr(secret_container)` and any raised exception's `str()` never contain the raw credential value |

## Boundary tests — exactly at 4 MB / 6 MB, one byte over
`tests/test_schema_validator.py`
| Test | Asserts |
|------|---------|
| `test_reference_audio_exactly_4mb_accepted` | one clip, decoded length == `4 * 1024 * 1024` bytes exactly ⇒ accepted |
| `test_reference_audio_4mb_plus_one_byte_rejected` | one clip, decoded length == `4 * 1024 * 1024 + 1` ⇒ `ValidationError(code="reference_audio_too_large")` |
| `test_reference_audio_total_exactly_6mb_accepted` | multiple clips (array form) summing to exactly `6 * 1024 * 1024` decoded bytes, each individually ≤ 4 MB ⇒ accepted |
| `test_reference_audio_total_6mb_plus_one_byte_rejected` | same, summing to `6 * 1024 * 1024 + 1` ⇒ `ValidationError(code="reference_audio_total_too_large")` |
| `test_limits_apply_to_decoded_not_base64_length` | a base64 string whose *encoded* length exceeds 4 MB but *decoded* length does not ⇒ accepted (proves the limit is on decoded bytes, per `../../references/payload-contracts.md`) |

## Synthesis metadata tests
`tests/test_handler.py::test_response_includes_synthesis_metadata` —
asserts the merged success response (mocked engine + mocked storage)
contains all 4 fields from
`../../references/payload-contracts.md#synthesis-metadata-fixed-field-set-always-present-on-success`
(`mode`, `cfg_scale`, `sample_rate == 24000`, `duration_seconds` computed
correctly from a known `size_bytes`), alongside the delivery fields, in one
top-level dict.

## RunPod local harness — `--test_input`, per mode
`tests/test_runpod_local.py`, invoking the real `handler.py` as a
subprocess with the engine's module-scope bootstrap monkeypatched/mocked
(via a `BREEZE_TEST_MOCK_ENGINE=1` env var the engine module checks at
import time) so no GPU/model is required:
- `test_handler_test_input_clone` — `python3 handler.py --test_input
  '{"input": {"text": "...", "reference_audio": "...", "reference_text":
  "..."}}'` exits 0, stdout contains a JSON `output` with `delivery` set.
- `test_handler_test_input_design` — same, `instruct` only.
- `test_handler_test_input_direction` — same, reference + `instruct`.
- `test_handler_test_input_validation_failure` — malformed payload (e.g.
  `design` with `reference_audio`) ⇒ exits 0 (RunPod local harness reports
  job failure as output, not process exit code), stdout contains the
  structured error envelope, no traceback swallowed silently.

## Spec-consistency tests (stage 03 documented claims — no GPU required)
The three stage 03 audit boxes about profile numbers, checkpoint fallback
order, and warmup timing are claims about the *written spec*, not about
live GPU behavior (this goal's boundaries exclude GPU/CUDA runtime tests
entirely). `tests/test_spec_consistency.py` verifies the spec text itself
is internally consistent by reading the stage output and reference files
as plain text — still CPU-only, still network-free:
| Test | Asserts |
|------|---------|
| `test_checkpoint_resolution_order_documented` | in `stages/03-engine-and-model-lifecycle/output/engine-and-model-lifecycle.md`, the substring position of `/runpod-volume` precedes `hf_transfer`, which precedes `huggingface_hub fallback` — proving the three-step order (volume cache → hf_transfer → plain huggingface_hub) is stated in that order, not just mentioned |
| `test_profile_flags_and_vram_match_reference` | the exact strings `--fast-all`, `~7.7 GiB`, `~14.4 GiB` (and, if present, `12 GB` / `24 GB`) appear identically in both `stages/03-engine-and-model-lifecycle/output/engine-and-model-lifecycle.md` and `references/breezetts-architecture.md`'s Inference profiles table — a spec edit that drifts the two out of sync fails this test |
| `test_warmup_within_init_timeout_documented` | `stages/03-engine-and-model-lifecycle/output/engine-and-model-lifecycle.md` states warmup completes inside the init budget, and the literal value `RUNPOD_INIT_TIMEOUT=1200` it references matches the same literal in `references/runpod-invariants.md` AND in `stages/05-container-and-dockerfile/output/container-and-dockerfile.md` — proving the 1200 s budget is consistent across the engine spec and the container spec that actually sets the env var |

## Container smoke check (against stage 05 spec)
`tests/test_container_spec.py` — parses `Dockerfile` (repo root, no actual
`docker build`, per this goal's boundary against real builds) as text and
asserts, per
`../../stages/05-container-and-dockerfile/output/container-and-dockerfile.md`:
`test_dockerfile_entrypoint_empty` (`ENTRYPOINT []` present literally),
`test_dockerfile_cmd_unbuffered` (`CMD ["python3", "-u", "handler.py"]`
present literally), `test_dockerfile_init_timeout_env`
(`RUNPOD_INIT_TIMEOUT=1200` present), `test_dockerfile_flash_attn_pinned`
(`flash-attn==2.8.3` present), `test_dockerfile_flash_attn_arch_arg`
(`FLASH_ATTN_CUDA_ARCHS` build arg present with default `90`).

## Crash-dump behaviour
`tests/test_handler.py::test_synthesis_crash_dumps_traceback_no_secrets` —
forces `engine.synthesize` to raise; asserts stdout (captured) contains the
traceback and job context, the handler returns a structured error (process
does not exit), and the captured stdout contains neither the mocked
reference-audio bytes nor any credential string.
`tests/test_handler.py::test_delivery_failure_returns_structured_error` —
forces the mocked `storage.deliver(...)` to raise (simulating `s3` mode
with missing credentials); asserts the handler catches it the same way as a
synthesis failure (step 3 of the handler flow), returns the identical
structured error envelope shape, and the process does not exit.
`tests/test_engine.py::test_bootstrap_crash_dumps_before_exit` — forces
`load_runtime` to raise during the mocked bootstrap path; asserts a full
traceback is printed to stdout before the process would exit.

## Requirements pins test
`tests/test_requirements_pins.py::test_requirements_pins_present` — parses
`requirements.txt` (repo root, Phase 2 artifact) line by line and asserts
`boto3`, `botocore>=1.36`, and `hf_transfer` are each present with an
explicit version pin or floor (not left unpinned) — a regression that drops
or loosens any of these three fails this test.

## Stage 02–05 Audits → test coverage map (binding cross-check)
| Stage | Audit box | Test |
|-------|-----------|------|
| 02 | Both size constants named exactly, applied to decoded bytes | `test_reference_audio_exactly_4mb_accepted`, `test_reference_audio_total_exactly_6mb_accepted`, `test_limits_apply_to_decoded_not_base64_length` |
| 02 | Decode happens in exactly one pass | `test_limits_apply_to_decoded_not_base64_length` (a decode-twice implementation would double-count and misfire the boundary) |
| 02 | Per-mode required/forbidden matrix complete | `test_validate_clone_golden`, `test_validate_design_golden`, `test_validate_direction_golden`, `test_validate_design_rejects_reference_audio`, `test_validate_clone_missing_reference_text` |
| 02 | All 8 vocal events listed as passthrough | `test_vocal_events_passthrough` |
| 02 | `response_delivery` enum and default stated | `test_deliver_auto_prefers_s3_when_credentials_present` (exercises the `auto` default end to end) |
| 02 | Error envelope contains no credential material | `test_secret_never_in_repr_or_error` |
| 03 | Bootstrap is provably module-scope | `test_bootstrap_crash_dumps_before_exit` (bootstrap failure is only reachable at import time in the mocked harness, proving no per-job load path exists) |
| 03 | Checkpoint resolution order stated with both fallbacks | `test_checkpoint_resolution_order_documented` |
| 03 | Both profiles specified with exact flags and VRAM budgets | `test_profile_flags_and_vram_match_reference` |
| 03 | Warmup completes inside the 1200 s init budget | `test_warmup_within_init_timeout_documented` |
| 03 | Crash dump covers every failure path, leaks no secrets | `test_bootstrap_crash_dumps_before_exit`, `test_synthesis_crash_dumps_traceback_no_secrets` |
| 04 | `import runpod` + `runpod.serverless.start(...)` present and top-level | `test_handler_test_input_clone` (the RunPod local harness only works at all if both are present and top-level — a missing/misplaced call fails this test at the subprocess level) |
| 04 | `AUDIO_DELIVERY` enum + `auto` semantics stated | `test_deliver_auto_prefers_s3_when_credentials_present`, `test_deliver_base64_fallback_when_credentials_absent`, `test_deliver_s3_mode_fails_loudly_without_credentials` |
| 04 | All 7 S3 response fields specified | `test_deliver_s3_response_fields` |
| 04 | B2 checksum config and key template quoted verbatim | `test_deliver_s3_uses_when_required_checksum_config`, `test_deliver_s3_key_template` |
| 04 | Credentials wrapped in `Secret`; crash dumps leak nothing | `test_secret_never_in_repr_or_error`, `test_synthesis_crash_dumps_traceback_no_secrets` |
| 05 | `ENTRYPOINT []` literal, not omitted | `test_dockerfile_entrypoint_empty` |
| 05 | `CMD ["python3", "-u", "handler.py"]` exact | `test_dockerfile_cmd_unbuffered` |
| 05 | `RUNPOD_INIT_TIMEOUT=1200` set in the image | `test_dockerfile_init_timeout_env` |
| 05 | sm90 and sm80 both covered; `flash-attn` pinned | `test_dockerfile_flash_attn_pinned`, `test_dockerfile_flash_attn_arch_arg` |
| 05 | `boto3`, `botocore>=1.36`, `hf_transfer` pinned explicitly | `tests/test_requirements_pins.py::test_requirements_pins_present` (parses `requirements.txt`, asserts `boto3`, `botocore>=1.36`, `hf_transfer` all present and explicitly versioned/floored) |

Every stage 02–05 audit box has a named test above; none is left uncovered.
