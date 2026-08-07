"""Game/domain terminology discovery, source verification, and mapping application."""

from subtitle_core import *  # noqa: F401,F403
from twobyteasr.correction import parse_qwen_object
from twobyteasr.correction_safety import build_asr_difference_hints
from twobyteasr.runtime import get_runtime_context
from twobyteasr.term_constants import *  # noqa: F401,F403
from twobyteasr.text_similarity import levenshtein, phonetic_text

__all__ = [
    "apply_title_profile_aliases",
    "repair_with_user_glossary_terms",
    "select_relevant_game_lexicon_terms",
    "collect_stable_moss_term_candidates",
    "collect_global_term_disputes",
    "_public_https_url",
    "verify_term_source_urls",
    "discover_global_domain_term_mappings",
    "apply_global_domain_term_mappings",
]


def _title_matched_profile(media_title):
    """Return a local profile only when its explicit title trigger is present."""
    title_identity = runtime_game_identity(media_title)
    if not title_identity:
        return "", {}
    for name, profile in load_game_profiles().items():
        if not isinstance(profile, dict):
            continue
        triggers = profile.get("title_triggers", ())
        for trigger in triggers if isinstance(triggers, list) else ():
            trigger_identity = runtime_game_identity(trigger)
            if trigger_identity and trigger_identity in title_identity:
                return name, profile
    return "", {}


def apply_title_profile_aliases(segments, media_title):
    """Apply user-verified aliases scoped by an unambiguous media-title trigger."""
    profile_name, profile = _title_matched_profile(media_title)
    if not profile:
        return segments
    rules = []
    for item in profile.get("terms", ()):
        if not isinstance(item, dict) or not item.get("confirmed", False):
            continue
        target = clean_subtitle_text(item.get("canonical", ""))
        for source in item.get("aliases", ()):
            source = clean_subtitle_text(source)
            if source and target and source != target and len(content_only(source)) >= 2:
                rules.append((source, target))
    rules.sort(key=lambda pair: len(content_only(pair[0])), reverse=True)

    changes = []
    for segment in segments:
        for source, target in rules:
            if source not in segment.text:
                continue
            before = segment.text
            segment.text = clean_subtitle_text(segment.text.replace(source, target))
            if segment.text != before:
                changes.append((segment.segment_id, source, target))
                get_runtime_context().discovered_terms.add(target)
    if changes:
        sample = "、".join(
            f"{source}→{target}" for _, source, target in changes[:12]
        )
        print(
            f"   [标题本地词表] 《{profile_name}》命中 {len(changes)} 处：{sample}。"
        )
        record_run_event(
            "title_profile_aliases_applied",
            profile=profile_name,
            count=len(changes),
            edits=[
                {"cue_id": cue_id, "from": source, "to": target}
                for cue_id, source, target in changes
            ],
        )
    return segments


def repair_with_user_glossary_terms(segments, glossary, media_title=""):
    """Use explicit user glossary entries for repeated or independently heard homophones.

    The glossary remains conservative: the heard spelling must have the same
    length and effectively the same pronunciation, plus title, reference, or
    repeated-transcript support.  A one-off merely similar word is never changed.
    """
    targets = sorted(
        {content_only(term) for term in glossary if 2 <= len(content_only(term)) <= 12},
        key=len,
        reverse=True,
    )
    if not targets:
        return segments
    primary_texts = [content_only(segment.text) for segment in segments]
    media_content = content_only(media_title)
    changes = []
    for segment in segments:
        text = content_only(segment.text)
        display_text = clean_subtitle_text(segment.text)
        references = [
            content_only(value)
            for value in (
                segment.firered_text,
                segment.qwen_asr_text,
                segment.firered_llm_text,
            )
            if content_only(value)
        ]
        for target in targets:
            if target in text:
                continue
            target_sound = phonetic_text(target)
            best = None
            for start in range(0, len(text) - len(target) + 1):
                source = text[start : start + len(target)]
                if source == target or source in targets:
                    continue
                source_sound = phonetic_text(source)
                similarity = SequenceMatcher(
                    None,
                    source_sound,
                    target_sound,
                    autojunk=False,
                ).ratio()
                if similarity < 0.98:
                    continue
                occurrences = sum(source in value for value in primary_texts)
                supported = (
                    occurrences >= 2
                    or target in media_content
                    or any(target in value for value in references)
                )
                if not supported:
                    continue
                candidate = (similarity, occurrences, -start, start, source)
                if best is None or candidate[:3] > best[:3]:
                    best = candidate
            if best is None:
                continue
            _, _, _, start, source = best
            before = display_text
            display_text = clean_subtitle_text(display_text.replace(source, target, 1))
            if display_text == before:
                continue
            text = content_only(display_text)
            changes.append((segment.segment_id, source, target))
        segment.text = display_text
    if changes:
        sample = "、".join(
            f"{source}→{target}" for _, source, target in changes[:12]
        )
        print(f"   [用户词表本地纠错] 共 {len(changes)} 处：{sample}。")
        record_run_event(
            "local_user_glossary_applied",
            count=len(changes),
            edits=[
                {"cue_id": cue_id, "from": source, "to": target}
                for cue_id, source, target in changes
            ],
        )
    return segments

