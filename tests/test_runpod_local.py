"""RunPod local harness: `python3 handler.py --test_input '<json>'`, per
mode, run as a real subprocess against the mocked engine (no GPU)."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_test_input(payload: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["BREEZE_TEST_MOCK_ENGINE"] = "1"
    env.pop("AUDIO_DELIVERY", None)
    for key in ("B2_ACCESS_KEY_ID", "B2_SECRET_ACCESS_KEY", "B2_ENDPOINT_URL", "B2_BUCKET"):
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, "handler.py", "--test_input", json.dumps({"input": payload})],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_handler_test_input_clone():
    result = _run_test_input({
        "text": "hello", "reference_audio": "AAAA", "reference_text": "hi there",
    })
    assert result.returncode == 0, result.stderr
    assert "run_job return" in result.stdout
    assert "'delivery'" in result.stdout


def test_handler_test_input_design():
    result = _run_test_input({"text": "hello", "instruct": "a calm voice"})
    assert result.returncode == 0, result.stderr
    assert "'delivery'" in result.stdout


def test_handler_test_input_direction():
    result = _run_test_input({
        "text": "hello", "reference_audio": "AAAA", "reference_text": "hi",
        "instruct": "speak slowly",
    })
    assert result.returncode == 0, result.stderr
    assert "'delivery'" in result.stdout


def test_handler_test_input_validation_failure():
    result = _run_test_input({"text": "hello", "mode": "design", "reference_audio": "AAAA"})
    # RunPod's local harness itself exits 1 when the handler returns an
    # "error" key (job failure) -- that is expected platform behavior, not
    # a crash; the process still ran the full validate -> respond path.
    assert result.returncode == 1, result.stderr
    assert "forbidden_field_for_mode" in result.stdout
