"""Cloud grouping request/response handling and subtitle grouping orchestration."""

import threading

from subtitle_core import *  # noqa: F401,F403
from twobyteasr.segmentation import (
    firered_pause_character_gaps,
    hard_break_character_offsets,
    indexed_content_for_prompt,
    individual_cue,
    locally_repair_resegmented_cue,
    merge_hanging_attribute_cues,
    merge_isolated_two_character_cues,
    merge_same_speaker_dangling_cues,
    protected_source_boundary_offsets,
    refine_resegmented_texts,
    repair_compact_utterance_boundary_offsets,
    repair_dependent_particle_boundary_offsets,
    repair_dependent_prefix_boundary_offsets,
    repair_hanging_attribute_boundary_offsets,
    repair_incomplete_boundary_offsets,
    repair_latin_predicate_boundary_offsets,
    repair_lexical_boundary_offsets,
    repair_mid_word_adjacent_cues,
    repair_segmenter_word_boundary_offsets,
    segment_content_timeline,
    semantic_restart_boundary_offsets,
    snap_boundaries_away_from_word_interiors,
    snap_internal_cue_boundaries,
    source_segment_character_offsets,
    text_boundary_hints,
    texts_from_boundary_offsets,
)

__all__ = [
    "cues_from_resegmented_texts",
    "fallback_group",
    "call_grouping_api",
    "group_subtitles",
]

