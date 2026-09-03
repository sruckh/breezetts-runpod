import base64

import botocore.session
from botocore.stub import Stubber

import storage

WAV_BYTES = b"RIFF....WAVEfmt "

B2_ENV = {
    "B2_ACCESS_KEY_ID": "test-key-id",
    "B2_SECRET_ACCESS_KEY": "test-secret",
    "B2_ENDPOINT_URL": "https://s3.us-west-004.backblazeb2.com",
    "B2_BUCKET": "test-bucket",
}


def _stubbed_client():
    session = botocore.session.get_session()
    client = session.create_client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="test-key-id",
        aws_secret_access_key="test-secret",
        endpoint_url="https://s3.us-west-004.backblazeb2.com",
    )
    stubber = Stubber(client)
    return client, stubber


def test_deliver_s3_uses_when_required_checksum_config(monkeypatch):
    for key, value in B2_ENV.items():
        monkeypatch.setenv(key, value)

    captured = {}

    def fake_client(*args, **kwargs):
        captured["config"] = kwargs.get("config")
        client, stubber = _stubbed_client()
        stubber.add_response("put_object", {})
        stubber.activate()
        return client

    monkeypatch.setattr(storage.boto3, "client", fake_client)
    storage.deliver(WAV_BYTES, "job-1", "s3")

    cfg = captured["config"]
    assert cfg.signature_version == "s3v4"
    assert cfg.request_checksum_calculation == "when_required"
    assert cfg.response_checksum_validation == "when_required"


def test_deliver_s3_key_template(monkeypatch):
    for key, value in B2_ENV.items():
        monkeypatch.setenv(key, value)

    client, stubber = _stubbed_client()
    stubber.add_response("put_object", {})
    stubber.activate()

    result = storage.deliver(WAV_BYTES, "job/../weird id", "s3", client=client)
    key = result["key"]
    assert key.count("/") == 3  # YYYY/MM/DD/<file>
    assert ".." not in key
    assert "/" not in key.rsplit("/", 1)[1].replace(".wav", "")
    assert key.endswith(".wav")


def test_deliver_s3_response_fields(monkeypatch):
    for k, v in B2_ENV.items():
        monkeypatch.setenv(k, v)

    client, stubber = _stubbed_client()
    stubber.add_response("put_object", {})
    stubber.activate()

    result = storage.deliver(WAV_BYTES, "job-1", "s3", client=client)
    assert set(result.keys()) == {
        "delivery", "audio_url", "bucket", "key", "size_bytes",
        "url_expires_in", "url_expires_at",
    }
    assert result["delivery"] == "s3"
    assert result["bucket"] == "test-bucket"
    assert result["size_bytes"] == len(WAV_BYTES)


def test_deliver_auto_prefers_s3_when_credentials_present(monkeypatch):
    for k, v in B2_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AUDIO_DELIVERY", "auto")

    client, stubber = _stubbed_client()
    stubber.add_response("put_object", {})
    stubber.activate()

    result = storage.deliver(WAV_BYTES, "job-1", "auto", client=client)
    assert result["delivery"] == "s3"


def test_deliver_base64_fallback_when_credentials_absent(monkeypatch):
    for key in B2_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AUDIO_DELIVERY", "auto")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("no network/boto3 call should happen for base64 fallback")

    monkeypatch.setattr(storage.boto3, "client", fail_if_called)

    result = storage.deliver(WAV_BYTES, "job-1", "auto")
    assert result["delivery"] == "base64"
    assert base64.b64decode(result["audio_base64"]) == WAV_BYTES
    assert result["size_bytes"] == len(WAV_BYTES)


def test_deliver_s3_mode_fails_loudly_without_credentials(monkeypatch):
    for key in B2_ENV:
        monkeypatch.delenv(key, raising=False)

    try:
        storage.deliver(WAV_BYTES, "job-1", "s3")
        raise AssertionError("expected DeliveryError")
    except storage.DeliveryError as exc:
        assert exc.code == "s3_credentials_missing"
        envelope = exc.to_dict()
        assert "test-secret" not in str(envelope)


def test_secret_never_in_repr_or_error():
    secret = storage.Secret("super-secret-value")
    assert "super-secret-value" not in repr(secret)
    assert "super-secret-value" not in str(secret)
    assert secret.reveal() == "super-secret-value"
