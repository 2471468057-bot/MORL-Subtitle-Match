import subtitle_core


def test_primary_speaker_cache_changes_with_expected_speaker_count(monkeypatch):
    monkeypatch.setattr(subtitle_core, "RUNTIME_EXPECTED_SPEAKERS", 2)
    two_speaker_signature = subtitle_core.cache_stage_signature(
        "firered_primary",
        extra={"moss": "same-recognition"},
    )

    monkeypatch.setattr(subtitle_core, "RUNTIME_EXPECTED_SPEAKERS", 3)
    three_speaker_signature = subtitle_core.cache_stage_signature(
        "firered_primary",
        extra={"moss": "same-recognition"},
    )

    assert two_speaker_signature != three_speaker_signature
