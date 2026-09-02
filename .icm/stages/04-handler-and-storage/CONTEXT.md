# Stage 04 — handler-and-storage

> Layer 2 · "What do I do?" — the control point of the whole system.

**Purpose:** Specify handler.py and storage.py: RunPod serverless lifecycle, Backblaze B2 S3 presigned URL delivery, base64 fallback, and crash dumps.

One job: specify the request path end to end. This stage does not define the
container build or the test suite.

## Inputs
| Kind | File/Location | Scope | Why |
|------|---------------|-------|-----|
| working | ../03-engine-and-model-lifecycle/output/ | full | the warm engine the handler calls |
| reference | ../../references/s3-storage.md | all | the delivery contract |
| reference | ../../references/runpod-invariants.md | all | scanner + crash-dump rules |
| reference | ../../references/payload-contracts.md | response envelope | what the handler returns |

Exact paths only. **working** = this run (product, L4). **reference** = every
run (factory, L3). Anything not listed here is not loaded.

## Process
1. Read the inputs above — only those.
2. Specify `handler.py`: literal `import runpod` and top-level
   `runpod.serverless.start(...)`; per-job flow validate → synthesize →
   deliver; `--test_input` local-mock entry.
3. Specify `storage.py` (repo root): `AUDIO_DELIVERY` resolution (`auto` prefers
   S3 when credentials exist), WAV upload, presigned GET URL (24 h default),
   and the full S3 response field set from `s3-storage.md`.
4. Specify the B2 fix: botocore `when_required` checksum config on the client.
5. Specify key generation from the `{prefix}{YYYY}/{MM}/{DD}/{sanitized_job_id}-{uuid4}.wav`
   template and `Secret` wrapping of all credentials.
6. Specify the base64 fallback path and the crash-dump-before-exit behaviour.
7. Write the spec to `output/`.

## Outputs
| Artifact | Location | Format |
|----------|----------|--------|
| Handler + storage spec | output/handler-and-storage.md | markdown |

## Human check
Follow one job through both delivery paths (S3 and base64) and confirm the
response matches `payload-contracts.md` in each. Edit in place; the next
stage reads whatever is here.

## Audits
- [ ] `import runpod` + `runpod.serverless.start(...)` present and top-level
- [ ] `AUDIO_DELIVERY` enum + `auto` semantics stated
- [ ] All 7 S3 response fields specified
- [ ] B2 checksum config and key template quoted verbatim
- [ ] Credentials wrapped in `Secret`; crash dumps leak nothing