def cues_from_resegmented_texts(
    segment_batch,
    proposed_texts,
    firered_tokens=(),
    speech_regions=(),
):
    source_exact = content_exact("".join(segment.text for segment in segment_batch))
    output_exact = content_exact("".join(proposed_texts))
    if output_exact != source_exact:
        raise ValueError("Qwen 重切时改动了原文字、英文大小写或顺序。")

    source_content = content_only("".join(segment.text for segment in segment_batch))
    output_content = content_only("".join(proposed_texts))
    if output_content != source_content:
        raise ValueError("Qwen 重切时改动了原文字或顺序。")

    proposed_texts = refine_resegmented_texts(
        segment_batch,
        proposed_texts,
        firered_tokens,
    )

    timeline = []
    for segment in segment_batch:
        timeline.extend(segment_content_timeline(segment, firered_tokens))
    if len(timeline) != len(source_content):
        raise ValueError("校对文字与时间单元数量不一致。")

    hard_offsets = hard_break_character_offsets(segment_batch, firered_tokens)
    real_pause_offsets = set(
        firered_pause_character_gaps(segment_batch, firered_tokens)
    )
    preferred_offsets = (
        source_segment_character_offsets(segment_batch) | real_pause_offsets
    )
    locked_ranges = []
    source_cursor = 0
    for segment in segment_batch:
        segment_length = display_length(segment.text)
        if segment.timing_locked and segment_length > 0:
            locked_ranges.append(
                (source_cursor, source_cursor + segment_length)
            )
        source_cursor += segment_length

    def span_is_timing_locked(span_start, span_end):
        return any(
            locked_start <= span_start and span_end <= locked_end
            for locked_start, locked_end in locked_ranges
        )

    cue_end_offsets = set()
    cues = []
    cursor = 0
    for proposed_text in proposed_texts:
        text = clean_subtitle_text(proposed_text)
        length = display_length(text)
        if not text or length <= 0:
            raise ValueError("Qwen 返回了空字幕。")
        units = timeline[cursor : cursor + length]
        if len(units) != length:
            raise ValueError("Qwen 重切范围超出原文。")
        start = units[0].start
        end = max(units[-1].end, start + MIN_SUBTITLE_SECONDS)

        forced_inside = {
            offset - cursor
            for offset in hard_offsets
            if cursor < offset < cursor + length
        }
        preferred_inside = {
            offset - cursor
            for offset in preferred_offsets
            if cursor < offset < cursor + length
        }
        natural_soft_inside = {
            offset - cursor
            for offset in real_pause_offsets
            if cursor < offset < cursor + length
        }
        natural_soft_inside.update(text_boundary_hints(text))
        natural_soft_inside.update(semantic_restart_boundary_offsets(text))
        repair_reasons = []
        if length > COMPLETE_PHRASE_SOFT_MAX_CHARS:
            repair_reasons.append(f"{length} 字")
        # 10 字只是观看舒适目标，不是本地硬切条件。11-16 字若 Qwen 判断语义
        # 尚未说完就保持完整，避免用均匀字时长伪造断点并造成时间轴漂移。
        if end - start > MAX_SUBTITLE_SECONDS + 0.05:
            repair_reasons.append(f"{end - start:.2f} 秒")
        if forced_inside:
            repair_reasons.append("跨真实长停顿")

        if repair_reasons:
            repaired = locally_repair_resegmented_cue(
                text,
                units,
                forced_boundaries=forced_inside,
                preferred_boundaries=preferred_inside,
            )
            summary = "/".join(
                f"{display_length(cue.text)}字 {cue.end - cue.start:.2f}秒"
                for cue in repaired
            )
            print(
                f"   [本地修复] Qwen 单条 {'+'.join(repair_reasons)} -> {summary}"
            )
            cues.extend(repaired)
            running_offset = cursor
            for cue in repaired:
                cue_start_offset = running_offset
                running_offset += display_length(cue.text)
                cue.timing_locked = span_is_timing_locked(
                    cue_start_offset,
                    running_offset,
                )
                cue_end_offsets.add(running_offset)
        else:
            cues.append(
                SubtitleCue(
                    0,
                    start,
                    end,
                    text,
                    timing_locked=span_is_timing_locked(
                        cursor,
                        cursor + length,
                    ),
                )
            )
            cue_end_offsets.add(cursor + length)
        cursor += length

    if cursor != len(timeline):
        raise ValueError("Qwen 重切未覆盖完整原文。")
    # 词中硬边界已在本地修复前贴到词边；这里同步期望的句末偏移。
    hard_offsets = set(
        snap_boundaries_away_from_word_interiors(
            "".join(clean_subtitle_text(segment.text) for segment in segment_batch),
            hard_offsets,
        )
    )
    if hard_offsets and not hard_offsets.issubset(cue_end_offsets | {len(timeline)}):
        # 最后再用相邻字幕兜底修一次；仍缺硬边界时才失败。
        cues = repair_mid_word_adjacent_cues(cues)
        cue_end_offsets = set()
        running = 0
        for cue in cues:
            running += display_length(cue.text)
            cue_end_offsets.add(running)
    if hard_offsets and not hard_offsets.issubset(cue_end_offsets | {len(timeline)}):
        raise ValueError("Qwen 重切跨过了真实长停顿。")
    cues = repair_mid_word_adjacent_cues(cues)
    cues = merge_hanging_attribute_cues(cues)
    return snap_internal_cue_boundaries(
        cues,
        segment_batch,
        firered_tokens,
        speech_regions,
    )


def fallback_group(segment_batch, firered_tokens=(), speech_regions=()):
    # A rejected/unavailable cloud model must not make the local result worse.
    # MOSS already emits phrase-level utterances close to the supplied human
    # manuscript; keep them verbatim whenever they satisfy the real hard limits.
    source_cues = [individual_cue(segment) for segment in segment_batch]
    if all(
        display_length(cue.text) <= COMPLETE_PHRASE_SOFT_MAX_CHARS
        and cue.end - cue.start <= MAX_SUBTITLE_SECONDS + 0.05
        and cue.end > cue.start
        for cue in source_cues
    ):
        return source_cues
    try:
        return cues_from_resegmented_texts(
            segment_batch,
            [segment.text for segment in segment_batch],
            firered_tokens,
            speech_regions,
        )
    except Exception:
        return [individual_cue(segment) for segment in segment_batch]


