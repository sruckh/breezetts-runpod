# Stage 03 — engine-and-model-lifecycle

> Layer 2 · "What do I do?" — the control point of the whole system.

**Purpose:** Define module-scope model bootstrap, Hugging Face checkpoint resolution (volume cache + hf_transfer fallback), eager vs --fast-all CUDA Graph warmup, and diagnostic error trapping.

One job: specify the engine lifecycle. This stage does not define the request
handler, storage, container, or tests.

## Inputs
| Kind | File/Location | Scope | Why |
|------|---------------|-------|-----|
| working | ../02-schema-and-validation/output/ | full | the NormalizedRequest the engine consumes |
| reference | ../../references/breezetts-architecture.md | all | modes, profiles, VRAM budgets |
| reference | ../../references/runpod-invariants.md | all | bootstrap, cache, crash-dump rules |

Exact paths only. **working** = this run (product, L4). **reference** = every
run (factory, L3). Anything not listed here is not loaded.

## Process
1. Read the inputs above — only those.
2. Specify module-scope bootstrap: model load at import time; the job handler
   receives an already-warm engine.
3. Specify checkpoint resolution order: `/runpod-volume` cache → `hf_transfer`
   download → plain `huggingface_hub` fallback.
4. Specify the two inference profiles: eager (~7.7 GiB) and `--fast-all`
   modular CUDA Graphs (~14.4 GiB), including the one-time warmup sequence
   that fits inside `RUNPOD_INIT_TIMEOUT=1200`.
5. Specify synthesis dispatch per mode (clone / design / direction) with
   `cfg_scale` handling and vocal-event text reaching the model untouched.
6. Specify diagnostic error trapping: full traceback + context dumped to
   stdout before any exit.
7. Write the spec to `output/`.

## Outputs
| Artifact | Location | Format |
|----------|----------|--------|
| Engine lifecycle spec | output/engine-and-model-lifecycle.md | markdown |

## Human check
Walk the bootstrap sequence top to bottom and confirm no code path loads the
model inside a request. Edit in place; the next stage reads whatever is here.

## Audits
- [ ] Bootstrap is provably module-scope
- [ ] Checkpoint resolution order stated with both fallbacks
- [ ] Both profiles specified with exact flags and VRAM budgets
- [ ] Warmup completes inside the 1200 s init budget
- [ ] Crash dump covers every failure path, leaks no secrets
