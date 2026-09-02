# Reference — RunPod serverless invariants

> Layer 3 · factory. Non-negotiable platform rules; stages 03/04/05 enforce them.

## Process & bootstrap
- **Module-scope model bootstrap**: the model loads at import time, never
  inside the job handler. A request must never trigger a model load.
- **Static scanner compliance**: the handler file must literally contain
  `import runpod` and a top-level `runpod.serverless.start(...)` call —
  RunPod's static scanner greps for both.
- **Crash dumps**: on unhandled failure, dump the full crash log (traceback +
  context) to stdout before exiting. Silent exits are forbidden.

## Container
- `ENTRYPOINT []` — explicitly empty, so RunPod's command injection works.
- `CMD ["python3", "-u", "handler.py"]` — unbuffered stdout/stderr (`-u`) so
  logs stream in real time.
- `RUNPOD_INIT_TIMEOUT=1200` — 20-minute init budget for model download and
  warmup before the worker is declared unhealthy. RunPod's platform default
  marks a worker unhealthy if cold start exceeds 7 minutes (420 s);
  `RUNPOD_INIT_TIMEOUT` extends that budget — `1200` s is this project's
  extension for model download plus warmup, confirmed against
  docs.runpod.io/serverless/development/optimization.

## Model cache & download
- Hugging Face cache lives on the network volume at `/runpod-volume`. This
  worker caches the Breeze TTS 2 checkpoint at the fixed subdirectory
  `/runpod-volume/breeze-tts-2`.
- Downloads use `hf_transfer==0.1.9` (current release, PyPI, checked
  2026-09-01) with a plain `huggingface_hub` fallback when `hf_transfer` is
  unavailable or fails. `hf_transfer` is enabled through
  `huggingface_hub`'s own toggle env var, `HF_HUB_ENABLE_HF_TRANSFER=1`; the
  plain fallback unsets it (or sets `0`) and retries with
  `huggingface_hub`'s default HTTP downloader.

## Python SDK
- `runpod==1.12.0` (current release, PyPI, checked 2026-09-01) — provides
  `runpod.serverless.start(...)` and the `--test_input` local harness.
- Warmup (eager or `--fast-all` CUDA Graph capture) happens once during
  bootstrap, inside the init-timeout budget — see
  `breezetts-architecture.md` for the profiles.

## Local testing
- The handler must run under RunPod's local mock:
  `python3 handler.py --test_input '<json>'` (also exercised via
  `RUNPOD_LOCAL_TEST` conventions). Stage 06 builds the suite on this.
