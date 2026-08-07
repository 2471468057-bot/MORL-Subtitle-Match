from types import SimpleNamespace

import moss_firered_pipeline as pipeline


def _segment(speaker, start, text="主播发言"):
    return {
        "speaker": speaker,
        "start": float(start),
        "end": float(start + 1.0),
        "text": text,
    }


def test_manual_three_speakers_selects_three_even_if_third_is_sparse():
    rows = []
    rows.extend(_segment("S01", value) for value in (0, 60, 120, 180))
    rows.extend(_segment("S02", value) for value in (10, 70, 130, 190))
    rows.append(_segment("S03", 200, "第三位主播短暂加入"))
    legacy = SimpleNamespace(
        RUNTIME_EXPECTED_SPEAKERS=3,
        content_only=lambda text: text,
        add_review_item=lambda *args, **kwargs: None,
    )

    selected = pipeline.select_host_speakers(rows, 240.0, legacy)

    assert selected == ["S01", "S02", "S03"]


def test_auto_mode_keeps_three_stable_hosts_but_rejects_one_off_voice():
    rows = []
    for speaker, offset in (("S01", 0), ("S02", 5), ("S03", 10)):
        rows.extend(
            _segment(speaker, minute * 60 + offset)
            for minute in range(5)
        )
    rows.append(_segment("S04", 125, "一次性角色声"))
    legacy = SimpleNamespace(
        RUNTIME_EXPECTED_SPEAKERS=0,
        content_only=lambda text: text,
        add_review_item=lambda *args, **kwargs: None,
    )

    selected = pipeline.select_host_speakers(rows, 300.0, legacy)

    assert set(selected) == {"S01", "S02", "S03"}
