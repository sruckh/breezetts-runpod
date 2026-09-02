# Spec: .icm/stages/05-container-and-dockerfile/output/container-and-dockerfile.md
FROM pytorch/pytorch:2.9.1-cuda12.8-cudnn9-devel

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
        ca-certificates \
        curl \
        ffmpeg \
        git \
        libsndfile1 \
        sox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

RUN python -m pip install --upgrade pip setuptools wheel

RUN python -m pip install -r requirements.txt

RUN python -m pip install --no-deps \
    "https://github.com/Dao-AILab/flash-attention/releases/download/v2.8.3/flash_attn-2.8.3+cu12torch2.9cxx11abiTRUE-cp312-cp312-linux_x86_64.whl"

COPY . .

ENTRYPOINT []
CMD ["python3", "-u", "handler.py"]
