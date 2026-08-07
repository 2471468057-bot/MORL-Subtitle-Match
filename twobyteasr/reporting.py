"""Per-media task reports.  Reports intentionally contain no API keys or raw audio."""

import json
import os
import time
import threading
from pathlib import Path


_active_report = None
_REPORT_LOCK = threading.RLock()
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = PROJECT_ROOT / "reports"


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def report_paths_for_media(media_path):
    path = Path(media_path)
    base_name = path.stem
    return (
        str(REPORT_ROOT / f"{base_name}_字幕任务报告.json"),
        str(REPORT_ROOT / f"{base_name}_字幕任务报告.txt"),
    )


def begin_media_report(media_path, cache_context, settings):
    global _active_report
    path = Path(media_path).resolve()
    stat = path.stat()
    _active_report = {
        "schema_version": 1,
        "status": "running",
        "started_at": _now(),
        "media": {
            "name": path.name,
            "path": str(path),
            "size_bytes": int(stat.st_size),
        },
        "cache": {"directory": str(cache_context.get("cache_dir", "")), "hits": [], "writes": []},
        "settings": settings,
        "stages": [],
        "events": [],
        "review_items": [],
    }


def record_media_event(event, **payload):
    with _REPORT_LOCK:
        if _active_report is None:
            return
        row = {"time": _now(), "event": str(event), **payload}
        _active_report["events"].append(row)
        if event == "stage_started":
            _active_report["stages"].append(
                {"index": payload.get("index"), "label": payload.get("label"), "resource": payload.get("resource"), "status": "running"}
            )
        elif event in {"stage_completed", "stage_failed", "stage_cancelled"}:
            for stage in reversed(_active_report["stages"]):
                if stage.get("label") == payload.get("label") and stage.get("status") == "running":
                    stage["status"] = {
                        "stage_completed": "completed",
                        "stage_failed": "failed",
                        "stage_cancelled": "cancelled",
                    }[event]
                    stage["elapsed_seconds"] = payload.get("elapsed_seconds")
                    if event in {"stage_failed", "stage_cancelled"}:
                        stage["error"] = payload.get("error", "")
                    break
        elif event == "cache_hit":
            _active_report["cache"]["hits"].append(payload.get("stage", "unknown"))
        elif event == "cache_write":
            _active_report["cache"]["writes"].append(payload.get("stage", "unknown"))


