"""Engine tests run against the mocked runtime (BREEZE_TEST_MOCK_ENGINE=1,
set in conftest.py) -- no GPU, no real model, no network."""
import sys
import types
import wave
from io import BytesIO
from pathlib import Path

import pytest

import engine
from schema_validator import validate


def test_synthesize_returns_24khz_mono_16bit_wav():
    req = validate({"text": "hello (laugh) world", "instruct": "calm"})
    wav_bytes = engine.synthesize(req)
    with wave.open(BytesIO(wav_bytes), "rb") as wav_file:
        assert wav_file.getframerate() == engine.SAMPLE_RATE == 24000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2


def test_synthesize_dispatches_all_three_modes():
    for payload in (
        {"text": "hi", "reference_audio": "AAAA", "reference_text": "t"},
        {"text": "hi", "instruct": "calm"},
        {"text": "hi", "reference_audio": "AAAA", "reference_text": "t", "instruct": "calm"},
    ):
        req = validate(payload)
        wav_bytes = engine.synthesize(req)
        assert wav_bytes[:4] == b"RIFF"


def test_vocal_events_reach_engine_unmodified():
    cue = "[叹气]"
    req = validate({"text": f"hello {cue} there", "instruct": "calm"})
    assert cue in req.text
    # The mocked engine does not parse vocal events; the guarantee under
    # test is that schema_validator's passthrough survives into the
    # NormalizedRequest the engine receives -- verified via req.text above.
    engine.synthesize(req)


def test_bootstrap_crash_dumps_before_exit(monkeypatch, capsys):
    """Forces a failure in the real (non-mock) bootstrap path and asserts
    the crash dump includes checkpoint path, device, and fast_all context
    (per the engine spec's "Diagnostic error trapping" section) before
    EngineBootstrapError is raised."""
    fake_runtime_module = types.ModuleType("breeze_infer.runtime")
    fake_runtime_module.load_runtime = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("model load exploded")
    )
    fake_runtime_module.resolve_device = lambda: "cpu"
    fake_runtime_module.update_generation_config_for_breeze = lambda model: None

    fake_fast_streaming_module = types.ModuleType("models.fast_streaming")
    fake_fast_streaming_module.FastBreezeStreamingRuntime = object
    fake_fast_streaming_module.FastStreamingConfig = lambda **k: None

    fake_warmup_module = types.ModuleType("models.warmup_profile")
    fake_warmup_module.load_warmup_profile = lambda path: None

    monkeypatch.setitem(sys.modules, "breeze_infer", types.ModuleType("breeze_infer"))
    monkeypatch.setitem(sys.modules, "breeze_infer.runtime", fake_runtime_module)
    monkeypatch.setitem(sys.modules, "models", types.ModuleType("models"))
    monkeypatch.setitem(sys.modules, "models.fast_streaming", fake_fast_streaming_module)
    monkeypatch.setitem(sys.modules, "models.warmup_profile", fake_warmup_module)
    monkeypatch.setattr(engine, "resolve_checkpoint", lambda: Path("/fake/ckpt"))
    monkeypatch.setattr(engine, "_MOCK_MODE", False)

    try:
        with pytest.raises(engine.EngineBootstrapError):
            engine._bootstrap()
    finally:
        monkeypatch.setattr(engine, "_MOCK_MODE", True)

    captured = capsys.readouterr().out
    assert "checkpoint_dir_attempted: /fake/ckpt" in captured
    assert "device: cpu" in captured
    assert "fast_all:" in captured
    assert "Traceback" in captured
    assert "model load exploded" in captured


def test_resolve_checkpoint_finds_runpod_cached_snapshot(tmp_path, monkeypatch):
    runpod_cache_hub = tmp_path / "huggingface-cache" / "hub"
    model_dir = runpod_cache_hub / "models--BreezeBlue--Breeze-TTS-2"
    snapshot_dir = model_dir / "snapshots" / "abc123456789"
    (snapshot_dir / "audio_tokenizer").mkdir(parents=True)
    (snapshot_dir / "config.json").write_text("{}")
    (model_dir / "refs").mkdir(parents=True)
    (model_dir / "refs" / "main").write_text("abc123456789")

    monkeypatch.setattr(engine, "VOLUME_ROOT", tmp_path)
    monkeypatch.setattr(engine, "CHECKPOINT_DIR", tmp_path / "breeze-tts-2")

    resolved = engine.resolve_checkpoint()
    assert resolved == snapshot_dir


def test_resolve_checkpoint_finds_available_snapshot_without_refs(tmp_path, monkeypatch):
    runpod_cache_hub = tmp_path / "huggingface-cache" / "hub"
    model_dir = runpod_cache_hub / "models--BreezeBlue--Breeze-TTS-2"
    snapshot_dir = model_dir / "snapshots" / "snap999"
    (snapshot_dir / "audio_tokenizer").mkdir(parents=True)

    monkeypatch.setattr(engine, "VOLUME_ROOT", tmp_path)
    monkeypatch.setattr(engine, "CHECKPOINT_DIR", tmp_path / "breeze-tts-2")

    resolved = engine.resolve_checkpoint()
    assert resolved == snapshot_dir


def test_resolve_checkpoint_uses_env_override(tmp_path, monkeypatch):
    custom_dir = tmp_path / "custom-breeze"
    (custom_dir / "audio_tokenizer").mkdir(parents=True)

    monkeypatch.setenv("BREEZE_CHECKPOINT_DIR", str(custom_dir))
    resolved = engine.resolve_checkpoint()
    assert resolved == custom_dir
