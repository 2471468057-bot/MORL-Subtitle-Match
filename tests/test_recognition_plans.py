from pathlib import Path

from twobyteasr.recognition_plans import (
    lightweight_media_profile,
    matching_plan,
    recognition_plan,
)


def test_quality_plan_maps_to_independent_primary_timeline_and_review():
    plan = recognition_plan("quality")
    assert (plan.primary, plan.timeline, plan.review) == ("moss", "local", "local")
    assert matching_plan("moss", "local", "local") == "quality"


def test_unknown_backend_combination_is_custom():
    assert matching_plan("firered_llm", "qwen_aligner", "api") == "custom"
    assert recognition_plan("stale-setting").key == "custom"


def test_lightweight_profile_recommends_speed_for_small_audio(tmp_path):
    audio = Path(tmp_path) / "sample.wav"
    audio.write_bytes(b"0" * 1024)
    profile = lightweight_media_profile([audio])
    assert profile["audio_only"] is True
    assert profile["recommended_plan"] == "speed"


def test_lightweight_profile_recommends_low_memory_for_large_batch(tmp_path):
    paths = []
    for index in range(5):
        path = Path(tmp_path) / f"sample-{index}.mp4"
        path.write_bytes(b"0")
        paths.append(path)
    assert lightweight_media_profile(paths)["recommended_plan"] == "low_memory"
