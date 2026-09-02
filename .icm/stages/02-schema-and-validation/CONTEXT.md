# Stage 02 — schema-and-validation

> Layer 2 · "What do I do?" — the control point of the whole system.

**Purpose:** Specify schema_validator.py: multi-mode validation, single-pass base64 decode with 4MB/6MB bounds, inline vocal events, response_delivery parameter.

One job: produce the validation spec. This stage does not touch the engine,
handler, storage, container, or tests.

## Inputs
| Kind | File/Location | Scope | Why |
|------|---------------|-------|-----|
| working | ../01-discovery-and-contracts/output/ | full | pinned contracts from discovery |
| reference | ../../references/payload-contracts.md | all | request/response shapes and limits |
| reference | ../../references/breezetts-architecture.md | modes + vocal events | what payloads must support |
| reference | ../../_config/conventions.md | all | fail-fast + single-pass decode rules |

Exact paths only. **working** = this run (product, L4). **reference** = every
run (factory, L3). Anything not listed here is not loaded.

## Process
1. Read the inputs above — only those.
2. Define the module API: `validate(payload) -> NormalizedRequest`, with the
   per-mode required/forbidden field table from `payload-contracts.md`.
3. Specify single-pass base64 decoding: decode once, enforce
   `MAX_REFERENCE_AUDIO_BYTES` (4 MB) per clip and
   `MAX_TOTAL_REFERENCE_AUDIO_BYTES` (6 MB) total on decoded bytes.
4. Specify vocal-event passthrough (both English and Chinese syntaxes) —
   validation never strips or rewrites them.
5. Specify `response_delivery` resolution (`auto | s3 | base64`, default
   `auto`) and the structured error envelope with machine-readable codes.
6. Write the spec to `output/`.

## Outputs
| Artifact | Location | Format |
|----------|----------|--------|
| Validator spec | output/schema-and-validation.md | markdown |

## Human check
Trace one payload per mode through the spec by hand and confirm each accepts
or rejects for the stated reason. Edit in place; the next stage reads
whatever is here.

## Audits
- [ ] Both size constants named exactly and applied to decoded bytes
- [ ] Decode happens in exactly one pass
- [ ] Per-mode required/forbidden matrix complete (clone / design / direction)
- [ ] All 8 vocal events listed as passthrough
- [ ] `response_delivery` enum and default stated
- [ ] Error envelope contains no credential material
