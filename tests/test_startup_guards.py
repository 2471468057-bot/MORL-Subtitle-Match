import subtitle_core

def test_startup_self_test_passes():
    result = subtitle_core.run_startup_self_test()
    assert result["id"].startswith("startup-self-test-")
    assert result["checks"] >= 10

def test_pipeline_build_id_aligned():
    import auto_asr
    import moss_firered_pipeline
    assert auto_asr.PIPELINE_BUILD_ID == subtitle_core.PIPELINE_BUILD_ID
    assert moss_firered_pipeline.PIPELINE_BUILD_ID == subtitle_core.PIPELINE_BUILD_ID


def test_public_secret_redactor_is_available_to_stage_modules():
    from twobyteasr import correction, segmentation

    assert subtitle_core.redact_runtime_secrets("safe") == "safe"
    assert correction.redact_runtime_secrets("safe") == "safe"
    assert segmentation.redact_runtime_secrets("safe") == "safe"