def select_relevant_game_lexicon_terms(
    segments,
    source_candidates=(),
    limit=GAME_LEXICON_MAX_PROMPT_TERMS,
):
    """
    从完整图鉴中按本批多套 ASR 的原字/近音检索少量候选。

    返回值只会追加到 Qwen 的弱 glossary_reference；不会参与本地强制替换。
    """
    if not get_runtime_context().enable_domain_terms:
        return []
    lexicon_names, loaded = load_active_game_lexicon_names()
    if not lexicon_names:
        return []

    evidence_values = Counter()
    heard_candidates = Counter()
    for segment in segments:
        primary = content_only(segment.text)
        values = {
            content_only(value)
            for value in (
                segment.text,
                segment.moss_text,
                segment.firered_text,
                segment.qwen_asr_text,
                segment.firered_llm_text,
                segment.alternate_text,
            )
            if content_only(value)
        }
        for value in values:
            evidence_values[value] += 1
            if 2 <= len(value) <= 12:
                heard_candidates[value] += 1
        for alternate in values - {primary}:
            for hint in build_asr_difference_hints(primary, alternate):
                for key in ("primary", "alternate"):
                    value = content_only(hint.get(key, ""))
                    if 2 <= len(value) <= 12:
                        heard_candidates[value] += 2
    for item in source_candidates:
        value = content_only(
            item.get("term", "") if isinstance(item, dict) else item
        )
        if 2 <= len(value) <= 12:
            heard_candidates[value] += int(
                item.get("occurrences", 1) if isinstance(item, dict) else 1
            )

    terms_by_length = {}
    for name in lexicon_names:
        term = content_only(name)
        if 2 <= len(term) <= 12:
            terms_by_length.setdefault(len(term), []).append(term)
    phonetic_cache = {}

    def sound(value):
        if value not in phonetic_cache:
            phonetic_cache[value] = phonetic_text(value)
        return phonetic_cache[value]

    ranked_by_term = {}
    for term in (term for terms in terms_by_length.values() for term in terms):
        exact_occurrences = sum(
            occurrences
            for value, occurrences in evidence_values.items()
            if term in value
        )
        if exact_occurrences:
            ranked_by_term[term] = (2, 1.0, exact_occurrences, len(term), term)

    for heard, occurrences in heard_candidates.items():
        heard_sound = sound(heard)
        for length in range(max(2, len(heard) - 1), min(12, len(heard) + 1) + 1):
            for term in terms_by_length.get(length, ()):
                if term in ranked_by_term:
                    continue
                similarity = SequenceMatcher(
                    None,
                    heard_sound,
                    sound(term),
                    autojunk=False,
                ).ratio() - abs(len(heard) - len(term)) * 0.08
                threshold = (
                    0.90 if len(term) == 2 else 0.84 if len(term) <= 4 else 0.80
                )
                if similarity < threshold:
                    continue
                candidate = (1, similarity, occurrences, len(term), term)
                if candidate > ranked_by_term.get(term, (0, 0.0, 0, 0, term)):
                    ranked_by_term[term] = candidate

    ranked = list(ranked_by_term.values())
    ranked.sort(reverse=True)
    selected = []
    for _, _, _, _, term in ranked:
        if term not in selected:
            selected.append(term)
        if len(selected) >= int(limit):
            break
    summary = "、".join(
        f"{category}{entries}条/{unique}名"
        for category, entries, unique in loaded
    )
    print(
        f"   [本地图鉴词库] {summary}；按本批原字/近音检索出 "
        f"{len(selected)} 个弱候选，不执行机械替换。"
    )
    return selected


