Human check: agent-verified — pending human

# Stage 03 output — engine-and-model-lifecycle

## Module-scope bootstrap (provably import-time)
The engine module (e.g. `engine.py`) performs all of the following at
**module scope** — executed once when the interpreter imports the module,
before `handler.py`'s `runpod.serverless.start(...)` call runs, and never
inside a function invoked per job:
```python
# module scope — runs once at import time
_CKPT_DIR = resolve_checkpoint()          # see Checkpoint resolution below
_TOKENIZER, _MODEL, _AUDIO_TOKENIZER = load_runtime(
    _CKPT_DIR, device=resolve_device(), attn_implementation="eager",
    # "eager" is passed unconditionally in both profiles — flash-attn is
    # engaged by the fast-path CUDA Graph modules, not this argument; see
    # ../../references/breezetts-architecture.md's "Inference profiles"
    # section (the flash-attn bullet, second bullet after the five-stage
    # table).
)
update_generation_config_for_breeze(_MODEL)
_RUNTIME = build_streaming_runtime(_MODEL, _AUDIO_TOKENIZER, fast_all=_FAST_ALL)
if _RUNTIME.fast_enabled:
    _RUNTIME.warmup_from_profile(load_warmup_profile(_FAST_CONFIG_PATH))
```
The per-job entry point (`synthesize(normalized_request) -> bytes`, called
by `handler.py`) only reads these module-level globals — it never calls
`load_runtime`, never re-instantiates the model, and never re-runs warmup.
A request that arrives before bootstrap completes is not possible under
RunPod's lifecycle: the platform does not route jobs to a worker until its
process has started, and `runpod.serverless.start(...)` (stage 04) is the
last line the module reaches, after the block above. See
`../../references/runpod-invariants.md` ("Module-scope model bootstrap").

## Checkpoint resolution order (both fallbacks stated)
`resolve_checkpoint()` tries, in order:
1. **Volume cache** — if `/runpod-volume/breeze-tts-2` (this worker's fixed
   checkpoint subdirectory, per
   `../../references/runpod-invariants.md`'s "Model cache & download")
   exists AND `/runpod-volume/breeze-tts-2/audio_tokenizer` is a directory,
   use it directly, no download. This worker checks the same condition upstream's
   own `load_runtime(...)` checks internally (it raises `FileNotFoundError`
   if `<ckpt_dir>/audio_tokenizer` is missing, per
   `../../references/breezetts-architecture.md`'s upstream-identity
   section) — checking it in `resolve_checkpoint()` first, rather than
   letting `load_runtime` raise, is what lets an incomplete volume cache
   fall through to step 2 instead of crashing bootstrap outright.
2. **`hf_transfer` download** — else, download `BreezeBlue/Breeze-TTS-2`
   (`../../references/breezetts-architecture.md#upstream-identity`) into
   `/runpod-volume/breeze-tts-2` with `HF_HUB_ENABLE_HF_TRANSFER=1` set
   (`huggingface_hub`'s toggle env var, per
   `../../references/runpod-invariants.md`'s "Model cache & download"), so
   `huggingface_hub` uses the `hf_transfer` accelerated backend.
3. **Plain `huggingface_hub` fallback** — if the `hf_transfer` download
   raises (missing binary, transfer error), retry the same download with
   `HF_HUB_ENABLE_HF_TRANSFER` unset (or `0`), using `huggingface_hub`'s
   default HTTP downloader. A failure on this fallback is fatal and goes
   through Diagnostic error trapping below — it exits the bootstrap, not a
   single job.
See `../../references/runpod-invariants.md` ("Model cache & download").

## Inference profiles (exact flags, exact VRAM budgets)
| Profile | Flag | VRAM | Min GPU |
|---------|------|------|---------|
| Eager | (default) | ~7.7 GiB | 12 GB |
| Fast | `--fast-all` | ~14.4 GiB | 24 GB |

`_FAST_ALL` is read once at bootstrap from an env var (`BREEZE_FAST_ALL`,
truthy string → `True`) — it is a deployment-time choice, not a per-request
parameter; `cfg_scale` is the only per-request tuning knob (see stage 02's
`NormalizedRequest`). When `_FAST_ALL` is set, `build_streaming_runtime`
constructs `FastStreamingConfig(fast_all=True, ...)` and
`_RUNTIME.warmup_from_profile(...)` performs one-time CUDA Graph capture for
all five stages listed in
`../../references/breezetts-architecture.md`'s Inference profiles section
(text encoder, backbone prefill, backbone decode, depth decoder, codec);
when unset, the engine skips
warmup entirely and runs native eager forward passes. Both paths — warmup
skipped (eager) or warmup run (`--fast-all`) — complete inside the module
bootstrap block above, which itself must finish inside the
`RUNPOD_INIT_TIMEOUT=1200` s budget (20 min) before RunPod marks the worker
unhealthy. See `../../references/runpod-invariants.md`.

## Synthesis dispatch per mode
`synthesize(req: NormalizedRequest) -> bytes` (returns 24 kHz mono 16-bit
PCM WAV bytes, per `../../references/breezetts-architecture.md`):
1. Select the upstream template by mode: `clone` → reference path with no
   instruction (`instruction` defaults to `"Speak clearly and naturally."`
   per the upstream CLI default pinned in
   `../../references/breezetts-architecture.md`); `design` → no reference,
   `instruct` required; `direction` → reference path with `instruct` set.
   Reference vs. no-reference selects the upstream template name per
   `../../references/breezetts-architecture.md`'s "Synthesis request
   templates" section (`ref_edit_tata` vs `tts_instruction`).
2. Pass `req.cfg_scale` straight through as the upstream `guidance_scale`
   argument to `prepare_inputs(...)` — no clamping or re-derivation; the
   Voice Design `4` baseline is applied by the caller (stage 02's default),
   not recomputed here.
3. `req.text` (containing any inline vocal events, English parentheses or
   Chinese brackets) reaches `prepare_inputs(...)` byte-for-byte —
   `schema_validator.py` already guaranteed passthrough (stage 02); the
   engine performs no additional parsing, stripping, or escaping of vocal
   events. See `../../references/breezetts-architecture.md`.
4. Collect PCM chunks from `_RUNTIME.iter_audio_chunks(...)` and write them
   through a single `soundfile.SoundFile` writer opened with
   `samplerate=24000, channels=1, subtype="PCM_16"`, returning the complete
   WAV bytes to the caller (`handler.py`, stage 04) for delivery.

## Diagnostic error trapping (every failure path, no secrets)
- Bootstrap failure (checkpoint resolution, `load_runtime`, or warmup
  raising): caught at module scope, the full traceback plus context
  (checkpoint path attempted, device, `_FAST_ALL` value) is printed to
  stdout via `traceback.print_exc()` before the process exits non-zero —
  this crashes the worker process (correct: a worker that cannot bootstrap
  must not accept jobs).
- Per-job synthesis failure: caught in `synthesize(...)`'s caller
  (`handler.py`), full traceback plus job context (job id, mode, whether
  reference audio was present — never the reference audio bytes or
  `reference_text` content) dumped to stdout before returning a structured
  error response; the process itself does not exit (one bad job must not
  kill a warm worker).
- No crash path ever logs decoded reference-audio bytes, credential
  material, or anything wrapped in a `Secret` container (there are none in
  this module; storage's `Secret` wrapping is stage 04's concern). See
  `../../references/runpod-invariants.md` ("Crash dumps").
