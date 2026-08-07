"""Headless queue orchestration shared by the current Tk and future Qt UI."""

from __future__ import annotations

import glob
import inspect
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from twobyteasr.runtime import (
    RuntimeContext,
    activate_runtime_context,
    sync_legacy_runtime,
)


EventSink = Callable[["PipelineEvent"], None]


class CancelledError(RuntimeError):
    """Raised at a safe pipeline boundary after cancellation is requested."""


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise CancelledError("任务已取消。")


@dataclass(frozen=True)
class RunOptions:
    content_name: str = ""
    enable_domain_terms: bool = False
    output_review_track: bool = False
    force_refresh_polish: bool = False
    force_refresh_group: bool = False
    expected_speakers: int = 0
    overwrite_policy: str = "overwrite"

    def __post_init__(self) -> None:
        if not 0 <= self.expected_speakers <= 6:
            raise ValueError("expected_speakers 只能是 0（自动）或 1 到 6")
        if self.overwrite_policy not in {"overwrite", "skip", "error"}:
            raise ValueError("overwrite_policy 只能是 overwrite、skip 或 error")

    @classmethod
    def from_legacy(cls, legacy: Any, *, overwrite_policy: str = "overwrite") -> "RunOptions":
        return cls(
            content_name=str(getattr(legacy, "RUNTIME_GAME_NAME", "") or ""),
            enable_domain_terms=bool(getattr(legacy, "RUNTIME_ENABLE_DOMAIN_TERMS", False)),
            output_review_track=bool(getattr(legacy, "RUNTIME_OUTPUT_REVIEW_TRACK", False)),
            force_refresh_polish=bool(getattr(legacy, "RUNTIME_FORCE_REFRESH_POLISH_CACHE", False)),
            force_refresh_group=bool(getattr(legacy, "RUNTIME_FORCE_REFRESH_GROUP_CACHE", False)),
            expected_speakers=int(getattr(legacy, "RUNTIME_EXPECTED_SPEAKERS", 0) or 0),
            overwrite_policy=overwrite_policy,
        )

    def create_runtime_context(
        self,
        legacy: Any,
        *,
        cancellation_token: Any | None = None,
    ) -> RuntimeContext:
        canonicalize = getattr(legacy, "canonicalize_runtime_game_name", str)
        content_name = canonicalize(self.content_name)
        return RuntimeContext(
            game_name=content_name,
            enable_domain_terms=bool(content_name and self.enable_domain_terms),
            output_review_track=bool(self.output_review_track),
            force_refresh_api_cache=False,
            force_refresh_polish_cache=bool(self.force_refresh_polish),
            force_refresh_group_cache=bool(self.force_refresh_group),
            expected_speakers=int(self.expected_speakers),
            cancellation_token=cancellation_token,
        )

    def apply(
        self,
        legacy: Any,
        runtime_context: RuntimeContext | None = None,
    ) -> RuntimeContext:
        context = runtime_context or self.create_runtime_context(legacy)
        configured = self.create_runtime_context(
            legacy,
            cancellation_token=context.cancellation_token,
        )
        context.game_name = configured.game_name
        context.enable_domain_terms = configured.enable_domain_terms
        context.discovered_terms.clear()
        context.output_review_track = configured.output_review_track
        context.force_refresh_api_cache = configured.force_refresh_api_cache
        context.force_refresh_polish_cache = configured.force_refresh_polish_cache
        context.force_refresh_group_cache = configured.force_refresh_group_cache
        context.expected_speakers = configured.expected_speakers
        context.event_log_path = ""
        context.review_items.clear()
        sync_legacy_runtime(legacy, context)
        return context


@dataclass(frozen=True)
class PipelineEvent:
    kind: str
    timestamp: str
    media_path: str = ""
    media_index: int = 0
    media_total: int = 0
    stage_index: int = 0
    stage_total: int = 0
    label: str = ""
    resource: str = ""
    elapsed_seconds: float = 0.0
    message: str = ""
    output_path: str = ""
    error: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MediaResult:
    media_path: str
    status: str
    txt_path: str = ""
    srt_path: str = ""
    speaker_paths: tuple[str, ...] = ()
    review_path: str = ""
    report_json_path: str = ""
    report_text_path: str = ""
    elapsed_seconds: float = 0.0
    error: str = ""


