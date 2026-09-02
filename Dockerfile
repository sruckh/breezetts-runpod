# Spec: .icm/stages/05-container-and-dockerfile/output/container-and-dockerfile.md
FROM nvidia/cuda:12.8.0-cudnn-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    RUNPOD_LOG_LEVEL=INFO \
    RUNPOD_INIT_TIMEOUT=1200 \
    HF_HOME=/runpod-volume/hf-cache \
    HF_HUB_ENABLE_HF_TRANSFER=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-dev \
        ca-certificates \
        curl \
        ffmpeg \
        git \
        libsndfile1 \
        sox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

RUN python3 -m pip install --upgrade pip setuptools wheel

RUN python3 -m pip install --extra-index-url https://download.pytorch.org/whl/cu128 -r requirements.txt

RUN python3 -m pip install --no-deps \
    "https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl"

COPY . .

ENTRYPOINT []
CMD ["python3", "-u", "handler.py"]
