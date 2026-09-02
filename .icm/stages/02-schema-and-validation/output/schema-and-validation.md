Human check: agent-verified — pending human

# Stage 02 output — schema-and-validation (`schema_validator.py`)

## Module API
```python
def validate(payload: dict) -> NormalizedRequest: ...
```
Raises `ValidationError` (see Error envelope below) on any failure; never
raises a bare exception. `NormalizedRequest` carries: `text`, `mode`
(resolved, one of `clone` / `design` / `direction`), `reference_audio_bytes`
(`list[bytes]`, decoded, empty for `design`), `reference_text`, `instruct`,
`cfg_scale` (float, default `4`), `response_delivery` (validated enum
member, passed through unchanged — see "`response_delivery` resolution"
below; the `auto` → `s3`-or-`base64` decision itself happens in stage 04,
not here).

## Per-mode required/forbidden matrix
(verbatim from `../../references/payload-contracts.md`)

| Mode | Required | Forbidden |
|------|----------|-----------|
| `clone` | `reference_audio` + `reference_text` | — |
| `design` | `instruct` | `reference_audio` |
| `direction` | `reference_audio` + `reference_text` + `instruct` | — |

Mode resolution when `mode` is absent from the payload: `reference_audio`
present ⇒ `clone` or `direction` (`instruct` also present ⇒ `direction`);
`reference_audio` absent ⇒ `design`. If `mode` is present explicitly, it is
validated against this same required/forbidden matrix — a mismatch (e.g.
`mode: "design"` with `reference_audio` set) is a validation failure, not a
silent override.

## Single-pass base64 decode (exactly one pass)
0. **Normalize** `reference_audio` to a list before any decoding: per
   `../../references/payload-contracts.md`, the field is either a single
   base64 `string` or a JSON array of base64 strings. If it is a `string`,
   wrap it as a one-element list; if it is already an array, use it as-is.
   Every step below operates on this normalized `list[str]` — there is no
   code path that decodes a bare `string` payload directly.
1. For each clip in the normalized list, call `base64.b64decode` exactly
   once; the resulting `bytes` object is stored (as `reference_audio_bytes:
   list[bytes]`) and reused by every downstream consumer (engine, storage).
   No code path decodes the same clip a second time.
2. Apply `MAX_REFERENCE_AUDIO_BYTES = 4 MB` (4 * 1024 * 1024 bytes) to the
   length of each decoded clip individually — reject a clip exceeding this
   with `error.code = "reference_audio_too_large"`.
3. Sum the decoded lengths of all clips in the request and apply
   `MAX_TOTAL_REFERENCE_AUDIO_BYTES = 6 MB` (6 * 1024 * 1024 bytes) to the
   total — reject with `error.code = "reference_audio_total_too_large"`.
4. Both limits apply to **decoded** bytes, never to base64-string length
   (base64 inflates size ~4/3×, so base64-length checks would misfire).
   See `../../references/payload-contracts.md`.

## Vocal-event passthrough (all 8, both syntaxes)
Validation performs no stripping, rewriting, or escaping of these sequences
anywhere in `text`:
`(laugh)`, `(cough)`, `(clears throat)`, `(sigh)`,
`[笑]`, `[咳嗽]`, `[清嗓子]`, `[叹气]`.
They are opaque substrings to `schema_validator.py`; only the engine (stage
03) interprets them. See `../../references/breezetts-architecture.md`.

## `response_delivery` resolution
Enum: `auto | s3 | base64`. Default: `auto`. `schema_validator.py` only
validates the field is one of these three values (or absent, defaulting to
`auto`) and passes it through unchanged in `NormalizedRequest`; the actual
`auto` → `s3`-or-`base64` resolution (credential presence check) happens in
`storage.py` (repo root, stage 04), not here. See
`../../references/s3-storage.md`.

## Error envelope (fail-fast, structured, machine-readable)
```json
{
  "error": {
    "code": "missing_required_field",
    "message": "clone mode requires reference_text",
    "field": "reference_text"
  }
}
```
- `code`: machine-readable, snake_case, stable (used by tests and callers to
  branch on failure type). Fixed set includes at minimum:
  `missing_required_field`, `forbidden_field_for_mode`, `invalid_mode`,
  `invalid_base64`, `reference_audio_too_large`,
  `reference_audio_total_too_large`, `invalid_response_delivery`.
- `message`: human-readable, no interpolation of secrets or raw payload
  bytes.
- Never includes: credential material, decoded audio bytes, or any value
  wrapped in a `Secret` container (there are none at this stage, but the
  rule holds for every stage per `../../_config/conventions.md`).
- Validation returns on the **first** failing rule per request (fail-fast);
  it does not accumulate a list of all violations.

## Reference text and instruction pass-through
`reference_text` and `instruct` are passed through as UTF-8 strings, exact,
untrimmed of vocal-event syntax; no length cap is specified by
`../../references/payload-contracts.md` beyond the implicit request-size
limits enforced by RunPod's platform, so `schema_validator.py` does not
impose one.
