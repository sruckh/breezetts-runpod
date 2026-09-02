# Reference — Breeze TTS 2 architecture

> Layer 3 · factory. Pinned by stage 01; every later stage trusts these values.

## Upstream identity
- Model weights: `BreezeBlue/Breeze-TTS-2` (Hugging Face). Inference code:
  `github.com/breezeblue-ai/breeze-tts`, Apache-2.0 licensed source; model
  weights, checkpoints, and derivative outputs are governed separately by
  the BreezeBlue Research and Non-Commercial License — commercial use
  requires written authorization from BreezeBlue AI.
- Audio tokenizer: `qwen_tts.Qwen3TTSTokenizer`, bundled inside the
  checkpoint at `<ckpt_dir>/audio_tokenizer` (Apache-2.0, from Alibaba
  Qwen3-TTS). Upstream's own `load_runtime(...)` raises `FileNotFoundError`
  if `<ckpt_dir>/audio_tokenizer` is not a directory — this is upstream's
  built-in checkpoint-completeness check, not something this worker adds.
- Backbone class: `models.breeze.BreezeForConditionalGeneration`, loaded
  with `dtype=torch.bfloat16`.
- Runtime module: `breeze_infer.runtime` —
  `load_runtime(ckpt_dir, *, device, attn_implementation) -> (tokenizer,
  model, audio_tokenizer)`, `update_generation_config_for_breeze(model)`,
  `resolve_device()`, `set_all_seeds(seed)`.
- Upstream CLI (`infer.py`) confirms field pairing: `--ref-audio` /
  `--ref-text` must be supplied together or both omitted; `--instruction`
  defaults to `"Speak clearly and naturally."` when absent; upstream's own
  `--cfg-scale` default is `1.0` — this project's `4` Voice Design baseline
  is a request-level override this worker applies, not a change to
  upstream's default.

## Container build stack (upstream `docker/Dockerfile`)
- Base image: `pytorch/pytorch:2.9.1-cuda12.8-cudnn9-devel`.
- `flash-attn==2.8.3`, built with `MAX_JOBS=8
  FLASH_ATTN_CUDA_ARCHS=${FLASH_ATTN_CUDA_ARCHS} pip install
  --no-build-isolation --no-deps "flash-attn==2.8.3"`
  (`FLASH_ATTN_CUDA_ARCHS` = `90` default / Hopper, `80` for A100).
- Upstream `requirements.txt` pins: `torch==2.9.1`, `torchaudio==2.9.1`,
  `qwen-tts==0.1.1`, `transformers==4.57.3`, `numpy>=2.0`,
  `soundfile>=0.13`. This worker adds `runpod`, `boto3`,
  `botocore>=1.36` (B2 checksum fix floor, see `s3-storage.md`), and
  `hf_transfer` on top of these — pinned in stage 05's output.

## Model & audio format
- Engine: **Breeze TTS 2** (upstream identity pinned above).
- Output audio: **24 kHz, mono, 16-bit PCM WAV** — confirmed against the
  upstream streaming API response headers (`X-Sample-Rate`,
  `X-Sample-Format: s16le`) and `infer.py`'s `sf.SoundFile(...,
  samplerate=runtime.sample_rate, channels=1, subtype="PCM_16")`. Every
  delivery path
  (S3 object or base64 payload) carries exactly this format.
- Reference audio input: base64-encoded clips plus the **exact reference
  transcript text** (Voice Clone / Voice Direction modes).

## Synthesis modes (closed set of 3)
| Mode | Reference audio | Instruction text | CFG scale |
|------|-----------------|------------------|-----------|
| Voice Clone | required (base64 + exact transcript) | no | default |
| Voice Design | none (reference-free) | required — natural-language voice description | tuned, `--cfg-scale 4` baseline |
| Voice Direction | required (identity preserved) | required — steers tone, emotion, pace, delivery | tuned |

Mode is inferred from payload shape: reference audio present ⇒ Clone or
Direction (instruction present ⇒ Direction); no reference audio ⇒ Design.

## Inline vocal events
Parsed inline in the synthesis text; never stripped by validation.
- English, parentheses: `(laugh)`, `(cough)`, `(clears throat)`, `(sigh)`
- Chinese, square brackets: `[笑]`, `[咳嗽]`, `[清嗓子]`, `[叹气]`

## Inference profiles
| Profile | Flag | VRAM | Min GPU |
|---------|------|------|---------|
| Eager | (default) | ~7.7 GiB | 12 GB |
| Fast | `--fast-all` (modular CUDA Graphs) | ~14.4 GiB | 24 GB |

`--fast-all` enables the best configuration for five independently
togglable pipeline stages (each also controllable alone via
`--[no-]fast-<stage>`, profiling/debugging use only):

| Stage | Fast parameter | Disabled | Enabled |
|-------|-----------------|----------|---------|
| Text encoder | `--[no-]fast-text-encoder` | native eager forward | static CUDA Graph selected by CFG shape and text-length bucket |
| Backbone prefill | `--[no-]fast-backbone-prefill` | native eager prefill | CUDA Graph selected by CFG shape and prompt-length bucket |
| Backbone decode | `--[no-]fast-backbone-decode` | native eager token step | StaticCache-backed graph selected by CFG shape |
| Depth decoder | `--[no-]fast-depth-decoder` | native eager depth loop | full-graph compilation with CFG-shape CUDA Graphs |
| Codec | `--[no-]fast-codec` | eager streaming decode | single-request streaming CUDA Graph with one-frame chunks |

- `--cfg-scale 4` is the Voice Design tuning baseline.
- `flash-attn` is compiled into the image and build targets **sm90 / sm80**
  (see Container build stack above), but it is engaged internally by the
  fast-path CUDA Graph modules (the five `--fast-*` stages above), not by
  the `attn_implementation` argument to `load_runtime(...)` — upstream's
  own `infer.py` and `breeze_infer.api` call `load_runtime(...,
  attn_implementation="eager")` unconditionally, in both the eager and
  `--fast-all` profiles. A worker built on this stack still needs
  `flash-attn` compiled in for the fast path to function even though the
  top-level model call always requests `"eager"`.

## Synthesis request templates (upstream `breeze_infer.templates`)
Upstream selects the prompt template by whether reference audio is present:
`ref_edit_tata` when `ref_audio_path` is set (Voice Clone / Voice
Direction), `tts_instruction` otherwise (Voice Design). Both templates
accept the same `guidance_scale` (this project's `cfg_scale`) parameter.

## Upstream API expectations
- Model loads once, at module scope — never per request (see
  `runpod-invariants.md`).
- Checkpoint resolution: `/runpod-volume` cache first, then download with
  `hf_transfer`, with a plain-download fallback if `hf_transfer` fails.
