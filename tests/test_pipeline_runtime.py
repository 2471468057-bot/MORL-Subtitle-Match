from contextlib import contextmanager
import threading

from twobyteasr.pipeline_runtime import finalize_cues, run_parallel_stages


class _ParallelLegacy:
    def __init__(self):
        self.items = []
        self.local = threading.local()

    @contextmanager
    def capture_review_items(self):
        bucket = []
        self.local.current = bucket
        try:
            yield bucket
        finally:
            self.local.current = None

    def extend_review_items(self, rows):
        self.items.extend(rows)


def test_parallel_stage_results_and_reviews_keep_declared_order():
    legacy = _ParallelLegacy()

    def stage(label):
        legacy.local.current.append(label)
        return label.upper()

    results = run_parallel_stages(
        legacy,
        {"first": lambda: stage("first"), "second": lambda: stage("second")},
        thread_name_prefix="test",
    )

    assert results == {"first": "FIRST", "second": "SECOND"}
    assert legacy.items == ["first", "second"]


class _FinalizeLegacy:
    def __init__(self):
        self.calls = []

    def _same(self, name, cues, *_args, **_kwargs):
        self.calls.append(name)
        return cues

    def repair_overlong_cues_from_source(self, cues, *_args):
        return self._same("repair", cues)

    def normalize_cue_times(self, cues, *_args):
        return self._same("normalize", cues)

    def final_text_conservation_differences(self, *_args):
        self.calls.append("conservation")
        return []

    def validate_final_cues(self, cues, *_args, **_kwargs):
        return self._same("validate", cues)

    def apply_isolated_single_character_rules_safely(self, cues):
        return self._same("single_character", cues)

    def merge_consecutive_short_repeated_cues(self, cues):
        return self._same("repeat_merge", cues)

    def snap_cue_starts_to_vad_onsets(self, cues, *_args):
        return self._same("vad_onset", cues)

    def extend_cue_tails_by_speaker(self, cues, *_args):
        return self._same("speaker_tail", cues)

    def bridge_short_display_gaps(self, cues, *_args):
        return self._same("display_gap", cues)

    def collect_review_items(self, *_args):
        self.calls.append("reviews")


def test_finalize_cues_preserves_the_established_stage_order():
    legacy = _FinalizeLegacy()
    cues = [object()]
    assert finalize_cues(cues, [], [], [], 10.0, 60.0, legacy) is cues
    assert legacy.calls == [
        "repair",
        "normalize",
        "conservation",
        "validate",
        "single_character",
        "repeat_merge",
        "repair",
        "normalize",
        "vad_onset",
        "speaker_tail",
        "display_gap",
        "validate",
        "reviews",
    ]
