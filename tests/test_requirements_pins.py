from pathlib import Path

REQUIREMENTS = (Path(__file__).resolve().parent.parent / "requirements.txt").read_text()


def _lines():
    return [line.strip() for line in REQUIREMENTS.splitlines() if line.strip()]


def test_requirements_pins_present():
    lines = _lines()
    assert any(line.startswith("boto3==") for line in lines), "boto3 must be pinned exactly"
    assert any(line.startswith("botocore>=1.36") for line in lines), "botocore floor must be present"
    assert any(line.startswith("hf_transfer==") for line in lines), "hf_transfer must be pinned exactly"
    assert any(line.startswith("runpod==") for line in lines), "runpod must be pinned exactly"
