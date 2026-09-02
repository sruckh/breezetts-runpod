# Spec: .icm/stages/05-container-and-dockerfile/output/container-and-dockerfile.md
FROM pytorch/pytorch:2.9.1-cuda12.8-cudnn9-devel

ARG FLASH_ATTN_CUDA_ARCHS=90

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    RUNPOD_INIT_TIMEOUT=1200 \
    HF_HOME=/runpod-volume/hf-cache \
    HF_HUB_ENABLE_HF_TRANSFER=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        ffmpeg \
        git \
        libsndfile1 \
        ninja-build \
        sox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

RUN python -m pip install --upgrade pip setuptools wheel packaging ninja \
    && grep -v '^flash-attn' requirements.txt > /tmp/requirements.no-flash-attn.txt \
    && python -m pip install -r /tmp/requirements.no-flash-attn.txt \
    && MAX_JOBS=8 FLASH_ATTN_CUDA_ARCHS=${FLASH_ATTN_CUDA_ARCHS} python -m pip install \
        --no-build-isolation \
        --no-deps \
        "flash-attn==2.8.3"

COPY . .

ENTRYPOINT []
CMD ["python3", "-u", "handler.py"]