def call_grouping_api(
    segment_batch,
    protect_all_source_boundaries=False,
    protected_after_segment_ids=(),
    firered_tokens=(),
    speech_regions=(),
    abort_event=None,
):
    import requests

    if abort_event is not None and abort_event.is_set():
        add_review_item(
            segment_batch[0].start,
            "断句回退",
            "云端断句模型已在前一批次被服务端拒绝，本批保留 MOSS 原始自然语句边界",
            segment_batch[0].text,
            priority=3,
        )
        return fallback_group(segment_batch, firered_tokens, speech_regions)

    hard_break_offsets = sorted(
        hard_break_character_offsets(segment_batch, firered_tokens)
    )
    source_text = "".join(
        clean_subtitle_text(segment.text) for segment in segment_batch
    )
    total_length = display_length(source_text)
    segment_payload = []
    content_cursor = 0
    for segment in segment_batch:
        length = display_length(segment.text)
        segment_payload.append(
            {
                "id": segment.segment_id,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "content_start": content_cursor,
                "content_end": content_cursor + length,
                "text": segment.text,
            }
        )
        content_cursor += length

    source_boundary_offsets = sorted(source_segment_character_offsets(segment_batch))
    protected_source_offsets = set(
        source_segment_character_offsets(segment_batch)
        if protect_all_source_boundaries
        else protected_source_boundary_offsets(segment_batch)
    )
    protected_ids = set(protected_after_segment_ids)
    running_offset = 0
    for segment in segment_batch[:-1]:
        running_offset += display_length(segment.text)
        if segment.segment_id in protected_ids:
            protected_source_offsets.add(running_offset)
    protected_source_offsets = sorted(protected_source_offsets)
    pause_hints = [
        {"offset": offset, "gap_ms": int(round(gap * 1000))}
        for offset, gap in sorted(
            firered_pause_character_gaps(segment_batch, firered_tokens).items()
        )
    ]
    source_gap_hints = []
    running_offset = 0
    for segment, following in zip(segment_batch, segment_batch[1:]):
        running_offset += display_length(segment.text)
        gap = following.start - segment.end
        if gap >= 0.12:
            source_gap_hints.append(
                {"offset": running_offset, "gap_ms": int(round(gap * 1000))}
            )
    prompt = f"""你是中文口语视频字幕的全文断句编辑。文字已经校对完成；你只能在原文中插入竖线“|”表示换字幕，不能修改、增删或重排任何原字。

严格规则：
1. segmented_text 去掉所有“|”后，必须与 source_text 逐字一致。严禁加字、删字、改字、换序、加标点、改同音字或润色；你不是校对器，只插入“|”。
2. 先按口语含义和真实气口断句，再考虑长度。pause_hints 是 FireRed 字级气口，非常有价值，应优先参考；source_gap_hints 是原语音段之间的停顿，同样优先。但 pause 若落在完整词内部（例如“估|计”“眼|皮”“为什|么”），不得只因 pause 切开，必须改到该词前或后的完整边界。绝不能为了平均字数拆开专名或普通完整词。
3. 一条必须是听起来已经说完的完整成分。禁止让上一条停在“这、那、他、我、我们、其实、因为、所以、然后、但是、如果、可能、要、再、的、地、得、呢、把、被、给、对、从、向、和、跟、与、而、且、就、都、也、还、又”等悬空位置；也禁止让下一条以“了、着、过、的、地、得、吗、呢、吧、啊”等粘附成分单独开头。
4. 一个字幕表达一个操作、判断或反应。转折、因果、条件、操作转评价时优先换句；但主语与谓语、动词与宾语、修饰语与中心词必须留在一起。特别禁止切开：进入、藏品、接受、能力、估计、眼皮、睫毛、鸡皮疙瘩、一瞬间、生理不适、我的X我的Y 这类内部结构；也不要切成“其实我的|后文”“我对于…的接|受能力”。
5. 观看舒适度：中位数约 {PREFERRED_MAX_SUBTITLE_CHARS} 字，常见 6-10 字；单条硬上限为 {MAX_SUBTITLE_CHARS} 字和 {MAX_SUBTITLE_SECONDS} 秒，完整短语也不得超过。不要为了贴近 8 字而切开完整词或专名；接近上限且包含两个动作、判断、反应或重复重点时，应在自然语义处拆开。特别禁止：“那我们就直接进入一个｜珊瑚场啊”——应切成“那我们就直接进入｜一个珊瑚场啊”。上条不能停在“的/地/得/一个/这个/那个”后只把短中心语甩到下条。任何单字都不要单独成条；不要留下依附后文的残尾。同一条若同时出现中文口语数量和阿拉伯界面数值，优先在自然停顿或分句处拆开，避免混用。
6. hard_break_offsets 和 protected_source_offsets 是必须保留的原边界。pause_hints 与 source_gap_hints 权重高，应积极利用；仅当该气口会切开完整词、或左右都不是完整口语成分时，才改到邻近合法边界（轻度让步，不是忽略气口）。约 180-2999ms 的停顿若位于“因为、所以、应该、可能、的、要、再”等未完成成分后，可以跨过去重组；3 秒以上才必须断开，source_segment_offsets 只是参考。
7. 示例：“名次倒是不要紧现在名次都是虚的”应为“名次倒是不要紧|现在名次都是虚的”；“他这个队应该应该是首领化队”应为“他这个队|应该应该是首领化队”，不能切成“应该应|该是”；“哦耶还没到保底我就抽到了哈哈”应为“哦耶还没到保底|我就抽到了哈哈”，不能切成“我就抽到|了哈哈”；“好来就看这把ELO能不能发点力给我们排到一位小众变态阵容”应为“好来|就看这把|ELO能不能发点力|给我们排到一位|小众变态阵容”，英文缩写若与后面的“能不能/会不会/怎么/可以”等谓语连读，应放在后一条，不能提前挂在上一条末尾；“啊我我会给你这个把商城里边的这个这次的所有的衣服啊”应为“啊我我会给你这个|把商城里边的这个|这次的所有的衣服啊”，不能切开“商城”或“所有”；“所以你那边怎么突然你能想到我们能听到我们这边的BGM了”应为“所以你那边怎么突然|你能想到我们能听到|我们这边的BGM了”，不能切成“你能想到|我们能听到”；“我们血量保一下保一下后面好打一点”应为“我们血量保一下|保一下后面好打一点”；“那我们这个炮米花的血量又回上来了”应为“那我们这个|炮米花的血量|又回上来了”，所有示例都必须逐字保留。
8. 只返回 JSON，不要解释：{{"segmented_text":"原文第一条|原文第二条","boundaries":[8,17,全文总字符数]}}。segmented_text 用于确认自然语义节奏，去掉“|”后必须与 source_text 逐字一致；boundaries 是每条字幕末尾在 indexed_content 中的字符序号，必须严格递增，最后一个数字必须等于 total_length。"""
    request_body = {
        "total_length": total_length,
        "source_text": source_text,
        "indexed_content": indexed_content_for_prompt(source_text),
        "hard_break_character_offsets": hard_break_offsets,
        "source_segment_offsets": source_boundary_offsets,
        "protected_source_offsets": protected_source_offsets,
        "pause_hints": pause_hints,
        "source_gap_hints": source_gap_hints,
        "segments": segment_payload,
    }
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(request_body, ensure_ascii=False)},
    ]
    group_settings = group_llm_settings()
    validate_endpoint(group_settings, "全文断句模型")
    print(
        f"   [断句] 使用 {group_settings['model']}（禁止改字，仅插入|）"
    )
    last_error = None
    working_messages = list(messages)
    for attempt in range(1, GROUPING_API_RETRIES + 1):
        content = ""
        try:
            content = post_chat_completion(
                working_messages,
                model=group_settings["model"],
                api_key=group_settings["api_key"],
                url=group_settings["url"],
                max_tokens=min(4096, max(512, len(source_text) * 2)),
                temperature=0.0,
                timeout=(10, GROUPING_API_TIMEOUT_SECONDS),
                enable_thinking=False,
                response_format={"type": "json_object"},
            )
            returned = parse_qwen_object(content)
            boundary_offsets = returned.get("boundaries")
            segmented_text = returned.get("segmented_text")
            if isinstance(segmented_text, str) and segmented_text.strip():
                proposed_texts = [
                    clean_subtitle_text(part)
                    for part in segmented_text.split("|")
                ]
                if not proposed_texts or any(not part for part in proposed_texts):
                    raise ValueError("模型 segmented_text 含有空字幕。")
                if content_exact("".join(proposed_texts)) == content_exact(source_text):
                    # 逐字一致时，带竖线的正文最能反映模型的自然语义判断；
                    # 本地只把竖线换算为数字断点，实际正文仍从 source_text 切片。
                    boundary_offsets = []
                    running_offset = 0
                    for text in proposed_texts:
                        running_offset += display_length(text)
                        boundary_offsets.append(running_offset)
                elif not isinstance(boundary_offsets, list):
                    raise ValueError("模型插入断句线时改动了原文字或顺序。")
            elif not isinstance(boundary_offsets, list):
                raise ValueError("模型 JSON 中缺少 segmented_text 和 boundaries。")
            boundary_offsets = repair_lexical_boundary_offsets(
                segment_batch,
                boundary_offsets,
                firered_tokens,
            )
            boundary_offsets = repair_segmenter_word_boundary_offsets(
                segment_batch,
                boundary_offsets,
                firered_tokens,
            )
            boundary_offsets = repair_incomplete_boundary_offsets(
                segment_batch,
                boundary_offsets,
                protected_offsets=(
                    set(hard_break_offsets) | set(protected_source_offsets)
                ),
                firered_tokens=firered_tokens,
            )
            boundary_offsets = repair_latin_predicate_boundary_offsets(
                segment_batch,
                boundary_offsets,
                protected_offsets=(
                    set(hard_break_offsets) | set(protected_source_offsets)
                ),
                firered_tokens=firered_tokens,
            )
            boundary_offsets = repair_dependent_particle_boundary_offsets(
                segment_batch,
                boundary_offsets,
                protected_offsets=(
                    set(hard_break_offsets) | set(protected_source_offsets)
                ),
                firered_tokens=firered_tokens,
            )
            boundary_offsets = repair_hanging_attribute_boundary_offsets(
                segment_batch,
                boundary_offsets,
                protected_offsets=(
                    set(hard_break_offsets) | set(protected_source_offsets)
                ),
                firered_tokens=firered_tokens,
            )
            missing_required = sorted(
                (set(hard_break_offsets) | set(protected_source_offsets))
                - set(boundary_offsets)
            )
            if missing_required:
                # 这些边界来自真实停顿或另一位主播的插话。模型只负责语义断句，
                # 漏报时由本地精确补回即可；不能因此丢掉整批其余自然断句。
                boundary_offsets = sorted(
                    set(boundary_offsets) | set(missing_required)
                )
                print(
                    "   [边界保护] 本地补回模型漏报的 "
                    f"{len(missing_required)} 个说话人/停顿边界。"
                )
            before_validate = list(boundary_offsets)
            if SECOND_PASS_GROUP_VALIDATION:
                boundary_offsets = validate_grouping_boundaries_with_llm(
                    segment_batch,
                    boundary_offsets,
                    firered_tokens=firered_tokens,
                )
            boundary_offsets = repair_lexical_boundary_offsets(
                segment_batch,
                boundary_offsets,
                firered_tokens,
            )
            boundary_offsets = repair_segmenter_word_boundary_offsets(
                segment_batch,
                boundary_offsets,
                firered_tokens,
            )
            boundary_offsets = repair_dependent_particle_boundary_offsets(
                segment_batch,
                boundary_offsets,
                protected_offsets=(
                    set(hard_break_offsets) | set(protected_source_offsets)
                ),
                firered_tokens=firered_tokens,
            )
            boundary_offsets = repair_hanging_attribute_boundary_offsets(
                segment_batch,
                boundary_offsets,
                protected_offsets=(
                    set(hard_break_offsets) | set(protected_source_offsets)
                ),
                firered_tokens=firered_tokens,
            )
            boundary_offsets = sorted(
                set(boundary_offsets) | set(hard_break_offsets) | set(protected_source_offsets)
            )
            # hard/protected 并入后可能重新落入词中，再护栏一次。
            boundary_offsets = repair_segmenter_word_boundary_offsets(
                segment_batch,
                boundary_offsets,
                firered_tokens,
            )
            boundary_offsets = sorted(
                set(
                    snap_boundaries_away_from_word_interiors(
                        source_text,
                        boundary_offsets,
                        blocked=set(protected_source_offsets),
                    )
                )
                | set(
                    snap_boundaries_away_from_word_interiors(
                        source_text,
                        hard_break_offsets,
                    )
                )
                | set(protected_source_offsets)
            )
            boundary_offsets = repair_incomplete_boundary_offsets(
                segment_batch,
                boundary_offsets,
                protected_offsets=(
                    set(hard_break_offsets) | set(protected_source_offsets)
                ),
                firered_tokens=firered_tokens,
            )
            boundary_offsets = repair_compact_utterance_boundary_offsets(
                segment_batch,
                boundary_offsets,
                protected_offsets=(
                    set(hard_break_offsets) | set(protected_source_offsets)
                ),
                firered_tokens=firered_tokens,
            )
            boundary_offsets = repair_dependent_prefix_boundary_offsets(
                segment_batch,
                boundary_offsets,
                protected_offsets=(
                    set(hard_break_offsets) | set(protected_source_offsets)
                ),
                firered_tokens=firered_tokens,
            )
            boundary_offsets = repair_segmenter_word_boundary_offsets(
                segment_batch,
                boundary_offsets,
                firered_tokens,
            )
            if boundary_offsets and boundary_offsets[-1] != total_length:
                boundary_offsets = [offset for offset in boundary_offsets if 0 < offset < total_length] + [
                    total_length
                ]
            if before_validate != boundary_offsets:
                print("   [断句校验] 已应用云端模型竖线校正与本地护栏。")
            proposed_texts = texts_from_boundary_offsets(
                segment_batch,
                boundary_offsets,
                firered_tokens,
            )
            return cues_from_resegmented_texts(
                segment_batch,
                proposed_texts,
                firered_tokens,
                speech_regions,
            )
        except Exception as exc:
            last_error = exc
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in {400, 401, 403, 404}:
                if abort_event is not None:
                    abort_event.set()
                print(
                    f"   [警告] 云端断句配置被服务端拒绝（HTTP {status_code}），"
                    "立即保留本地自然语句边界，不再重复请求。"
                )
                break
            if attempt < GROUPING_API_RETRIES:
                if content:
                    working_messages = messages + [
                        {"role": "assistant", "content": content[:6000]},
                        {
                            "role": "user",
                            "content": (
                                f"上一次结果未通过本地校验：{exc}。"
                                "请只修正这个问题，重新返回完整 JSON。"
                            ),
                        },
                    ]
                delay = 2 ** (attempt - 1)
                print(
                    f"   [警告] 断句建议失败，{delay} 秒后重试（{attempt}/{GROUPING_API_RETRIES}）"
                )
                time.sleep(delay)

    print(f"   [警告] 断句连续失败，当前批次使用本地均衡分段：{last_error}")
    record_run_event(
        "grouping_api_fallback",
        segment_start=round(float(segment_batch[0].start), 3),
        segment_end=round(float(segment_batch[-1].end), 3),
        error=redact_runtime_secrets(last_error),
    )
    add_review_item(
        segment_batch[0].start,
        "断句回退",
        f"断句失败，已使用本地均衡分段：{str(last_error)[:120]}",
        segment_batch[0].text,
        priority=3,
    )
    return fallback_group(segment_batch, firered_tokens, speech_regions)