def _write_report(report):
    json_path, text_path = report_paths_for_media(report["media"]["path"])
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    result = report.get("result", {})
    elapsed_seconds = float(result.get("elapsed_seconds", 0) or 0)
    audio_seconds = float(result.get("audio_seconds", 0) or 0)
    realtime_ratio = elapsed_seconds / audio_seconds if audio_seconds > 0 else 0.0
    performance = report.get("settings", {}).get("performance", {})
    lines = [
        "2ByteASR 字幕任务报告",
        f"状态：{report['status']}",
        f"素材：{report['media']['name']}",
        f"开始：{report['started_at']}",
        f"结束：{report.get('finished_at', '')}",
        f"耗时：{elapsed_seconds:.2f} 秒",
        f"素材时长：{audio_seconds:.2f} 秒",
        f"处理倍率：{realtime_ratio:.2f}x 实时",
        "",
        "模型：",
        f"- Qwen3-ASR：{report['settings']['models']['qwen_asr_model']}",
        f"- 字幕校对：{report['settings']['models']['polish_model']}",
        f"- 全文断句：{report['settings']['models']['group_model']}",
        "",
        "加速配置：",
        f"- 云端批次：{'并行' if performance.get('parallel_cloud_batches') else '串行'}，"
        f"最多 {performance.get('cloud_batch_workers', 1)} 路",
        f"- MOSS/VAD：{'并行' if performance.get('parallel_cpu_vad') else '串行'}",
        f"- MOSS 长音频分块：最多 {performance.get('moss_parallel_workers', 1)} 路，"
        f"显存门槛 {performance.get('moss_parallel_min_vram_gb', 0)} GB",
        f"- Qwen3-ASR：每批最多 {performance.get('qwen_asr_batch_size', 4)} 个短块",
        f"- FireRed/Qwen3 GPU：{'允许并行' if performance.get('parallel_gpu_asr') else '串行'}，"
        f"显存门槛 {performance.get('parallel_gpu_asr_min_vram_gb', 0)} GB",
        "",
        f"缓存命中：{', '.join(report['cache']['hits']) or '无'}",
        f"缓存写入：{', '.join(report['cache']['writes']) or '无'}",
        "",
        "阶段：",
    ]
    for stage in report["stages"]:
        lines.append(f"- {stage.get('index')}. {stage.get('label')}：{stage.get('status')}（{stage.get('elapsed_seconds', 0)} 秒）")
    mapping_events = [
        event
        for event in report["events"]
        if event.get("event") == "host_voiceprint_mapping"
    ]
    if mapping_events:
        lines.extend(["", "声纹标签合并："])
        for source, info in mapping_events[-1].get("assignments", {}).items():
            lines.append(
                f"- {source} -> {info.get('label')} {info.get('name')} "
                f"（相似度 {info.get('score')}，余量 {info.get('margin')}）"
            )
    if report["status"] == "success":
        correction_count = sum(
            len(event.get("edits", []))
            for event in report["events"]
            if event.get("event") == "cloud_correction_applied"
        )
        term_started = [
            event for event in report["events"]
            if event.get("event") == "domain_term_search_started"
        ]
        term_completed = [
            event for event in report["events"]
            if event.get("event") == "domain_term_search_completed"
        ]
        term_failed = [
            event for event in report["events"]
            if event.get("event") == "domain_term_search_failed"
        ]
        term_applied = sum(
            int(event.get("count", 0) or 0)
            for event in report["events"]
            if event.get("event") in {
                "domain_term_mapping_applied",
                "profile_term_mapping_applied",
            }
        )
        if term_completed:
            term_status = (
                f"已检索 {term_started[-1].get('candidate_count', 0)} 条候选，"
                f"采纳 {term_completed[-1].get('accepted_count', 0)} 组，"
                f"实际应用 {term_applied} 处"
            )
        elif term_failed:
            term_status = "联网检索失败，未自动修改专名（详情见 JSON 报告）"
        elif (
            report.get("settings", {}).get("content_profile", {}).get("domain_terms")
            and "polished" in report.get("cache", {}).get("hits", [])
        ):
            term_status = "命中校对缓存，沿用上次已核验术语结果"
        else:
            term_status = "未执行或没有可检索正文"
        lines.extend([
            "",
            f"字幕条数：{result.get('cue_count', 0)}",
            f"已采纳云端校对：{correction_count} 处（具体内容见 JSON 报告）",
            f"联网术语：{term_status}",
            f"待复核项：{len(report.get('review_items', []))}",
            f"TXT：{result.get('outputs', {}).get('txt', '')}",
            f"SRT：{result.get('outputs', {}).get('srt', '')}",
        ])
    else:
        lines.extend(["", f"错误：{result.get('error', '')}"])
    Path(text_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, text_path


def finish_media_report(status, **result):
    global _active_report
    if _active_report is None:
        return "", ""
    review_items = result.pop("review_items", [])
    _active_report["status"] = status
    _active_report["finished_at"] = _now()
    _active_report["result"] = result
    _active_report["review_items"] = list(review_items or [])
    report = _active_report
    report["stages"].sort(key=lambda stage: (int(stage.get("index") or 0), stage.get("label", "")))
    _active_report = None
    try:
        return _write_report(report)
    except OSError:
        # A report must never turn a successfully generated subtitle into a failure.
        return "", ""


def active_media_report():
    return _active_report
