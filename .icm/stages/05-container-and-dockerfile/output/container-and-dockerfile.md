Human check: agent-verified — pending human

# Stage 05 output — container-and-dockerfile

## Base image and CUDA build configuration
Base: `pytorch/pytorch:2.9.1-cuda12.8-cudnn9-devel`, per
`../../references/breezetts-architecture.md#container-build-stack-upstream-dockerdockerfile`.

`flash-attn` is compiled from source, targeting **sm90** (default, Hopper /
H100) or **sm80** (A100), selected by the build-time
`FLASH_ATTN_CUDA_ARCHS` argument (`90` default, `80` for A100), matching
upstream's own build:
```dockerfile
ARG FLASH_ATTN_CUDA_ARCHS=90
...
RUN MAX_JOBS=8 FLASH_ATTN_CUDA_ARCHS=${FLASH_ATTN_CUDA_ARCHS} \
    python -m pip install --no-build-isolation --no-deps "flash-attn==2.8.3"
```
This worker's image inherits the same `ARG FLASH_ATTN_CUDA_ARCHS=90` default
and the identical `--no-build-isolation --no-deps flash-attn==2.8.3` install
line, so an A100 build overrides it with `--build-arg
FLASH_ATTN_CUDA_ARCHS=80` exactly as upstream's `docker/build.sh` does. See
`../../references/breezetts-architecture.md`.

## Explicit package pins
| Package | Pin | Source |
|---------|-----|--------|
| `torch` | `==2.9.1` | `../../references/breezetts-architecture.md` |
| `torchaudio` | `==2.9.1` | `../../references/breezetts-architecture.md` |
| `qwen-tts` | `==0.1.1` | `../../references/breezetts-architecture.md` |
| `transformers` | `==4.57.3` | `../../references/breezetts-architecture.md` |
| `numpy` | `>=2.0` | `../../references/breezetts-architecture.md` |
| `soundfile` | `>=0.13` | `../../references/breezetts-architecture.md` |
| `flash-attn` | `==2.8.3` | `../../references/breezetts-architecture.md` |
| `runpod` | `==1.12.0` | `../../references/runpod-invariants.md` |
| `boto3` | `==1.43.86` | `../../references/s3-storage.md` |
| `botocore` | `>=1.36` (hard floor — B2 checksum fix; `==1.43.86` satisfies it) | `../../references/s3-storage.md` |
| `hf_transfer` | `==0.1.9` | `../../references/runpod-invariants.md` |

All eleven packages above are pinned explicitly in `requirements.txt` (repo
root, Phase 2 artifact) — none is left to float on an unpinned transitive
resolution, per `../../_config/conventions.md` ("every external dependency
is pinned explicitly; `botocore>=1.36` is a hard floor").

## Environment
```dockerfile
ENV PYTHONUNBUFFERED=1 \
    RUNPOD_INIT_TIMEOUT=1200 \
    HF_HOME=/runpod-volume/hf-cache \
    HF_HUB_ENABLE_HF_TRANSFER=1
```
- `RUNPOD_INIT_TIMEOUT=1200` — literal, per
  `../../references/runpod-invariants.md`.
- HF cache directed at the network volume `/runpod-volume` (mounted at
  runtime by RunPod, not baked into the image), per
  `../../references/runpod-invariants.md`.
- `PYTHONUNBUFFERED=1` plus the `-u` CMD flag below both ensure logs stream
  unbuffered, redundantly and intentionally (image env survives even if a
  future CMD edit drops `-u`).

## Launch contract (exact)
```dockerfile
ENTRYPOINT []
CMD ["python3", "-u", "handler.py"]
```
`ENTRYPOINT []` is explicitly empty — not omitted — so RunPod's command
injection can override `CMD` at deploy time; `CMD` runs `handler.py`
unbuffered (`-u`). Both lines are literal, per
`../../references/runpod-invariants.md`.

## Build-time model bake-in
The Breeze TTS 2 checkpoint is **not** baked into the image — stage 03's
checkpoint-resolution order (volume cache → `hf_transfer` download → plain
`huggingface_hub` fallback) runs at container start, writing into
`/runpod-volume`, which persists across worker restarts on the same
network volume. This keeps the image build free of large model weights and
avoids re-downloading on every cold start once the volume is warm.
