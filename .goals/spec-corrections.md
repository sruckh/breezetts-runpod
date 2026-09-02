# Spec corrections log — PHASE 0

## Audit baseline
`icm audit .icm --strict` → `OK — conforms to ICM conventions (0 warning(s))`,
exit 0, before any Phase 1/2 work. Re-run after every structural change.

## Checkbox-to-fact verification (stages 01–05 Audits, read against
`.icm/references/*.md` before any stage output existed)
- Stage 01 all 6 boxes: facts present verbatim in `breezetts-architecture.md`,
  `payload-contracts.md`, `runpod-invariants.md`, `s3-storage.md`.
- Stage 02 all 6 boxes: present in `payload-contracts.md` +
  `breezetts-architecture.md` (vocal events) + `_config/conventions.md`
  (single-pass decode rule).
- Stage 03 all 5 boxes: present in `breezetts-architecture.md` +
  `runpod-invariants.md`.
- Stage 04 all 5 boxes: present in `s3-storage.md` + `runpod-invariants.md`.
- Stage 05 all 5 boxes: present in `runpod-invariants.md` (container section)
  + `breezetts-architecture.md` (inference profiles) + `s3-storage.md`
  (botocore floor).

No internal inconsistency found across `_config/`, `references/`, and the six
`stages/*/CONTEXT.md` contracts — numbers agree everywhere (24 kHz/mono/16-bit
PCM WAV, ~7.7 GiB / ~14.4 GiB, 4 MB / 6 MB, `RUNPOD_INIT_TIMEOUT=1200`,
`ENTRYPOINT []`, `botocore>=1.36`). **No contract edits made** — none were
needed; this section exists to record that the check happened, per the goal's
Phase 0 instruction.

## Upstream verification (stage 01 Process step 3 — resolve against upstream
sources before pinning stage 01's output)
Confirmed live 2026-09-01 via web research (not from training-data memory):
- Model: `BreezeBlue/Breeze-TTS-2` on Hugging Face; inference code
  `github.com/breezeblue-ai/breeze-tts` (Apache-2.0 source; **model weights
  are BreezeBlue Research and Non-Commercial License** — a fact worth stating
  in stage 01 output for completeness, out of scope for the Audits list, and
  not a blocker for the technical build).
- CLI (`infer.py`): positional `model` (checkpoint dir), `--text`,
  `--instruction`, `--ref-audio`, `--ref-text`, `--output`, `--seed`,
  `--cfg-scale` (default `1.0` upstream; our contract's Voice Design baseline
  of `--cfg-scale 4` is a request-level override we apply, not upstream's
  default — both are correct, pinned as such in the stage 01 output),
  `--fast-all` plus five independently-togglable
  `--[no-]fast-{text-encoder,backbone-prefill,backbone-decode,depth-decoder,codec}`
  flags.
- Runtime API: `breeze_infer.runtime.load_runtime(ckpt_dir, device=...,
  attn_implementation=...)` → `(tokenizer, model, audio_tokenizer)`;
  `update_generation_config_for_breeze(model)`; audio tokenizer is
  `qwen_tts.Qwen3TTSTokenizer` bundled at `<ckpt_dir>/audio_tokenizer`
  (Apache-2.0, from Alibaba Qwen3-TTS).
- Confirmed VRAM/format numbers match our pinned references exactly: eager
  ~7.7 GiB (12 GB GPU min) / `--fast-all` ~14.4 GiB (24 GB GPU recommended);
  streaming output is mono 24 kHz signed 16-bit little-endian PCM.
- Upstream Docker base: `pytorch/pytorch:2.9.1-cuda12.8-cudnn9-devel`;
  `flash-attn==2.8.3` built with `FLASH_ATTN_CUDA_ARCHS` (`90` default /
  Hopper, `80` for A100) via `MAX_JOBS=8 ... pip install --no-build-isolation
  --no-deps "flash-attn==2.8.3"`.
- Upstream `requirements.txt` pins: `torch==2.9.1`, `torchaudio==2.9.1`,
  `qwen-tts==0.1.1`, `transformers==4.57.3`, `numpy>=2.0`, `soundfile>=0.13`,
  `fastapi>=0.115`, `uvicorn>=0.30`, `python-multipart>=0.0.18`.
- Confirmed against RunPod docs (docs.runpod.io): literal
  `import runpod` / `runpod.serverless.start({"handler": handler})`,
  `CMD ["python3", "-u", "handler.py"]`, the `--test_input '<json>'` local
  test flag, and that `RUNPOD_INIT_TIMEOUT` extends the default 7-minute
  cold-start health check (our pinned `1200` s = 20 min is a deliberate
  extension for model download + warmup, consistent with the platform
  default, not a contradiction of it).

These are new pinned facts for stage 01's *output* (`references/*.md` already
carried the architecture-level numbers correctly; stage 01 output additionally
carries the concrete upstream repo/checkpoint/CLI/API identities that
`breezetts-architecture.md` deferred to "stage 01 output").

## Correction — `worker/storage.py` → `storage.py` (repo root), discovered
entering PHASE 2
The ICM spec (stage 02 output, stage 04 output, stage 04's own `CONTEXT.md`,
and `references/s3-storage.md`'s title) consistently named the delivery
module `worker/storage.py`, implying a `worker/` subdirectory. The goal's
Phase 2 instruction and Done criterion 4 are unambiguous and binding: *"Repo
root contains working schema_validator.py, engine module, handler.py,
storage.py, Dockerfile, requirements.txt"* — a flat repo-root layout, no
`worker/` subdirectory, file named `storage.py`. This is a genuine
disagreement between the ICM spec and the goal's binding deliverable
contract, caught before any code was written. **Corrected**: all four
occurrences (`stages/02.../output/schema-and-validation.md`,
`stages/04.../output/handler-and-storage.md` ×2,
`stages/04.../CONTEXT.md` — a contract file, edited because this is a
genuine error per the goal's Phase 0 scope rule — and
`references/s3-storage.md`'s title) now say `storage.py` (repo root). No
other content changed; the delivery logic itself was already
directory-agnostic. `icm audit .icm --strict` re-run clean after the fix.
