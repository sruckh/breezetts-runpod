# Reference — Payload contracts (`schema_validator.py`)

> Layer 3 · factory. Request/response shapes; stages 02 and 06 implement/test to this.

## Request envelope (all modes)
| Field | Type | Notes |
|-------|------|-------|
| `text` | string | synthesis text; may contain inline vocal events |
| `mode` | string | optional explicit `clone` / `design` / `direction`; inferred when absent |
| `reference_audio` | string or array of strings | one base64 clip, or a JSON array of base64 clips; required for clone/direction. A single string is normalized to a one-element array before decoding — every downstream rule (limits, decode) always operates on a list of clips. |
| `reference_text` | string | exact transcript of the reference; required with `reference_audio` |
| `instruct` | string | natural-language instruction; required for design/direction |
| `cfg_scale` | number | optional; default `4` (Voice Design baseline) |
| `response_delivery` | string | optional `auto` / `s3` / `base64`, default `auto` |

## Decoding & size limits (hard bounds)
- **Single-pass base64 decode** in `schema_validator.py` — decode once,
  reuse the bytes; no decode-then-redecode.
- `MAX_REFERENCE_AUDIO_BYTES = 4 MB` per clip — reject larger clips.
- `MAX_TOTAL_REFERENCE_AUDIO_BYTES = 6 MB` across all decoded reference
  audio in one request — reject larger totals.
- Limits apply to **decoded** bytes, not base64 length.

## Validation rules per mode
| Mode | Required | Forbidden |
|------|----------|-----------|
| clone | `reference_audio` + `reference_text` | — |
| design | `instruct` | `reference_audio` |
| direction | `reference_audio` + `reference_text` + `instruct` | — |

Vocal events pass through untouched: `(laugh)`, `(cough)`,
`(clears throat)`, `(sigh)`, `[笑]`, `[咳嗽]`, `[清嗓子]`, `[叹气]`
(see `breezetts-architecture.md`).

## Response envelope
Success: `audio` fields per `s3-storage.md` (`delivery`, plus either the S3
URL field set or the base64 payload), and the synthesis metadata below,
merged into one top-level response object.
Failure: structured error with machine-readable code, human message, and no
credential material — ever.

### Synthesis metadata (fixed field set, always present on success)
| Field | Type | Value |
|-------|------|-------|
| `mode` | string | the resolved mode actually synthesized: `clone` / `design` / `direction` |
| `cfg_scale` | number | the `cfg_scale` value actually applied |
| `sample_rate` | integer | `24000` (constant, per `breezetts-architecture.md`'s 24 kHz pin) |
| `duration_seconds` | number | WAV audio duration, computed as
  `size_bytes / (sample_rate * 2)` for 16-bit mono PCM (2 bytes per sample) |
