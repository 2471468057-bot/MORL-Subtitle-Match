"""output stage implementation extracted from subtitle_core."""

# The core owns runtime configuration; these imports preserve the existing public contract.
from subtitle_core import *  # noqa: F401,F403
from twobyteasr.runtime import get_runtime_context

__all__ = [
    'format_review_time',
    'print_review_summary',
    'add_safe_punctuation',
    'final_text_conservation_differences',
    'validate_final_cues',
    'format_srt_time',
    'render_txt',
    'render_srt',
    'build_single_lane_cues',
    'build_review_track_cues',
    '_safe_existing_track_paths',
    'write_all_outputs_transactional',
]

def format_review_time(seconds):
    total_seconds = max(0, int(round(float(seconds))))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def print_review_summary():
    deduplicated = {}
    for item in get_runtime_context().review_items:
        key = (
            item.get("category", ""),
            round(float(item.get("timestamp", 0.0)) * 2),
            content_only(item.get("text", "")),
        )
        previous = deduplicated.get(key)
        if previous is None or int(item.get("priority", 0)) > int(
            previous.get("priority", 0)
        ):
            deduplicated[key] = item
    items = sorted(
        deduplicated.values(),
        key=lambda item: (-int(item.get("priority", 0)), float(item["timestamp"])),
    )
    print("\n[建议复核时间点]")
    if not items:
        print("   未发现明显异常，可直接导入剪映抽查。")
        return []
    shown = items[:REVIEW_MAX_ITEMS]
    for item in shown:
        text = item.get("text", "")
        suffix = f"｜{text}" if text else ""
        print(
            f"   {format_review_time(item['timestamp'])} "
            f"[{item['category']}] {item['detail']}{suffix}"
        )
    if len(items) > len(shown):
        print(f"   ……另有 {len(items) - len(shown)} 条低优先级提示未展开。")
    return shown


def add_safe_punctuation(cues):
    """最终稿不再猜测问句；移除 ASR/Qwen 自动推断的问号。"""
    for cue in cues:
        text = clean_subtitle_text(cue.text)
        cue.text = text.replace("?", "").replace("？", "")
    return cues


def final_text_conservation_differences(cues, segments):
    """Return precise per-speaker text differences without weakening validation."""
    source_by_speaker = {}
    output_by_speaker = {}
    for segment in segments:
        source_by_speaker.setdefault(segment.speaker or "S00", []).append(segment.text)
    for cue in cues:
        output_by_speaker.setdefault(cue.speaker or "S00", []).append(cue.text)
    source_by_speaker = {
        speaker: content_only("".join(texts))
        for speaker, texts in source_by_speaker.items()
    }
    output_by_speaker = {
        speaker: content_only("".join(texts))
        for speaker, texts in output_by_speaker.items()
    }
    differences = []
    for speaker in sorted(set(source_by_speaker) | set(output_by_speaker)):
        expected = source_by_speaker.get(speaker, "")
        actual = output_by_speaker.get(speaker, "")
        if expected == actual:
            continue
        matcher = SequenceMatcher(None, expected, actual, autojunk=False)
        first = next(
            (
                (tag, left_start, left_end, right_start, right_end)
                for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes()
                if tag != "equal"
            ),
            ("unknown", 0, min(12, len(expected)), 0, min(12, len(actual))),
        )
        tag, left_start, left_end, right_start, right_end = first
        differences.append(
            {
                "speaker": speaker,
                "expected_length": len(expected),
                "actual_length": len(actual),
                "operation": tag,
                "expected_excerpt": expected[max(0, left_start - 8) : left_end + 8],
                "actual_excerpt": actual[max(0, right_start - 8) : right_end + 8],
            }
        )
    return differences


