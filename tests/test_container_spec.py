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


def test_dockerfile_break_system_packages_env():
    assert "PIP_BREAK_SYSTEM_PACKAGES=1" in DOCKERFILE


def test_dockerfile_runpod_log_level_env():
    assert "RUNPOD_LOG_LEVEL=INFO" in DOCKERFILE


def test_dockerfile_flash_attn_wheel_installed():
    assert "flash-attn==2.8.3" in DOCKERFILE
    assert "https://github.com/Dao-AILab/flash-attention/releases/expanded_assets" in DOCKERFILE
