"""Read-only review proposals, distinct from automatic correction authority."""
from __future__ import annotations

from difflib import SequenceMatcher

from .studio_text_tools import TextOccurrence


def diff_occurrences(cue, final, *, reason, source, selected=True, evidence='', missing=''):
    """Keep the editable cue as the baseline; each independent diff can be declined."""
    intervals=[]
    identifier=lambda char:char.isascii() and (char.isalnum() or char=='_')
    for tag,a,b,c,d in SequenceMatcher(None,cue.text,final,autojunk=False).get_opcodes():
        if tag=='equal':continue
        # A player's case/spelling is one decision, not independent letters.
        if (all(identifier(char) for char in cue.text[a:b])
                and all(identifier(char) for char in final[c:d])):
            while a and c and identifier(cue.text[a-1]) and cue.text[a-1]==final[c-1]:a-=1;c-=1
            while b<len(cue.text) and d<len(final) and identifier(cue.text[b]) and cue.text[b]==final[d]:b+=1;d+=1
        if intervals and a<=intervals[-1][1] and c<=intervals[-1][3]:
            previous=intervals.pop();intervals.append((previous[0],max(b,previous[1]),previous[2],max(d,previous[3])))
        else:intervals.append((a,b,c,d))
    return [TextOccurrence(cue.id, cue.start_ms, cue.text[a:b], final[c:d], (a, b),
        reason=reason, confidence=1.0 if source == 'local_confirmed' else .75,
        default_selected=selected, source=source, evidence=evidence, missing_evidence=missing)
        for a,b,c,d in intervals]


def original_span(original, draft, start, end):
    """Map an untouched or complete normalized span back to the actual cue."""
    mapped = []
    for tag, a, b, c, d in SequenceMatcher(None, original, draft, autojunk=False).get_opcodes():
        if c <= start and end <= d:
            if tag == 'equal':
                return a + start-c, a + end-c
            if start == c and end == d:
                return a, b
        if start <= c and d <= end:
            mapped.append((a, b, c, d))
    if mapped and mapped[0][2] == start and mapped[-1][3] == end:
        return mapped[0][0], mapped[-1][1]
    return None


def recover_review_edits(cue, draft, detail, snapshot, scene):
    """Expose valid name proposals without relaxing any automatic safety gate."""
    from .content_scene import alias_context_conflict
    targets = {term.canonical for library in snapshot.libraries for term in library.terms}
    targets.update(name for library in snapshot.libraries for name in library.reference_terms)
    sent = {row['candidate_id']: row for row in detail.get('sent_candidates', ())}
    recoverable = {'catalog_without_local_support', 'local_difference_without_two_sources',
        'length_change_without_support', 'ambiguous_single_character', 'protected_domain_term',
        'unsupported_phonetic_change', 'insufficient_asr_support'}
    output, invalid = [], []
    for edit in detail.get('rejected_edits', ()):
        source, target = str(edit.get('from') or ''), str(edit.get('to') or '')
        failure = edit.get('rule_id', 'invalid_or_no_effect')
        if failure not in recoverable:
            invalid.append({**edit, 'review_state':'invalid_or_protected'})
            continue
        reason = ''
        matches = [value for value in targets if value.casefold() == target.casefold()]
        if len(matches) != 1:
            reason = 'target_not_in_current_snapshot_or_conflicting_spelling'
        else:
            target = matches[0]
        a, b = edit.get('start'), edit.get('end')
        if a is None and b is None and source and draft.count(source) == 1:
            a = draft.index(source); b = a + len(source)
        if (type(a) is not int or type(b) is not int or not 0 <= a < b <= len(draft)
                or draft[a:b] != source or not target or len(source)>24 or len(target)>32):
            reason = 'invalid_or_unbounded_review_span'
        candidate_id = str(edit.get('candidate_id') or '')
        if candidate_id and (candidate_id not in sent or sent[candidate_id]['canonical'] != target):
            reason = 'unknown_or_mismatched_sent_candidate'
        if any(value.casefold() == source.casefold() and value != target for value in targets):
            reason = 'different_existing_canonical_identity'
        if not reason and alias_context_conflict(draft, source, target, scene=scene, span=(a,b)):
            reason = 'alias_context_topic_conflict'
        span = original_span(cue.text, draft, a, b) if not reason else None
        if span is None:
            reason = reason or 'span_changed_by_local_normalization'
        if reason:
            invalid.append({**edit, 'review_state':reason}); continue
        start, end = span
        labels={'catalog_without_local_support':'词库候选缺少局部支持',
            'local_difference_without_two_sources':'缺少两路独立转写支持',
            'length_change_without_support':'增删字缺少支持', 'ambiguous_single_character':'单字存在歧义',
            'protected_domain_term':'现有专名需要人工确认',
            'unsupported_phonetic_change':'近音改字缺少支持', 'insufficient_asr_support':'转写证据不足'}
        output.append(TextOccurrence(cue.id,cue.start_ms,cue.text[start:end],target,(start,end),
            reason='AI 名称建议，需要人工确认', confidence=.5, default_selected=False,
            source='ai_review', evidence=str(edit.get('basis') or edit.get('evidence') or ''),
            missing_evidence=labels[failure]+'；未核验原音'))
    return output, invalid


def local_review_candidates(cue, draft, candidates, scene, *, processing_id):
    """Near matches remain unselected suggestions; semantic rosters stay choices."""
    from .content_scene import alias_context_conflict
    from .stutter_cleanup import plausible_name_span
    output = []
    identifier=lambda char:char.isascii() and (char.isalnum() or char=='_')
    for candidate in candidates:
        for match in candidate.get('matches', ()):
            # Retrieval rows retain matches from the complete processing batch.
            # Stable project cue IDs are not processing IDs or numeric indexes.
            if type(match.get('cue_id')) is not int or match['cue_id'] != processing_id:
                continue
            a,b=match.get('start'),match.get('end')
            if a is None and b is None and match.get('method')=='single_hanzi_weak':
                import re
                positions=[m.span() for m in re.finditer(re.escape(str(match.get('heard',''))),draft)]
                if len(positions)==1:a,b=positions[0]
            if (match.get('asr_source') != 'text' or match.get('method') not in
                    {'phonetic','spelling','latin_identifier','single_hanzi_weak'}
                    or type(a) is not int or type(b) is not int
                    or not 0 <= a < b <= len(draft)):
                continue
            source,target=draft[a:b],candidate['canonical']
            heard=match.get('heard')
            if not isinstance(heard,str) or source.casefold()!=heard.casefold():
                continue
            if match['method']=='latin_identifier' and (not all(identifier(char) for char in source)
                    or a and identifier(draft[a-1]) or b<len(draft) and identifier(draft[b])):
                continue
            if not source or source == target or alias_context_conflict(draft,source,target,scene=scene,span=(a,b)):
                continue
            if any(row['canonical'].casefold()==source.casefold() and row['canonical']!=target for row in candidates):
                continue
            # A near sound alone is no reason to change a common word that
            # reads naturally in its sentence (学聪明了 -> 学虫鸣了, 2026-10-10).
            if match['method'] in {'phonetic','spelling'} and not plausible_name_span(draft,a,b):
                continue
            span=original_span(cue.text,draft,a,b)
            if span is None:continue
            output.append(TextOccurrence(cue.id,cue.start_ms,cue.text[span[0]:span[1]],target,span,
                reason='当前词库近似候选，需要人工确认',confidence=min(.7,float(match.get('score',.5))),
                default_selected=False,source='local_review',
                evidence='检索方式：'+match['method'],missing_evidence='缺少已确认别名或充分局部证据；未核验原音'))
    return output
