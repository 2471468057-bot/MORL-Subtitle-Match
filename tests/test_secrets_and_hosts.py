import subtitle_core


def test_secret_loader_prefers_env(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-test-env")
    monkeypatch.delenv("2BYTEASR_DASHSCOPE_API_KEY", raising=False)
    value = subtitle_core._load_secret_value("DASHSCOPE_API_KEY", "2BYTEASR_DASHSCOPE_API_KEY")
    assert value == "sk-test-env"


def test_require_runtime_secrets_raises_when_missing(monkeypatch):
    monkeypatch.setattr(subtitle_core, "get_dashscope_api_key", lambda: "")
    try:
        subtitle_core.require_runtime_secrets(require_dashscope=True, require_hf=False)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "DASHSCOPE_API_KEY" in str(exc)


def test_host_registry_loader_handles_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(subtitle_core, "HOST_VOICEPRINT_REGISTRY_PATH", str(tmp_path / "missing.json"))
    payload = subtitle_core.load_host_voiceprint_registry()
    assert payload["hosts"] == []


def test_describe_secret_source_masks_and_prefers_env(monkeypatch):
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-ws-ABCDEFGHxxxxYYYY")
    source, value = subtitle_core.describe_secret_source()
    assert source.startswith("env:")
    assert value.startswith("sk-ws-")
    masked = subtitle_core.mask_api_key(value)
    assert "ABCD" in masked or "sk-ws-" in masked
    assert "YYYY" in masked