def group_subtitles(
    segments,
    firered_tokens=(),
    speech_regions=(),
    protect_all_source_boundaries=False,
    cache_context=None,
):
    print(
        "   云端模型阅读全稿并选择同一说话人内部的语义断点，"
        "不修改任何字幕文字..."
    )
    cues = []
    ordered_segments = sorted(
        segments,
        key=lambda item: (item.start, item.end, item.segment_id),
    )
    global_position = {
        segment.segment_id: index for index, segment in enumerate(ordered_segments)
    }
    speaker_groups = {}
    for segment in ordered_segments:
        speaker = segment.speaker or "S00"
        speaker_groups.setdefault(speaker, []).append(segment)
    interrupted_after = set()
    for speaker, speaker_segments in speaker_groups.items():
        for left, right in zip(speaker_segments, speaker_segments[1:]):
            left_index = global_position[left.segment_id]
            right_index = global_position[right.segment_id]
            if any(
                (middle.speaker or "S00") != speaker
                for middle in ordered_segments[left_index + 1 : right_index]
            ):
                interrupted_after.add(left.segment_id)
    batches = []
    for speaker, speaker_segments in speaker_groups.items():
        speaker_segments.sort(key=lambda item: (item.start, item.end, item.segment_id))
        for batch in split_items_for_api(speaker_segments):
            batches.append((speaker, batch))
    jobs = []
    grouping_abort_event = threading.Event()
    for index, (speaker, batch) in enumerate(batches, 1):
        dependency = {
            "speaker": speaker,
            "batch": serialize_segments(batch),
            "protect_all": bool(protect_all_source_boundaries),
            "protected_after": sorted(interrupted_after),
            "firered_tokens": firered_tokens,
            "speech_regions": speech_regions,
        }
        jobs.append((index, speaker, batch, dependency))

    def run_job(job):
        index, speaker, batch, dependency = job
        print(f"   断句批次 {index}/{len(batches)}，说话人 {speaker}")
        started_at = time.perf_counter()

        def run_group_batch():
            return call_grouping_api(
                batch,
                protect_all_source_boundaries=protect_all_source_boundaries,
                protected_after_segment_ids=interrupted_after,
                firered_tokens=firered_tokens,
                speech_regions=speech_regions,
                abort_event=grouping_abort_event,
            )
        with capture_review_items() as review_items:
            if cache_context is not None:
                batch_cues = run_cached_api_batch(
                    "grouped",
                    cache_context,
                    dependency,
                    run_group_batch,
                    encoder=serialize_cues,
                    decoder=deserialize_cues,
                    fallback_categories=("断句回退",),
                )
            else:
                batch_cues = run_group_batch()
        for cue in batch_cues:
            cue.speaker = speaker
        elapsed_seconds = time.perf_counter() - started_at
        record_run_event(
            "cloud_batch_completed",
            stage="grouped",
            batch_index=index,
            batch_total=len(batches),
            cue_count=len(batch),
            elapsed_seconds=round(elapsed_seconds, 3),
        )
        return index, batch_cues, review_items

    results = {}
    workers = min(CLOUD_BATCH_WORKERS, len(jobs)) if PARALLEL_CLOUD_BATCHES else 1
    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        print(f"   [并行加速] {len(jobs)} 个断句批次，最多 {workers} 路并发。")
        record_run_event(
            "cloud_batches_parallel",
            stage="grouped",
            batches=len(jobs),
            workers=workers,
        )
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="glm-group") as pool:
            futures = {pool.submit(run_job, job): job[0] for job in jobs}
            for future in as_completed(futures):
                index, batch_cues, review_items = future.result()
                results[index] = batch_cues
                extend_review_items(review_items)
    else:
        for job in jobs:
            index, batch_cues, review_items = run_job(job)
            results[index] = batch_cues
            extend_review_items(review_items)
    for index in sorted(results):
        cues.extend(results[index])
    cues = merge_same_speaker_dangling_cues(cues)
    cues = merge_isolated_two_character_cues(cues)
    cues = repair_mid_word_adjacent_cues(cues)
    cues = merge_hanging_attribute_cues(cues)
    cues.sort(key=lambda cue: (cue.start, cue.end, cue.speaker))
    for cue_id, cue in enumerate(cues, 1):
        cue.cue_id = cue_id
    return cues