def validate_final_cues(cues, segments, audio_seconds, validate_text=True):
    if not cues:
        raise RuntimeError("断句后没有可用字幕。")
    source_content = content_only("".join(segment.text for segment in segments))
    output_content = content_only("".join(cue.text for cue in cues))
    if validate_text:
        # Always verify each track. A speaker swap can leave the global joined
        # text unchanged while silently putting words on the wrong output track.
        differences = final_text_conservation_differences(cues, segments)
        if differences:
            sample = differences[0]
            raise RuntimeError(
                "最终字幕出现漏字、重复或调序，已停止写入："
                f"{sample['speaker']} 源文 {sample['expected_length']} 字/"
                f"输出 {sample['actual_length']} 字，首处差异 "
                f"{sample['expected_excerpt']!r} -> {sample['actual_excerpt']!r}。"
            )
        if source_content != output_content:
            # 不同说话人真实重叠时，按时间排序会把 A 的后半句放到 B 的接话之后；
            # 全局字符串顺序因此变化，但每位说话人的文字仍应逐字完整且有序。
            print("   [重叠保护] 全局时间顺序发生说话人交错，但各说话人文字逐字完整。")

    lengths = [display_length(cue.text) for cue in cues]
    durations = [cue.end - cue.start for cue in cues]
    invalid = [
        cue
        for cue in cues
        if display_length(cue.text) > COMPLETE_PHRASE_SOFT_MAX_CHARS
        or cue.end - cue.start > MAX_SUBTITLE_SECONDS + 0.05
        or cue.end <= cue.start
    ]
    if invalid:
        sample = "、".join(
            f"{cue.text}({display_length(cue.text)}字/{cue.end - cue.start:.2f}s)"
            for cue in invalid[:6]
        )
        raise RuntimeError(f"最终字幕超过硬性长度/时长上限：{sample}")
    within_preferred = (
        sum(length <= PREFERRED_MAX_SUBTITLE_CHARS for length in lengths) / len(lengths)
    )
    within_limit = sum(length <= MAX_SUBTITLE_CHARS for length in lengths) / len(lengths)
    print(
        f"[完成] 断句：{len(cues)} 条，中位 {median(lengths):.0f} 字/"
        f"{median(durations):.2f} 秒，{within_preferred:.0%} 不超过 "
        f"{PREFERRED_MAX_SUBTITLE_CHARS} 字，{within_limit:.0%} 不超过硬上限 "
        f"{MAX_SUBTITLE_CHARS} 字。"
    )
    if within_preferred < 0.8:
        print("   [警告] 本次长字幕比例偏高，建议抽查现场噪声较重的区段。")
    last_end = max(cue.end for cue in cues)
    if audio_seconds - last_end > 8.0:
        print("   [警告] 最后一条字幕距离音频结尾超过 8 秒，请抽查尾部。")
    return cues


def format_srt_time(seconds):
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def render_txt(cues):
    return "\n".join(format_subtitle_display_text(cue.text) for cue in cues) + "\n"


def render_srt(cues):
    blocks = []
    for index, cue in enumerate(cues, 1):
        text = format_subtitle_display_text(cue.text)
        if SHOW_SPEAKER_LABELS_IN_SRT and cue.speaker:
            text = f"[{cue.speaker}] {text}"
        blocks.append(
            f"{index}\n"
            f"{format_srt_time(cue.start)} --> {format_srt_time(cue.end)}\n"
            f"{text}"
        )
    return "\n\n".join(blocks) + "\n"


def build_single_lane_cues(cues):
    """Return a non-overlapping copy for the combined SRT only.

    Speaker tracks retain real simultaneous speech.  The combined SRT is one
    editorial lane, so a 200 ms display tail from one speaker must not overlap
    the next speaker and make NLE import look like a shifted timeline.
    """
    rows = [
        SubtitleCue(
            cue_id=cue.cue_id,
            start=float(cue.start),
            end=float(cue.end),
            text=cue.text,
            timing_locked=bool(cue.timing_locked),
            speaker=cue.speaker,
        )
        for cue in cues
    ]
    rows.sort(key=lambda cue: (cue.start, cue.end, cue.speaker or "", cue.cue_id))
    adjusted = 0
    for previous, current in zip(rows, rows[1:]):
        if previous.end <= current.start or previous.speaker == current.speaker:
            continue
        lower = previous.start + MIN_SUBTITLE_SECONDS
        upper = current.end - MIN_SUBTITLE_SECONDS
        if lower > upper:
            continue
        boundary = min(max(current.start, lower), upper)
        if boundary < previous.end or boundary > current.start:
            previous.end = boundary
            current.start = boundary
            adjusted += 1
    for cue_id, cue in enumerate(rows, 1):
        cue.cue_id = cue_id
    if adjusted:
        print(
            f"   [总轨时间轴] 修正 {adjusted} 处跨主播显示重叠；"
            "主播分轨仍保留真实抢话。"
        )
        record_run_event("single_lane_overlap_repair", adjusted=adjusted)
    return rows


def build_review_track_cues(review_items=None):
    """把高风险时间点做成独立审核轨；它从不回写主字幕。"""
    review_items = (
        review_items
        if review_items is not None
        else get_runtime_context().review_items
    )
    categories = {
        "MOSS提前结束",
        "MOSS漏段",
        "FireRed漏段",
        "低置信度",
        "ASR分歧",
        "多模型争议",
        "Qwen骨架缺口",
        "孤立实义单字",
        "边界待看",
    }
    deduplicated = {}
    for item in review_items:
        if item.get("category") not in categories:
            continue
        timestamp = max(0.0, float(item.get("timestamp", 0.0)))
        text = clean_subtitle_text(item.get("text", ""))
        if not text:
            text = "请听原音复核"
        label = f"【{item.get('category')}】{text}"
        key = (round(timestamp * 2), label)
        deduplicated[key] = SubtitleCue(
            cue_id=0,
            start=max(0.0, timestamp - 0.30),
            end=timestamp + 3.00,
            text=label,
            speaker="REVIEW",
        )
    rows = sorted(deduplicated.values(), key=lambda cue: (cue.start, cue.end))
    for cue_id, cue in enumerate(rows, 1):
        cue.cue_id = cue_id
    return rows[:REVIEW_MAX_ITEMS]


