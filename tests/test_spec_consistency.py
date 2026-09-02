"""Static text consistency checks between stage 03's spec and the reference
files it must match -- no GPU required (this goal's boundaries exclude live
GPU/CUDA behavior tests entirely)."""
from pathlib import Path

ICM = Path(__file__).resolve().parent.parent / ".icm"
ENGINE_SPEC = (ICM / "stages/03-engine-and-model-lifecycle/output/engine-and-model-lifecycle.md").read_text()
ARCHITECTURE_REF = (ICM / "references/breezetts-architecture.md").read_text()
RUNPOD_REF = (ICM / "references/runpod-invariants.md").read_text()
CONTAINER_SPEC = (ICM / "stages/05-container-and-dockerfile/output/container-and-dockerfile.md").read_text()


def test_checkpoint_resolution_order_documented():
    volume_idx = ENGINE_SPEC.find("/runpod-volume")
    hf_transfer_idx = ENGINE_SPEC.find("hf_transfer")
    fallback_idx = ENGINE_SPEC.find("huggingface_hub` fallback")
    assert -1 < volume_idx < hf_transfer_idx < fallback_idx


def test_profile_flags_and_vram_match_reference():
    for token in ("--fast-all", "~7.7 GiB", "~14.4 GiB"):
        assert token in ENGINE_SPEC
        assert token in ARCHITECTURE_REF


def test_warmup_within_init_timeout_documented():
    assert "RUNPOD_INIT_TIMEOUT=1200" in ENGINE_SPEC or "1200" in ENGINE_SPEC
    assert "RUNPOD_INIT_TIMEOUT=1200" in RUNPOD_REF
    assert "RUNPOD_INIT_TIMEOUT=1200" in CONTAINER_SPEC