def _moss_substring_segment_frequency(segments):
    """统计一个写法在多少个 MOSS 段里出现，避免口头重复把频次虚高。"""
    counts = Counter()
    for segment in segments:
        source = content_only(segment.moss_text or segment.text)
        seen = set()
        for length in range(
            MOSS_TERM_STABILITY_MIN_CHARS,
            MOSS_TERM_STABILITY_MAX_CHARS + 1,
        ):
            seen.update(
                source[index : index + length]
                for index in range(max(0, len(source) - length + 1))
            )
        counts.update(seen)
    return counts


def collect_stable_moss_term_candidates(segments, glossary=(), limit=80):
    """给 Qwen 一份全文重复专名候选；它是线索，不是强制词表。"""
    segment_frequency = _moss_substring_segment_frequency(segments)
    canonical_frequency = Counter()
    for term, occurrences in segment_frequency.items():
        if not (
            MOSS_TERM_STABILITY_MIN_CHARS
            <= len(term)
            <= MOSS_TERM_STABILITY_MAX_CHARS
            and occurrences >= MOSS_TERM_STABILITY_MIN_SEGMENTS
        ):
            continue
        if term in MOSS_TERM_STABILITY_STOPWORDS:
            continue
        if occurrences == MOSS_TERM_STABILITY_MIN_SEGMENTS and term[-1:] not in MOSS_DOMAIN_TERM_SUFFIXES:
            continue
        # 保留 ASR 的原始错词交给联网核对。旧逻辑先把候选替换成正确词，
        # 随后又拿正确词去 primary_text 里查，导致“藤角/藤绞”这类候选消失。
        canonical_frequency[term] += int(occurrences)
    candidates = list(canonical_frequency.items())
    candidates.sort(key=lambda item: (item[1], len(item[0]), item[0]), reverse=True)

    selected = []
    seen = set()
    for term, occurrences in candidates:
        if term in seen:
            continue
        # 同频时只留更完整的候选，避免把“飞飞药”同时拆成“飞药”。
        if any(
            (
                term in existing
                or existing in term
                or phonetic_text(term) in phonetic_text(existing)
            )
            and occurrences <= count
            for existing, count in selected
        ):
            continue
        selected.append((term, occurrences))
        seen.add(term)
        if len(selected) >= limit:
            break

    payload = [
        {"term": term, "moss_segment_count": count}
        for term, count in selected
    ]
    for term in glossary:
        clean = clean_subtitle_text(term)
        if clean and clean not in seen:
            payload.append({"term": clean, "source": "glossary"})
            seen.add(clean)
        if len(payload) >= limit:
            break
    return payload[:limit]


def collect_global_term_disputes(segments, stable_term_candidates, limit=140):
    """汇总全文专名冲突及低置信正文，供一次联网词汇表决使用。"""
    stable_terms = [item["term"] for item in stable_term_candidates]
    priority_disputes = []
    broad_audit_rows = []
    for segment in segments:
        primary = clean_subtitle_text(segment.text)
        if not content_only(primary):
            continue
        alternatives = []
        for value in (
            segment.firered_text,
            segment.qwen_asr_text,
            segment.firered_llm_text,
        ):
            value = clean_subtitle_text(value)
            if value and content_only(value) != content_only(primary) and value not in alternatives:
                alternatives.append(value)
        domain_hits = [term for term in stable_terms if term in content_only(primary)]
        difference_hints = []
        for alternate in alternatives:
            difference_hints.extend(build_asr_difference_hints(primary, alternate))
        phonetic_hints = [
            hint
            for hint in difference_hints
            if hint.get("primary")
            and hint.get("alternate")
            and max(len(hint["primary"]), len(hint["alternate"])) <= 8
            and levenshtein(
                phonetic_text(hint["primary"]),
                phonetic_text(hint["alternate"]),
            )
            / max(
                1,
                len(phonetic_text(hint["primary"])),
                len(phonetic_text(hint["alternate"])),
            )
            <= 0.55
        ]
        low_confidence = float(getattr(segment, "confidence", 1.0) or 0.0) < 0.72
        overlapping = bool(segment.overlapping_speaker_conflict)
        score = (
            len(domain_hits) * 50
            + min(20, len(phonetic_hints) * 5)
            + int(bool(alternatives)) * 2
            + int(low_confidence) * 4
            + int(overlapping) * 3
        )
        row = {
            "id": segment.segment_id,
            "speaker": segment.speaker,
            "primary_text": primary,
            "alternative_asr": alternatives[:3],
            "difference_hints": phonetic_hints[:8],
            "repeated_term_hits": domain_hits,
            "low_confidence": low_confidence,
            "overlapping_speaker_conflict": overlapping,
            "audit_reason": (
                "asr_or_term_conflict"
                if domain_hits or phonetic_hints
                else "low_confidence_or_overlap"
                if low_confidence or overlapping
                else "broad_proper_noun_audit"
            ),
        }
        ranked = (-score, segment.segment_id, row)
        if score > 0:
            priority_disputes.append(ranked)
        else:
            broad_audit_rows.append(ranked)

    priority_disputes.sort(key=lambda item: (item[0], item[1]))
    selected = priority_disputes[:limit]
    remaining = limit - len(selected)
    if remaining > 0 and broad_audit_rows:
        if len(broad_audit_rows) <= remaining:
            selected.extend(broad_audit_rows)
        else:
            step = len(broad_audit_rows) / remaining
            selected.extend(
                broad_audit_rows[min(len(broad_audit_rows) - 1, int(index * step))]
                for index in range(remaining)
            )
    return [item[2] for item in selected]