def _safe_existing_track_paths(srt_path):
    """只枚举同一素材、同一目录下由本程序命名的分轨文件。"""
    directory = os.path.dirname(os.path.abspath(srt_path))
    base, extension = os.path.splitext(os.path.basename(srt_path))
    prefix = base + "_主播"
    result = []
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    for name in names:
        if name.startswith(prefix) and name.endswith(extension):
            path = os.path.abspath(os.path.join(directory, name))
            if os.path.dirname(path) == directory:
                result.append(path)
    return result


def write_all_outputs_transactional(
    cues,
    txt_path,
    srt_path,
    include_review_track=False,
):
    """先完整生成所有文件，再统一替换；失败时恢复本批写入前版本。"""
    speaker_order = []
    for cue in cues:
        speaker = cue.speaker or "S00"
        if speaker not in speaker_order:
            speaker_order.append(speaker)
    base, extension = os.path.splitext(srt_path)
    speaker_outputs = []
    single_lane_cues = build_single_lane_cues(cues)
    payloads = {
        os.path.abspath(txt_path): (render_txt(cues), "utf-8"),
        os.path.abspath(srt_path): (render_srt(single_lane_cues), "utf-8-sig"),
    }
    for index, speaker in enumerate(speaker_order, 1):
        speaker_cues = [cue for cue in cues if (cue.speaker or "S00") == speaker]
        if not speaker_cues:
            continue
        path = os.path.abspath(f"{base}_主播{index}_{speaker}{extension}")
        payloads[path] = (render_srt(speaker_cues), "utf-8-sig")
        speaker_outputs.append((speaker, path, len(speaker_cues)))

    legacy_review_path = os.path.abspath(f"{base}_疑似吞字幕复核{extension}")
    review_root = os.path.join(SCRIPT_DIR, "review_tracks")
    review_name = os.path.basename(base) + "_疑似吞字幕复核" + extension
    review_path = os.path.abspath(os.path.join(review_root, review_name))
    review_cues = build_review_track_cues() if include_review_track else []
    if review_cues:
        payloads[review_path] = (render_srt(review_cues), "utf-8-sig")

    transaction_id = uuid.uuid4().hex
    temporary_paths = {}
    backup_paths = {}
    replaced = []
    try:
        for path, (content, encoding) in payloads.items():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            temporary = f"{path}.{transaction_id}.tmp"
            with open(temporary, "w", encoding=encoding) as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            temporary_paths[path] = temporary
            if os.path.isfile(path):
                backup = f"{path}.{transaction_id}.bak"
                shutil.copy2(path, backup)
                backup_paths[path] = backup

        for path, temporary in temporary_paths.items():
            os.replace(temporary, path)
            replaced.append(path)

        expected_tracks = {
            path for _, path, _ in speaker_outputs
        }
        for stale in _safe_existing_track_paths(srt_path):
            if stale not in expected_tracks:
                try:
                    os.remove(stale)
                    print(f"   [清理旧分轨] {stale}")
                except OSError as exc:
                    print(f"   [警告] 旧分轨暂时无法清理：{stale}（{exc}）")
        stale_review_paths = [legacy_review_path]
        if not review_cues:
            stale_review_paths.append(review_path)
        for stale_review_path in dict.fromkeys(stale_review_paths):
            if stale_review_path == review_path and review_cues:
                continue
            if os.path.isfile(stale_review_path):
                try:
                    os.remove(stale_review_path)
                    print(f"   [清理旧复核轨] {stale_review_path}")
                except OSError as exc:
                    print(f"   [警告] 旧复核轨暂时无法清理：{stale_review_path}（{exc}）")
    except Exception:
        for path in reversed(replaced):
            backup = backup_paths.get(path)
            if backup and os.path.isfile(backup):
                os.replace(backup, path)
            elif os.path.isfile(path):
                os.remove(path)
        raise
    finally:
        for path in list(temporary_paths.values()) + list(backup_paths.values()):
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    print("   [说话人分轨SRT]")
    for speaker, path, count in speaker_outputs:
        print(f"      {speaker}：{count} 条 -> {path}")
    if review_cues:
        print(f"   [疑似吞字幕复核轨] {len(review_cues)} 条 -> {review_path}")
    return {
        "speaker_outputs": speaker_outputs,
        "review_path": review_path if review_cues else "",
    }


import subtitle_core as _core
for _name in __all__:
    setattr(_core, _name, globals()[_name])
del _core, _name




