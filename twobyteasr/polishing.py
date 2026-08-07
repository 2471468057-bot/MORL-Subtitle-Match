"""Cloud polishing orchestration and post-correction boundary cleanup."""

import threading

from subtitle_core import *  # noqa: F401,F403
from twobyteasr.correction import (
    apply_title_profile_aliases,
    apply_correction_edits,
    apply_global_domain_term_mappings,
    build_asr_difference_hints,
    build_gacha_quantity_hints,
    build_gacha_term_hints,
    build_strong_reference_consensus_hint,
    collect_stable_moss_term_candidates,
    discover_global_domain_term_mappings,
    nearby_glossary_candidates,
    parse_qwen_json,
    repair_with_user_glossary_terms,
    reference_differences_are_compatible,
    select_relevant_game_lexicon_terms,
    split_items_for_api,
)
from twobyteasr.runtime import get_runtime_context

__all__ = [
    "call_correction_api",
    "boundary_overlap_length",
    "trim_content_suffix",
    "trim_content_prefix",
    "repair_introduced_boundary_duplicates",
    "apply_final_segment_boundary_dedup",
    "filter_untrusted_polished_text",
    "polish_subtitles",
]

def call_correction_api(
    segment_batch,
    glossary,
    context_before,
    context_after,
    media_title,
    project_context,
    stable_term_candidates,
    approved_global_mappings,
    verified_terms,
    abort_event=None,
):
    import requests
    runtime_context = get_runtime_context()

    baseline = {
        segment.segment_id: clean_subtitle_text(segment.text)
        for segment in segment_batch
    }
    if abort_event is not None and abort_event.is_set():
        add_review_item(
            segment_batch[0].start,
            "校对回退",
            "云端校对模型已在前一批次被服务端拒绝，本批直接使用本地双模型纠错结果",
            segment_batch[0].text,
            priority=3,
        )
        return baseline

    if active_canonical_replacements():
        mapping_summary = "、".join(
            f"{source}→{target}"
            for source, target in active_canonical_replacements()[:80]
        )
        canonical_summary = "、".join(active_profile_terms()[:120])
        editorial_rule = (
            "最终字幕不得保留‘我操’‘卧槽’及其‘我草/窝草’等同音写法；"
            f"本期《{runtime_context.game_name}》的用户核验术语来自结构化配置，必须全片统一。"
            f"已确认错词映射：{mapping_summary}。"
            f"正式术语：{canonical_summary}。"
            "精灵、人物、队伍、技能与机制同等重要；不得只核对技能，也不得改写普通同音词。"
        )
    else:
        editorial_rule = (
            "最终字幕不得保留‘我操’‘卧槽’及其‘我草/窝草’等同音写法；"
            "不要套用任何旧游戏的固定替换规则。"
        )

    prompt = f"""你是中文口语视频的受限式 ASR 校对员。primary_text 是已经筛出的 MOSS 主播原话和时间骨架；FireRedASR2-AED 与 Qwen3-ASR 只提供独立文字证据；FireRedASR2-LLM 仅在争议片段出现。project_context 是用户本次运行时选择的内容背景，可以调用你已有的知识理解专名，但你不能联网检索，也不得把不确定的知识臆造成台词。

严格规则：
1. 只返回确实需要修改的 id，禁止合并、拆分、删除、调换字幕，也不能改变 speaker。
2. primary_text 是主播骨架。只提交局部替换补丁，from 必须逐字且唯一地出现在 primary_text 中，通常不超过 6 个字。
3. 所有参考都可能串入邻句或另一位说话人。possible_overlapping_speaker_conflict=true 时原样返回空 edits，禁止让节目声、NPC 或另一位主播覆盖当前文字。
4. FireRed 与 Qwen3 独立一致是强证据；FireRedASR2-LLM 只有与 primary_text 或 Qwen3 至少一方一致时才可作为证据。任何单一模型都不能触发整句替换。
5. 只修正有充分依据的同音字、漏字、专名和数字；不要摘要、扩写、书面化，不要删除口语重复。禁止修改“呢/的、啊/他、他/它、搏/补”一类语气、代词或普通单字歧义；专名请提交完整的 2-8 字词组，不要只改其中一个字。
6. approved_global_term_mappings 是已经过联网全文表决和本地近音验证的专名映射，必须保持；除此之外，repeated_moss_term_candidates 中的词不得在逐批校对中改写。若无法确认，保留主稿。
7. 成片固定规则（最高优先级）：{editorial_rule}
8. glossary_reference 只是弱参考，只有读音和上下文同时支持时才能采用，禁止因词表存在就强制替换。
9. 数字格式必须按语境统一：百分比、伤害、威力、生命值等界面数值用阿拉伯数字（如“12%”“威力加40”）；普通口语数量用中文（如“一万”“十六层”“一个”）。“一百八十八”这类不带万/亿的明确三位数可写“188”。禁止“1万”“百分之1万”以及同一句无必要地混用中文数词和阿拉伯数字。
10. 当 confidence 低于 0.82、reference_consensus 至少 0.82，且 FireRed/Qwen3 对整段高度一致时，才允许较大补丁；本地仍会做长度、数量和多模型证据验证。
11. 一条字幕可以有多个互不重叠的小补丁。没有可靠修改就返回空 edits。
12. 只返回 JSON：{{"cues":[{{"id":1,"edits":[{{"from":"食物","to":"实物","basis":"moss+qwen3+context"}}]}}]}}。"""

    request_body = {
        "project_title": media_title,
        "context_before": context_before,
        "context_after": context_after,
        "content_domain": project_context,
        "project_context": project_context,
        "repeated_moss_term_candidates": stable_term_candidates,
        "approved_global_term_mappings": approved_global_mappings,
        "verified_game_terms": verified_terms,
        "glossary_reference": glossary,
        "cues": [
            {
                "id": segment.segment_id,
                "start": round(segment.start, 2),
                "end": round(segment.end, 2),
                "primary_text": segment.text,
                "primary_source": segment.primary_source,
                "speaker": segment.speaker,
                "reference_consensus": round(segment.reference_consensus, 3),
                "firered_aed_asr": segment.firered_text or segment.text,
                "firered_aed_difference_hints": build_asr_difference_hints(
                    segment.text, segment.firered_text
                ),
                "possible_overlapping_speaker_conflict": (
                    segment.overlapping_speaker_conflict
                ),
                "moss_asr": segment.moss_text or segment.alternate_text or None,
                "moss_context": segment.moss_context or segment.alternate_context or None,
                "moss_difference_hints": build_asr_difference_hints(
                    segment.text, segment.moss_text or segment.alternate_text
                ),
                "qwen3_asr": segment.qwen_asr_text or None,
                "qwen3_context": segment.qwen_asr_context or None,
                "qwen3_difference_hints": build_asr_difference_hints(
                    segment.text, segment.qwen_asr_text
                ),
                "firered_llm_asr": segment.firered_llm_text or None,
                "firered_llm_context": segment.firered_llm_context or None,
                "firered_llm_difference_hints": build_asr_difference_hints(
                    segment.text, segment.firered_llm_text
                ),
                "strong_reference_consensus": build_strong_reference_consensus_hint(
                    segment
                ),
                "gacha_quantity_hints": build_gacha_quantity_hints(
                    segment.text,
                    f"{context_before}{context_after}",
                ),
                "gacha_term_hints": build_gacha_term_hints(
                    segment.text,
                    f"{context_before}{context_after}",
                ),
                "nearby_glossary_candidates": nearby_glossary_candidates(
                    segment.text, glossary
                ),
                "confidence": round(segment.confidence, 2),
            }
            for segment in segment_batch
        ],
    }
    endpoint = polish_llm_settings()
    validate_endpoint(endpoint, "字幕校对模型")
    headers = {
        "Authorization": f"Bearer {endpoint['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": endpoint["model"],
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(request_body, ensure_ascii=False),
            },
        ],
        "temperature": 0.0,
        "max_tokens": min(8192, max(1024, len(segment_batch) * 64)),
    }

    last_error = None
    for attempt in range(1, API_RETRIES + 1):
        try:
            response = requests.post(
                endpoint["url"],
                headers=headers,
                json=payload,
                timeout=(10, API_TIMEOUT_SECONDS),
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            returned_items = parse_qwen_json(content)
            expected_ids = [segment.segment_id for segment in segment_batch]
            returned_ids = [int(item.get("id")) for item in returned_items]
            expected_set = set(expected_ids)
            if (
                len(returned_ids) != len(set(returned_ids))
                or any(item_id not in expected_set for item_id in returned_ids)
            ):
                raise ValueError(
                    "云端校对模型返回了未知或重复字幕 ID："
                    f"期望 {expected_ids[0]}-{expected_ids[-1]}，"
                    f"实际 {returned_ids[:5]}...{returned_ids[-5:]}"
                )

            validated = {}
            returned_by_id = {
                int(item["id"]): item for item in returned_items
            }
            for segment in segment_batch:
                item = returned_by_id.get(segment.segment_id, {"edits": []})
                first_independent_reference = (
                    segment.firered_text or segment.alternate_text
                    if segment.primary_source.startswith("moss-host")
                    else segment.moss_text or segment.alternate_text
                )
                allow_broad_consensus = (
                    segment.confidence < 0.82
                    and segment.reference_consensus >= 0.82
                    and reference_differences_are_compatible(
                        segment.firered_text or segment.alternate_text,
                        segment.qwen_asr_text,
                    )
                )
                corrected, applied = apply_correction_edits(
                    segment.text,
                    [
                        first_independent_reference,
                        segment.qwen_asr_text,
                        segment.firered_llm_text,
                    ],
                    item.get("edits", []),
                    allow_broad_consensus=allow_broad_consensus,
                    consensus_alternates=[
                        first_independent_reference,
                        segment.qwen_asr_text,
                    ],
                    gacha_quantity_hints=build_gacha_quantity_hints(
                        segment.text,
                        f"{context_before}{context_after}",
                    ),
                    gacha_term_hints=build_gacha_term_hints(
                        segment.text,
                        f"{context_before}{context_after}",
                    ),
                    protect_primary_speaker=(
                        segment.overlapping_speaker_conflict
                    ),
                    protected_domain_terms=[
                        item["to"] for item in approved_global_mappings
                    ]
                    + [item["term"] for item in stable_term_candidates]
                    + verified_terms,
                    approved_global_mappings=approved_global_mappings,
                    verified_terms=verified_terms,
                )
                if applied:
                    record_run_event(
                        "cloud_correction_applied",
                        cue_id=segment.segment_id,
                        edits=applied,
                    )
                    edit_summary = "；".join(
                        f"{edit['from']}→{edit['to']}({edit['basis']})"
                        for edit in applied
                    )
                    print(
                        f"   [采纳] 字幕 {segment.segment_id}：{edit_summary}\n"
                        f"           {segment.text} -> {corrected}"
                    )
                validated[segment.segment_id] = corrected
            return validated
        except Exception as exc:
            last_error = exc
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code in {400, 401, 403, 404}:
                if abort_event is not None:
                    abort_event.set()
                print(
                    f"   [警告] 云端校对配置被服务端拒绝（HTTP {status_code}），"
                    "本轮立即回退 ASR 原文，不再重复请求。"
                )
                break
            if attempt < API_RETRIES:
                delay = 2 ** (attempt - 1)
                print(f"   [警告] 云端校对失败，{delay} 秒后重试（{attempt}/{API_RETRIES}）")
                time.sleep(delay)

    print(f"   [警告] 云端校对失败，当前批次保留 ASR 原文：{last_error}")
    add_review_item(
        segment_batch[0].start,
        "校对回退",
        f"云端校对批次失败：{str(last_error)[:120]}",
        segment_batch[0].text,
        priority=3,
    )
    return baseline


def boundary_overlap_length(left, right, limit=3):
    left_content = content_only(simplify_chinese(left))
    right_content = content_only(simplify_chinese(right))
    for length in range(min(limit, len(left_content), len(right_content)), 0, -1):
        if left_content[-length:] == right_content[:length]:
            return length
    return 0


def trim_content_suffix(text, count):
    positions = [
        match.start()
        for match in re.finditer(r"[\u3400-\u9fffA-Za-z0-9]", str(text or ""))
    ]
    if count <= 0 or count > len(positions):
        return clean_subtitle_text(text)
    return clean_subtitle_text(str(text)[: positions[-count]])


def trim_content_prefix(text, count):
    positions = [
        match.start()
        for match in re.finditer(r"[\u3400-\u9fffA-Za-z0-9]", str(text or ""))
    ]
    if count <= 0 or count > len(positions):
        return clean_subtitle_text(text)
    return clean_subtitle_text(str(text)[positions[count - 1] + 1 :])


def repair_introduced_boundary_duplicates(segments, polished_by_id):
    """只移除校对新制造的跨句重复字；原 ASR 中已有的口语重复保持不动。"""
    repaired = dict(polished_by_id)
    for left_segment, right_segment in zip(segments, segments[1:]):
        left_original = clean_subtitle_text(
            simplify_chinese(left_segment.firered_text or left_segment.text)
        )
        right_original = clean_subtitle_text(
            simplify_chinese(right_segment.firered_text or right_segment.text)
        )
        left = clean_subtitle_text(
            repaired.get(left_segment.segment_id, left_original)
        )
        right = clean_subtitle_text(
            repaired.get(right_segment.segment_id, right_original)
        )
        original_overlap = boundary_overlap_length(left_original, right_original)
        candidate_overlap = boundary_overlap_length(left, right)
        if candidate_overlap <= original_overlap:
            continue

        left_grew = display_length(left) > display_length(left_original)
        right_grew = display_length(right) > display_length(right_original)
        if left_grew and not right_grew:
            candidate = trim_content_suffix(left, candidate_overlap)
            if candidate and display_length(candidate) >= display_length(left_original):
                repaired[left_segment.segment_id] = candidate
                print(
                    "   [相邻去重] 校对补字与下一句开头重复："
                    f"{left} / {right} -> {candidate} / {right}"
                )
        elif right_grew and not left_grew:
            candidate = trim_content_prefix(right, candidate_overlap)
            if candidate and display_length(candidate) >= display_length(right_original):
                repaired[right_segment.segment_id] = candidate
                print(
                    "   [相邻去重] 校对补字与上一句结尾重复："
                    f"{left} / {right} -> {left} / {candidate}"
                )
    return repaired


def apply_final_segment_boundary_dedup(segments):
    """校对文字写回后再做一次全文检查，避免缓存/分批让跨句重复漏网。"""
    if len(segments) < 2:
        return segments
    current = {segment.segment_id: segment.text for segment in segments}
    repaired = repair_introduced_boundary_duplicates(segments, current)
    changed = 0
    for segment in segments:
        text = clean_subtitle_text(repaired.get(segment.segment_id, segment.text))
        if content_only(text) != content_only(segment.text):
            segment.text = text
            changed += 1
    if changed:
        print(f"   [全文去重] 最终写回后再次修复 {changed} 个跨句重复边界。")
    return segments


def filter_untrusted_polished_text(
    baseline,
    candidate,
    alternates,
    verified_terms,
):
    """全文兜底：拦住模型把单字歧义或无证据增删写进最终稿。"""
    baseline_content = content_only(baseline)
    candidate_content = content_only(candidate)
    if not baseline_content or baseline_content == candidate_content:
        return clean_subtitle_text(candidate)
    verified_contents = {
        content_only(term) for term in verified_terms if content_only(term)
    }
    alternate_contents = [content_only(value) for value in alternates if content_only(value)]
    matcher = SequenceMatcher(
        None,
        baseline_content,
        candidate_content,
        autojunk=False,
    )
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        source = baseline_content[left_start:left_end]
        target = candidate_content[right_start:right_end]
        target_is_verified = False
        for term in verified_contents:
            aliases = {term}
            aliases.update(
                term[-length:]
                for length in range(2, min(6, len(term)) + 1)
            )
            for alias in aliases:
                for match in re.finditer(re.escape(alias), candidate_content):
                    if match.start() <= right_start and right_end <= match.end():
                        target_is_verified = True
                        break
                if target_is_verified:
                    break
            if target_is_verified:
                break
        exact_support = sum(
            bool(target) and target in value for value in alternate_contents
        )
        # 非核验专名必须同时出现在两套独立参考里。过去这里只拦普通单字，
        # 导致 Qwen3 单模型能把“无聊”改成“厉好”、把“拿了八百”改成
        # “拿到报表”；多字改动同样不能绕过共识门槛。
        if not target_is_verified and exact_support < 2:
            return clean_subtitle_text(baseline)
        if len(source) != len(target) and not target_is_verified:
            whole_support = sum(
                candidate_content in value or value in candidate_content
                for value in alternate_contents
            )
            if whole_support < 2:
                return clean_subtitle_text(baseline)
    return clean_subtitle_text(candidate)


def polish_subtitles(segments, media_title, cache_context=None):
    print(
        "\n[校对] Qwen 对照 FireRed-AED/MOSS/Qwen3/争议 LLM 与上下文，"
        "再由本地规则裁决..."
    )
    glossary = load_glossary()
    # These two deterministic passes do not depend on the cloud endpoint.  They
    # remain available when the cloud model is unavailable and are intentionally applied
    # before the cache dependency/baseline is built.
    segments = apply_title_profile_aliases(segments, media_title)
    segments = repair_with_user_glossary_terms(segments, glossary, media_title)
    verified_terms = load_verified_game_terms()
    segments = repair_with_contextual_profile_aliases(segments)
    segments = repair_with_verified_game_terms(segments, verified_terms)
    project_context = load_content_context(media_title)
    stable_term_candidates = []
    learned_mappings = []
    approved_global_mappings = []
    if get_runtime_context().enable_domain_terms:
        learned_mappings = prepared_learned_mappings(segments)
        if learned_mappings:
            print(f"   [已学习术语] 本批命中 {len(learned_mappings)} 组映射。")
            segments = apply_global_domain_term_mappings(segments, learned_mappings)
        stable_term_candidates = collect_stable_moss_term_candidates(
            segments, glossary
        )
        lexicon_terms = select_relevant_game_lexicon_terms(
            segments,
            stable_term_candidates,
        )
        glossary = list(dict.fromkeys([*glossary, *lexicon_terms]))
        if stable_term_candidates:
            sample = "、".join(item["term"] for item in stable_term_candidates[:12])
            print(
                f"   [全文术语候选] 共 {len(stable_term_candidates)} 个；"
                f"示例：{sample}。"
            )
        approved_global_mappings = discover_global_domain_term_mappings(
            segments,
            project_context,
            glossary,
            verified_terms,
            stable_term_candidates,
        )
    else:
        print("   [全文术语候选] 通用/弱背景模式关闭联网术语表决。")
    segments = apply_global_domain_term_mappings(
        segments,
        approved_global_mappings,
    )
    all_global_mappings = learned_mappings + approved_global_mappings
    baseline_by_id = {
        segment.segment_id: clean_subtitle_text(segment.text)
        for segment in segments
    }
    batches = split_items_for_api(segments, max_cues=POLISH_BATCH_MAX_CUES)
    index_by_id = {
        segment.segment_id: index for index, segment in enumerate(segments)
    }
    polished_by_id = {}
    jobs = []
    correction_abort_event = threading.Event()
    for index, batch in enumerate(batches, 1):
        first_index = index_by_id[batch[0].segment_id]
        last_index = index_by_id[batch[-1].segment_id]
        context_before = "".join(
            segment.text for segment in segments[max(0, first_index - 20) : first_index]
        )[-300:]
        context_after = "".join(
            segment.text for segment in segments[last_index + 1 : last_index + 21]
        )[:300]
        dependency = {
            "batch": serialize_segments(batch),
            "context_before": context_before,
            "context_after": context_after,
            "media_title": media_title,
            "project_context": project_context,
            "glossary": glossary,
            "stable_terms": stable_term_candidates,
            "mappings": all_global_mappings,
            "verified_terms": verified_terms,
        }
        jobs.append((index, batch, context_before, context_after, dependency))

    def run_job(job):
        index, batch, context_before, context_after, dependency = job
        print(f"   校对批次 {index}/{len(batches)}")
        started_at = time.perf_counter()

        def run_polish_batch():
            return call_correction_api(
                batch,
                glossary,
                context_before,
                context_after,
                media_title,
                project_context,
                stable_term_candidates,
                all_global_mappings,
                verified_terms,
                abort_event=correction_abort_event,
            )
        with capture_review_items() as review_items:
            if cache_context is not None:
                batch_result = run_cached_api_batch(
                    "polished",
                    cache_context,
                    dependency,
                    run_polish_batch,
                    decoder=lambda value: {
                        int(key): text for key, text in (value or {}).items()
                    },
                    fallback_categories=("校对回退",),
                )
            else:
                batch_result = run_polish_batch()
        elapsed_seconds = time.perf_counter() - started_at
        record_run_event(
            "cloud_batch_completed",
            stage="polished",
            batch_index=index,
            batch_total=len(batches),
            cue_count=len(batch),
            elapsed_seconds=round(elapsed_seconds, 3),
        )
        return index, batch_result, review_items

    results = {}
    workers = min(CLOUD_BATCH_WORKERS, len(jobs)) if PARALLEL_CLOUD_BATCHES else 1
    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        print(f"   [并行加速] {len(jobs)} 个校对批次，最多 {workers} 路并发。")
        record_run_event(
            "cloud_batches_parallel",
            stage="polished",
            batches=len(jobs),
            workers=workers,
        )
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="glm-polish") as pool:
            futures = {pool.submit(run_job, job): job[0] for job in jobs}
            for future in as_completed(futures):
                index, batch_result, review_items = future.result()
                results[index] = batch_result
                extend_review_items(review_items)
    else:
        for job in jobs:
            index, batch_result, review_items = run_job(job)
            results[index] = batch_result
            extend_review_items(review_items)
    for index in sorted(results):
        polished_by_id.update(results[index])

    polished_by_id = repair_introduced_boundary_duplicates(
        segments,
        polished_by_id,
    )
    for segment in segments:
        baseline = baseline_by_id[segment.segment_id]
        candidate = polished_by_id.get(segment.segment_id, baseline)
        filtered = filter_untrusted_polished_text(
            baseline,
            candidate,
            [
                segment.firered_text,
                segment.alternate_text,
                segment.qwen_asr_text,
                segment.firered_llm_text,
            ],
            verified_terms,
        )
        if content_only(filtered) != content_only(candidate):
            print(
                f"   [全文安全回退] 字幕 {segment.segment_id}："
                f"{candidate} -> {filtered}"
            )
        polished_by_id[segment.segment_id] = filtered
    normalized_segments = []
    for segment in segments:
        segment.text = normalize_output_text(
            polished_by_id.get(segment.segment_id, segment.text)
        )
        if not content_only(segment.text):
            continue
        segment.segment_id = len(normalized_segments) + 1
        normalized_segments.append(segment)
    return apply_final_segment_boundary_dedup(normalized_segments)