def _public_https_url(url):
    try:
        parsed = urllib.parse.urlparse(str(url))
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.fragment:
            return False
        for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
            address = ipaddress.ip_address(item[4][0])
            if not address.is_global:
                return False
        return True
    except (OSError, ValueError):
        return False


def _public_peer(response):
    """Reject DNS-rebinding connections when Requests exposes the live socket."""
    raw = getattr(response, "raw", None)
    candidates = (
        getattr(getattr(raw, "_connection", None), "sock", None),
        getattr(getattr(raw, "connection", None), "sock", None),
        getattr(getattr(getattr(getattr(raw, "_fp", None), "fp", None), "raw", None), "_sock", None),
    )
    for sock in candidates:
        if sock is None:
            continue
        try:
            return ipaddress.ip_address(sock.getpeername()[0]).is_global
        except (OSError, ValueError, TypeError):
            return False
    return True


def _bounded_response_text(response, limit=1_500_000):
    content_length = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
    if content_length:
        try:
            if int(content_length) > limit:
                raise ValueError("response too large")
        except ValueError as exc:
            raise ValueError("invalid or excessive Content-Length") from exc
    body = bytearray()
    for chunk in response.iter_content(chunk_size=64 * 1024, decode_unicode=False):
        if not chunk:
            continue
        body.extend(chunk)
        if len(body) > limit:
            raise ValueError("response too large")
    encoding = getattr(response, "encoding", None) or "utf-8"
    return bytes(body).decode(encoding, errors="replace")


def verify_term_source_urls(target, urls, requests_module):
    """新联网词必须在至少一个公开 HTTPS 来源正文中真实出现。"""
    verified = []
    target = content_only(target)
    if not target:
        return verified
    for raw_url in list(urls or ())[:5]:
        url = str(raw_url).strip()
        if not _public_https_url(url):
            continue
        response = None
        try:
            current_url = url
            for redirect_count in range(4):
                if not _public_https_url(current_url):
                    raise ValueError("unsafe source URL")
                response = requests_module.get(
                    current_url,
                    timeout=(6, 12),
                    headers={"User-Agent": "Mozilla/5.0 2ByteASR-TermVerifier/1.0"},
                    allow_redirects=False,
                    stream=True,
                    proxies={"http": None, "https": None},
                )
                if not _public_peer(response):
                    raise ValueError("source connected to a non-public address")
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location", "")
                    response.close()
                    response = None
                    if redirect_count >= 3 or not location:
                        raise ValueError("unsafe redirect chain")
                    current_url = urllib.parse.urljoin(current_url, location)
                    continue
                response.raise_for_status()
                body = _bounded_response_text(response)
                if target in content_only(body):
                    verified.append(current_url)
                break
        except Exception:
            continue
        finally:
            if response is not None:
                response.close()
        if len(verified) >= 2:
            break
    return verified