@dataclass(frozen=True)
class QueueResult:
    results: tuple[MediaResult, ...]
    elapsed_seconds: float
    log_path: str = ""

    @property
    def successes(self) -> tuple[MediaResult, ...]:
        return tuple(item for item in self.results if item.status == "success")

    @property
    def failures(self) -> tuple[MediaResult, ...]:
        return tuple(item for item in self.results if item.status == "failed")

    @property
    def cancelled(self) -> tuple[MediaResult, ...]:
        return tuple(item for item in self.results if item.status == "cancelled")

    @property
    def skipped(self) -> tuple[MediaResult, ...]:
        return tuple(item for item in self.results if item.status == "skipped")

    @property
    def exit_code(self) -> int:
        if self.failures:
            return 1
        return 2 if self.cancelled else 0

    def legacy_successes(self) -> list[tuple[str, str, str]]:
        return [(item.media_path, item.txt_path, item.srt_path) for item in self.successes]

    def legacy_failures(self) -> list[tuple[str, str]]:
        return [(item.media_path, item.error) for item in (*self.failures, *self.cancelled)]


def _event_from_payload(kind: str, payload: dict[str, Any], state: dict[str, Any]) -> PipelineEvent:
    output_path = str(payload.get("path") or payload.get("output_path") or "")
    return PipelineEvent(
        kind=str(kind),
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        media_path=str(payload.get("media_path") or state.get("media_path") or ""),
        media_index=int(payload.get("media_index") or state.get("media_index") or 0),
        media_total=int(payload.get("media_total") or state.get("media_total") or 0),
        stage_index=int(payload.get("index") or payload.get("stage_index") or 0),
        stage_total=int(payload.get("total") or payload.get("stage_total") or 0),
        label=str(payload.get("label") or ""),
        resource=str(payload.get("resource") or ""),
        elapsed_seconds=float(payload.get("elapsed_seconds") or 0.0),
        message=str(payload.get("message") or ""),
        output_path=output_path,
        error=str(payload.get("error") or ""),
        payload=dict(payload),
    )


def _existing_output(legacy: Any, media_path: str) -> bool:
    return any(os.path.exists(path) for path in legacy.output_paths_for_media(media_path))


def _result_output_details(media_path: str, srt_path: str, review_enabled: bool) -> tuple[tuple[str, ...], str]:
    base, extension = os.path.splitext(srt_path)
    speaker_paths = tuple(sorted(glob.glob(f"{glob.escape(base)}_主播*_*{glob.escape(extension)}")))
    review_path = ""
    if review_enabled:
        project_root = Path(__file__).resolve().parents[1]
        candidate = project_root / "review_tracks" / f"{Path(base).name}_疑似吞字幕复核{extension}"
        if candidate.is_file():
            review_path = str(candidate)
    return speaker_paths, review_path


