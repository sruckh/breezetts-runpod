"""Static text checks of the Dockerfile against stage 05's spec -- no
`docker build`, per this goal's boundaries."""
from pathlib import Path

DOCKERFILE = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text()


def test_dockerfile_entrypoint_empty():
    assert "ENTRYPOINT []" in DOCKERFILE


def test_dockerfile_cmd_unbuffered():
    assert 'CMD ["python3", "-u", "handler.py"]' in DOCKERFILE


def test_dockerfile_init_timeout_env():
    assert "RUNPOD_INIT_TIMEOUT=1200" in DOCKERFILE


def test_dockerfile_flash_attn_pinned():
    assert "flash-attn==2.8.3" in DOCKERFILE


def test_dockerfile_flash_attn_arch_arg():
    assert "ARG FLASH_ATTN_CUDA_ARCHS=90" in DOCKERFILE
    assert "FLASH_ATTN_CUDA_ARCHS" in DOCKERFILE