def discover_global_domain_term_mappings(
    segments,
    project_context,
    glossary,
    verified_terms,
    stable_term_candidates,
):
    """让 Qwen 联网核对一次全文专名；只接收高置信、近音、局部映射。"""
    import requests

    runtime_context = get_runtime_context()

    disputes = collect_global_term_disputes(
        segments,
        stable_term_candidates,
    )
    if not disputes:
        print("   [联网全局术语] 已启用联网检索，但全文没有形成可安全表决的专名冲突。")
        record_run_event(
            "domain_term_search_skipped",
            game=runtime_context.game_name,
            reason="no_candidate_text",
        )
        return []
    record_run_event(
        "domain_term_search_started",
        game=runtime_context.game_name,
        candidate_count=len(disputes),
        overlap_candidate_count=sum(
            bool(item.get("overlapping_speaker_conflict")) for item in disputes
        ),
        broad_audit_count=sum(
            item.get("audit_reason") == "broad_proper_noun_audit"
            for item in disputes
        ),
    )
    prompt = """你是游戏官方术语核对员。请先联网检索 project_context 对应游戏的官方资料、可靠攻略或社区术语，再对全文 ASR 冲突做一次全局词汇表决。

严格规则：
1. 只处理角色、生物、技能、机制、队伍、招式等游戏专名；不修改语气词、代词、助词、普通动词和口语表达。
2. from 必须是 primary_text 中连续出现的完整错词，优先 2-8 字；to 必须是读音相近且联网结果能支持的正式写法。不要只返回单个汉字。
3. repeated_moss_term_candidates 是重复候选，不保证正确；alternative_asr 也不保证正确。必须结合多个上下文和搜索结果判断。
4. verified_game_terms 是本地已核验词，命中它时优先采用；未命中时，只有搜索结果明确支持官方/通行专名，才可返回 verification="web_official"，并必须提供包含正式词的公开 HTTPS 来源 URL。即使三套 ASR 写法一致，broad_proper_noun_audit 中仍可能有一致误识别的新角色名；请逐条检查其中疑似专名。无法确认、搜索不到或存在多个可能时不要输出映射。
5. source_ids 只列确实出现 from 且语义相同的字幕 id；同一个专名在全文必须统一。
6. confidence 只能是 high；达不到 high 就不要返回。禁止编造“官方技能名”或搜索证据。
7. overlapping_speaker_conflict 只表示时间和说话人边界需要保护，不禁止修正专名中的同音错字；不得借此改写普通台词。
8. 只返回 JSON：{"mappings":[{"from":"听桥","to":"听潮","source_ids":[1,2],"confidence":"high","verification":"web_official","sources":["https://example.com/term"],"reason":"联网术语+上下文"}]}。"""
    request_body = {
        "project_context": project_context,
        "glossary_reference": glossary,
        "verified_game_terms": verified_terms,
        "repeated_moss_term_candidates": stable_term_candidates,
        "asr_disputes": disputes,
    }
    endpoint = polish_llm_settings()
    validate_endpoint(endpoint, "字幕校对模型")
    headers = {
        "Authorization": f"Bearer {endpoint['api_key']}",
        "Content-Type": "application/json",
    }
    request_payload = {
        "model": endpoint["model"],
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(request_body, ensure_ascii=False),
            },
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
    }
    if endpoint["provider"] == "bailian":
        request_payload.update(
            enable_search=True,
            search_options={"forced_search": True, "search_strategy": "turbo"},
        )
    last_error = None
    for attempt in range(1, API_RETRIES + 1):
        try:
            response = requests.post(
                endpoint["url"],
                headers=headers,
                json=request_payload,
                timeout=(10, max(API_TIMEOUT_SECONDS, 180)),
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            returned = parse_qwen_object(content).get("mappings", [])
            if not isinstance(returned, list):
                raise ValueError("联网术语表决缺少 mappings 数组。")
            record_run_event(
                "domain_term_search_response",
                game=runtime_context.game_name,
                returned_count=len(returned),
            )

            segment_by_id = {segment.segment_id: segment for segment in segments}
            accepted = []
            seen_sources = set()
            stable_terms = {item["term"] for item in stable_term_candidates}
            verified_set = {content_only(term) for term in verified_terms}
            blocked_mappings = active_blocked_mapping_pairs()
            rejected_candidates = []
            for item in returned:
                if not isinstance(item, dict) or item.get("confidence") != "high":
                    continue
                source = content_only(item.get("from", ""))
                target = content_only(item.get("to", ""))
                if (
                    not (2 <= len(source) <= 8 and 2 <= len(target) <= 8)
                    or source == target
                    or source in seen_sources
                    or source in verified_set
                    or (source, target) in blocked_mappings
                ):
                    continue
                target_is_verified = target in verified_set
                web_official = item.get("verification") == "web_official"
                if not target_is_verified and not web_official:
                    rejected_candidates.append((source, target))
                    continue
                verified_sources = []
                if web_official and not target_is_verified:
                    verified_sources = verify_term_source_urls(
                        target,
                        item.get("sources", []),
                        requests,
                    )
                    if not verified_sources:
                        rejected_candidates.append((source, target))
                        continue
                sound_distance = levenshtein(
                    phonetic_text(source), phonetic_text(target)
                ) / max(1, len(phonetic_text(source)), len(phonetic_text(target)))
                max_sound_distance = 0.45 if target_is_verified else 0.30
                if sound_distance > max_sound_distance:
                    continue
                source_ids = []
                for raw_id in item.get("source_ids", []):
                    try:
                        segment_id = int(raw_id)
                    except (TypeError, ValueError):
                        continue
                    segment = segment_by_id.get(segment_id)
                    if segment is not None and source in content_only(segment.text):
                        source_ids.append(segment_id)
                occurrence_ids = [
                    segment.segment_id
                    for segment in segments
                    if source in content_only(segment.text)
                ]
                domain_shaped = target[-1:] in GLOBAL_DOMAIN_TERM_SUFFIXES
                if not source_ids or not (
                    source in stable_terms
                    or len(occurrence_ids) >= 2
                    or bool(verified_sources)
                    or (
                        target_is_verified
                        and len(source) >= 2
                        and domain_shaped
                    )
                ):
                    continue
                if not target_is_verified and not (
                    source in stable_terms
                    or len(occurrence_ids) >= 2
                    or bool(verified_sources)
                ):
                    continue
                accepted.append(
                    {
                        "from": source,
                        "to": target,
                        "source_ids": sorted(set(source_ids)),
                        "apply_all": len(occurrence_ids) >= 2 or source in stable_terms,
                        "reason": clean_subtitle_text(item.get("reason", "联网术语核对"))[:120],
                        "sources": verified_sources,
                        "verification": (
                            "local_profile" if target_is_verified else "web_source"
                        ),
                        "confirmed": bool(target_is_verified),
                    }
                )
                seen_sources.add(source)
                runtime_context.discovered_terms.add(target)
            if rejected_candidates:
                sample = "、".join(
                    f"{source}→{target}" for source, target in rejected_candidates[:8]
                )
                print(
                    "   [联网候选待复核] 未达到本地核验/官方高置信门槛，"
                    f"未写入成片：{sample}。"
                )
            persist_learned_mappings(runtime_context.game_name, accepted)
            record_run_event(
                "domain_term_search_completed",
                game=runtime_context.game_name,
                accepted_count=len(accepted),
                rejected_count=len(rejected_candidates),
                mappings=[
                    {
                        "from": item["from"],
                        "to": item["to"],
                        "verification": item["verification"],
                        "sources": item["sources"],
                    }
                    for item in accepted
                ],
            )
            return accepted
        except Exception as exc:
            last_error = exc
            record_run_event(
                "domain_term_search_retry" if attempt < API_RETRIES else "domain_term_search_failed",
                game=runtime_context.game_name,
                attempt=attempt,
                error=redact_runtime_secrets(exc),
            )
            if attempt < API_RETRIES:
                delay = 2 ** (attempt - 1)
                print(
                    f"   [警告] 联网术语表决失败，{delay} 秒后重试"
                    f"（{attempt}/{API_RETRIES}）"
                )
                time.sleep(delay)
    print(f"   [警告] 联网术语表决失败，本次不自动改专名：{last_error}")
    return []


def apply_global_domain_term_mappings(segments, mappings):
    """只应用通过联网全局表决和本地近音门的专名映射。"""
    applied = Counter()
    blocked = active_blocked_mapping_pairs()
    for mapping in sorted(mappings, key=lambda item: len(item["from"]), reverse=True):
        if (content_only(mapping["from"]), content_only(mapping["to"])) in blocked:
            continue
        allowed_ids = set(mapping["source_ids"])
        for segment in segments:
            if not mapping["apply_all"] and segment.segment_id not in allowed_ids:
                continue
            before = segment.text
            segment.text = clean_subtitle_text(
                segment.text.replace(mapping["from"], mapping["to"])
            )
            if segment.text != before:
                applied[(mapping["from"], mapping["to"])] += 1
    if applied:
        summary = "、".join(
            f"{source}→{target}×{count}"
            for (source, target), count in applied.items()
        )
        print(f"   [联网全局术语] {summary}。")
        record_run_event(
            "domain_term_mapping_applied",
            count=sum(applied.values()),
            mappings=[
                {"from": source, "to": target, "count": count}
                for (source, target), count in applied.items()
            ],
        )
    else:
        print("   [联网全局术语] 未发现达到自动写入门槛的新映射。")
    return segments
