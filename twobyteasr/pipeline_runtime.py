"""Reusable orchestration helpers for the media pipeline.

This module deliberately contains no ASR or subtitle-editing rules.  It owns the
thread coordination, final-stage call order, and transactional hand-off only.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from twobyteasr.runtime import get_runtime_context
from twobyteasr.segmentation import merge_split_interjections_in_cues


def run_parallel_stages(legacy, runners, *, thread_name_prefix):
    """Run named stage callables and merge their thread-local review items."""

    def captured(runner):
        with legacy.capture_review_items() as review_items:
            value = runner()
        return value, review_items

    results = {}
    reviews = []
    with ThreadPoolExecutor(
        max_workers=len(runners), thread_name_prefix=thread_name_prefix
    ) as pool:
        futures = {
            name: pool.submit(captured, runner) for name, runner in runners.items()
        }
        # Preserve caller order in logs and deterministic review aggregation.
        for name, future in futures.items():
            value, stage_reviews = future.result()
            results[name] = value
            reviews.extend(stage_reviews)
    legacy.extend_review_items(reviews)
    return results


def finalize_cues(
    cues,
    segments,
    firered_tokens,
    speech_regions,
    audio_seconds,
    timeline_fps,
    legacy,
):
    """Apply the established final timing and conservation sequence unchanged."""
    # 语气词防拆：成片前把“哎 呦”等白名单拆分形态合并回“哎呦”
    # （与人工校对稿一致；组合不在白名单的保持原样）
    cues = merge_split_interjections_in_cues(cues)
    finalized = legacy.repair_overlong_cues_from_source(
        cues,
        segments,
        firered_tokens,
    )
    finalized = legacy.normalize_cue_times(finalized, timeline_fps)
    text_differences = legacy.final_text_conservation_differences(
        finalized,
        segments,
    )
    if text_differences:
        print(
            "   [文字守恒自愈] 云端断句/超限恢复发生调序，"
            "回退到本地源段重建；不会重新请求云端模型。"
        )
        legacy.record_run_event(
            "final_text_conservation_recovery",
            differences=text_differences,
            previous_cue_count=len(finalized),
        )
        finalized = legacy.build_local_source_cues(
            segments,
            firered_tokens,
        )
        finalized = legacy.normalize_cue_times(finalized, timeline_fps)
    finalized = legacy.validate_final_cues(finalized, segments, audio_seconds)
    finalized = legacy.apply_isolated_single_character_rules_safely(finalized)
    finalized = legacy.merge_consecutive_short_repeated_cues(finalized)
    finalized = legacy.snap_cue_starts_to_vad_onsets(
        finalized,
        speech_regions,
        timeline_fps,
    )
    finalized = legacy.extend_cue_tails_by_speaker(
        finalized,
        audio_seconds,
        timeline_fps,
    )
    finalized = legacy.bridge_short_display_gaps(
        finalized,
        audio_seconds,
        timeline_fps,
    )
    finalized = legacy.validate_final_cues(
        finalized,
        segments,
        audio_seconds,
        validate_text=False,
    )
    legacy.collect_review_items(
        segments,
        finalized,
        speech_regions,
        firered_tokens,
    )
    return finalized


def complete_media_run(
    *,
    cues,
    segments,
    file_index,
    file_total,
    started,
    audio_seconds,
    txt_path,
    srt_path,
    stage_index,
    stage_total,
    legacy,
    runtime_context=None,
):
    """Write outputs transactionally, finish the report, and return public paths."""
    review_items = legacy.print_review_summary()
    runtime_context = runtime_context or get_runtime_context()
    output_details = {}

    def write_all_outputs():
        output_details.update(
            legacy.write_all_outputs_transactional(
                cues,
                txt_path,
                srt_path,
                include_review_track=runtime_context.output_review_track,
            )
        )

    legacy.run_timed_stage(
        stage_index,
        stage_total,
        "写入剪映文稿、总SRT与分轨SRT",
        "磁盘",
        write_all_outputs,
    )
    elapsed = time.perf_counter() - started
    report_json_path, report_text_path = legacy.finish_media_report(
        "success",
        elapsed_seconds=round(elapsed, 3),
        audio_seconds=round(audio_seconds, 3),
        cue_count=len(cues),
        segment_count=len(segments),
        review_items=review_items,
        outputs={
            "txt": txt_path,
            "srt": srt_path,
            **output_details,
        },
    )
    print(
        f"\n[文件完成 {file_index}/{file_total}] {legacy.format_elapsed(elapsed)}"
        f"\n   {txt_path}\n   {srt_path}"
    )
    if report_text_path:
        print(f"   任务报告：{report_text_path}\n   结构化报告：{report_json_path}")
    return txt_path, srt_path, elapsed
