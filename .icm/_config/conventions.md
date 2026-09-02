# Config — Conventions

> Layer 3 · factory. Rules every stage's output must obey.

## Code conventions (the worker being specified)
- Secrets live in a `Secret` container; never logged, never in `repr()`,
  never in crash dumps.
- Base64 reference audio is decoded exactly once (single-pass) in
  `schema_validator.py`; downstream code receives bytes, not base64.
- All logs unbuffered (`python3 -u`); crash paths dump full logs to stdout
  before exit.
- Every external dependency is pinned explicitly; `botocore>=1.36` is a hard
  floor (B2 checksum fix).
- Validation fails fast with structured, machine-readable errors.

## Workspace conventions (this pipeline)
- Numbers, flag names, and field names are quoted verbatim from
  `references/` — never paraphrased or rounded in stage outputs.
- One fact, one home: stage outputs link to `references/` instead of copying
  spec text.
- Scratch notes, test scripts, and logs go to `../.goals/`, never the repo
  root.