def run_media_queue(
    media_paths: list[str] | tuple[str, ...],
    options: RunOptions | None = None,
    event_sink: EventSink | None = None,
    cancel_token: CancellationToken | None = None,
    *,
    _legacy: Any | None = None,
    _pipeline: Any | None = None,
    _startup_self_test: dict[str, Any] | None = None,
) -> QueueResult:
    """Run a media queue without opening UI dialogs or exiting the process."""

    if _legacy is None:
        import subtitle_core as _legacy
    if _pipeline is None:
        import moss_firered_pipeline as _pipeline

    legacy = _legacy
    pipeline = _pipeline
    token = cancel_token or CancellationToken()
    run_options = options or RunOptions.from_legacy(legacy)
    runtime_context = run_options.create_runtime_context(
        legacy,
        cancellation_token=token,
    )
    run_options.apply(legacy, runtime_context)
    runtime_scope = activate_runtime_context(runtime_context, legacy=legacy)
    runtime_scope.__enter__()
    try:
        process_media_supports_context = "runtime_context" in inspect.signature(
            pipeline.process_media
        ).parameters
    except (TypeError, ValueError):
        process_media_supports_context = False
    normalized_paths = [os.path.abspath(os.fspath(path)) for path in media_paths]
    state: dict[str, Any] = {"media_path": "", "media_index": 0, "media_total": len(normalized_paths)}

    def forward_event(kind: str, payload: dict[str, Any]) -> None:
        if event_sink is None:
            return
        event_sink(_event_from_payload(kind, payload, state))

    results: list[MediaResult] = []
    durations: list[float] = []
    queue_started = time.perf_counter()
    log_path = ""
    local_asr_session_started = False
    try:
        pipeline.set_cancellation_token(token)
        with legacy.run_event_observer(forward_event):
            startup_self_test = _startup_self_test or legacy.run_startup_self_test()
            log_path = legacy.begin_run_event_log()
            print(f"[运行日志] {log_path}")
            legacy.record_run_event(
                "queue_configured",
                media_count=len(normalized_paths),
                runtime_profile=legacy.runtime_content_profile_signature(),
                pipeline_build=getattr(pipeline, "PIPELINE_BUILD_ID", ""),
                pipeline_path=os.path.realpath(getattr(pipeline, "__file__", "")),
                core_build=getattr(legacy, "PIPELINE_BUILD_ID", ""),
                core_path=os.path.realpath(getattr(legacy, "__file__", "")),
                startup_self_test=startup_self_test,
                runtime_settings=legacy.runtime_settings_snapshot(),
            )
            if legacy.HF_TOKEN:
                os.environ["HF_TOKEN"] = legacy.HF_TOKEN
                os.environ["HUGGINGFACE_HUB_TOKEN"] = legacy.HF_TOKEN

            try:
                token.raise_if_cancelled()
                pipeline.check_runtime(legacy)
                legacy.cleanup_old_cache()
                token.raise_if_cancelled()
                try:
                    pipeline.precompute_moss_batch_cache(normalized_paths, legacy)
                except CancelledError:
                    raise
                except KeyboardInterrupt:
                    token.cancel()
                    raise CancelledError("MOSS 预计算已取消。")
                except Exception as exc:
                    print(f"   [警告] MOSS 批量预计算未完成，改为逐文件继续：{exc}")
                    legacy.record_run_event("moss_batch_fallback", error=str(exc))
                if len(normalized_paths) > 1:
                    begin_model_session = getattr(legacy, "begin_local_asr_session", None)
                    if callable(begin_model_session):
                        begin_model_session()
                        local_asr_session_started = True
                        legacy.record_run_event(
                            "local_asr_session_started",
                            media_count=len(normalized_paths),
                            models=["qwen3-asr"],
                        )
            except CancelledError as exc:
                for path in normalized_paths:
                    results.append(MediaResult(path, "cancelled", error=str(exc)))
                legacy.record_run_event("queue_cancelled", error=str(exc))
                return QueueResult(tuple(results), time.perf_counter() - queue_started, log_path)
            except Exception as exc:
                for path in normalized_paths:
                    results.append(MediaResult(path, "failed", error=str(exc)))
                legacy.record_run_event("queue_failed", error=str(exc))
                return QueueResult(tuple(results), time.perf_counter() - queue_started, log_path)

            for index, media_path in enumerate(normalized_paths, 1):
                state.update(media_path=media_path, media_index=index)
                if token.is_cancelled:
                    results.extend(
                        MediaResult(path, "cancelled", error="队列已取消。")
                        for path in normalized_paths[index - 1 :]
                    )
                    break

                if _existing_output(legacy, media_path):
                    if run_options.overwrite_policy == "skip":
                        result = MediaResult(media_path, "skipped", error="已存在字幕结果。")
                        results.append(result)
                        legacy.record_run_event("media_skipped", media_path=media_path, reason=result.error)
                        continue
                    if run_options.overwrite_policy == "error":
                        result = MediaResult(media_path, "failed", error="已存在字幕结果，覆盖策略为 error。")
                        results.append(result)
                        legacy.record_run_event("media_failed", media_path=media_path, error=result.error)
                        continue

                legacy.record_run_event(
                    "media_started",
                    media_path=media_path,
                    media_index=index,
                    media_total=len(normalized_paths),
                )
                file_started = time.perf_counter()
                try:
                    token.raise_if_cancelled()
                    process_kwargs = (
                        {"runtime_context": runtime_context}
                        if process_media_supports_context
                        else {}
                    )
                    txt_path, srt_path, elapsed = pipeline.process_media(
                        media_path,
                        index,
                        len(normalized_paths),
                        legacy,
                        **process_kwargs,
                    )
                    report_json, report_text = legacy.task_reporting.report_paths_for_media(media_path)
                    speaker_paths, review_path = _result_output_details(
                        media_path, srt_path, run_options.output_review_track
                    )
                    result = MediaResult(
                        media_path=media_path,
                        status="success",
                        txt_path=txt_path,
                        srt_path=srt_path,
                        speaker_paths=speaker_paths,
                        review_path=review_path,
                        report_json_path=report_json if os.path.isfile(report_json) else "",
                        report_text_path=report_text if os.path.isfile(report_text) else "",
                        elapsed_seconds=float(elapsed),
                    )
                    results.append(result)
                    durations.append(float(elapsed))
                    legacy.record_run_event(
                        "media_completed",
                        media_path=media_path,
                        elapsed_seconds=round(float(elapsed), 3),
                        txt_path=txt_path,
                        srt_path=srt_path,
                    )
                except CancelledError as exc:
                    elapsed = time.perf_counter() - file_started
                    legacy.finish_media_report("cancelled", elapsed_seconds=round(elapsed, 3), error=str(exc))
                    results.append(MediaResult(media_path, "cancelled", elapsed_seconds=elapsed, error=str(exc)))
                    token.cancel()
                    legacy.record_run_event("media_cancelled", media_path=media_path, error=str(exc))
                except KeyboardInterrupt:
                    elapsed = time.perf_counter() - file_started
                    token.cancel()
                    error = "用户取消了任务。"
                    legacy.finish_media_report("cancelled", elapsed_seconds=round(elapsed, 3), error=error)
                    results.append(MediaResult(media_path, "cancelled", elapsed_seconds=elapsed, error=error))
                    legacy.record_run_event("media_cancelled", media_path=media_path, error=error)
                except Exception as exc:
                    elapsed = time.perf_counter() - file_started
                    durations.append(elapsed)
                    legacy.finish_media_report("failed", elapsed_seconds=round(elapsed, 3), error=str(exc))
                    results.append(MediaResult(media_path, "failed", elapsed_seconds=elapsed, error=str(exc)))
                    print(f"\n[文件失败] {os.path.basename(media_path)}：{exc}")
                    legacy.record_run_event(
                        "media_failed",
                        media_path=media_path,
                        error=str(exc),
                        traceback=__import__("traceback").format_exc(),
                    )

                if token.is_cancelled:
                    results.extend(
                        MediaResult(path, "cancelled", error="队列已取消。")
                        for path in normalized_paths[index:]
                    )
                    break
                remaining = len(normalized_paths) - index
                if remaining and durations:
                    average = sum(durations) / len(durations)
                    print(
                        f"\n[队列进度] 已完成 {index}/{len(normalized_paths)}，"
                        f"预计剩余 {legacy.format_elapsed(average * remaining)}。"
                    )

            total_elapsed = time.perf_counter() - queue_started
            legacy.record_run_event(
                "run_completed",
                success_count=sum(item.status == "success" for item in results),
                failure_count=sum(item.status == "failed" for item in results),
                cancelled_count=sum(item.status == "cancelled" for item in results),
                skipped_count=sum(item.status == "skipped" for item in results),
                elapsed_seconds=round(total_elapsed, 3),
            )
            return QueueResult(tuple(results), total_elapsed, log_path)
    finally:
        if local_asr_session_started:
            end_model_session = getattr(legacy, "end_local_asr_session", None)
            if callable(end_model_session):
                end_model_session()
        runtime_context.cancellation_token = None
        try:
            pipeline.set_cancellation_token(None)
        finally:
            runtime_scope.__exit__(None, None, None)
