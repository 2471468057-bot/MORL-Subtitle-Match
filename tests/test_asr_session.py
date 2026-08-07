import sys
import types

from twobyteasr import asr


def _fake_torch(monkeypatch):
    """CI 不安装 torch；该测试只验证会话复用逻辑，与 CUDA 无关。"""
    fake = types.ModuleType("torch")
    fake.cuda = types.SimpleNamespace(is_available=lambda: False, empty_cache=lambda: None)
    monkeypatch.setitem(sys.modules, "torch", fake)


def test_qwen_model_is_reused_only_inside_explicit_queue_session(monkeypatch):
    _fake_torch(monkeypatch)
    marker = object()
    asr.begin_local_asr_session()
    try:
        assert asr._reuse_or_remember_qwen_model(marker) is marker
        assert asr._session_qwen_model() is marker
        assert asr._qwen_model_is_session_owned(marker)
    finally:
        asr.end_local_asr_session()

    assert asr._session_qwen_model() is None
    assert not asr._qwen_model_is_session_owned(marker)
