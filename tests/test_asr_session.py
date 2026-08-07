from twobyteasr import asr


def test_qwen_model_is_reused_only_inside_explicit_queue_session():
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
