"""Where FireRed and Qwen both heard something else than the caption says.

2026-10-10 (user, 天命之暗 vs 今天运气站/在): the recognition-time consensus
only replaces text when both models give the very same, equal-length
replacement, and the AI pass that decides the rest can time out. The
proofreading page shows the remaining cases: agreement is proposed ticked,
a near-agreement lists both readings for the user to pick.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

PARTICLES = frozenset('啊呀呢吧嘛吗啦哦呃嗯哈诶欸唉哎噢喔')
QUIET = frozenset(' ，。！？、,.!?；;：:…~～')
MAX_SPAN = 8


def _regions(source, ref):
    """Differing regions; two edits one equal character apart are one region."""
    ops = SequenceMatcher(None, source, ref, autojunk=False).get_opcodes()
    regions = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == 'equal':
            continue
        if regions and i1 - regions[-1][1] <= 1 and j1 - regions[-1][3] <= 1:
            regions[-1] = (regions[-1][0], i2, regions[-1][2], j2)
        else:
            regions.append((i1, i2, j1, j2))
    return ops, regions


def _map(ops, position, side):
    for tag, i1, i2, j1, j2 in ops:
        if i1 <= position <= i2:
            if tag == 'equal':
                return j1 + position - i1
            if position == i1 and side == 'start':
                return j1
            if position == i2 and side == 'end':
                return j2
            return None
    return None


def _core(text):
    return ''.join(char for char in text if char not in PARTICLES and char not in QUIET)


def _find_all(text, word):
    at = text.find(word)
    while at >= 0:
        yield at
        at = text.find(word, at + 1)


def evidence_occurrences(source, firered, qwen, *, protected=()):
    """[(span, original, replacement, agreed, provider)] against ``source``."""
    if not (source and firered and qwen):
        return []
    for ref in (firered, qwen):
        if SequenceMatcher(None, source, ref, autojunk=False).ratio() < .58:
            return []  # a different window or a different sentence, not a reading
    ops_f, regions_f = _regions(source, firered)
    ops_q, regions_q = _regions(source, qwen)
    guarded = [(at, at + len(word)) for word in protected if word and len(word) >= 2
               for at in _find_all(source, word)]
    found, seen = [], set()
    for a, b, _j, _k in regions_f:
        for c, d, _m, _n in regions_q:
            if c > b or a > d:
                continue
            start, end = min(a, c), max(b, d)
            for _ in range(4):
                spans = (_map(ops_f, start, 'start'), _map(ops_f, end, 'end'),
                         _map(ops_q, start, 'start'), _map(ops_q, end, 'end'))
                if None not in spans:
                    break
                start, end = max(0, start - 1), min(len(source), end + 1)
            else:
                continue
            if (start, end) in seen:
                continue
            seen.add((start, end))
            old, by_f, by_q = source[start:end], firered[spans[0]:spans[1]], qwen[spans[2]:spans[3]]
            # Window edges bleed in words of the neighbouring captions. One
            # character is enough only when both models agree on it.
            least = 1 if by_f == by_q else 2
            if start == 0 or end == len(source) or len(_core(old)) < least or end - start > MAX_SPAN:
                continue
            if any(abs(len(new) - len(old)) > 1 or len(_core(new)) < least for new in (by_f, by_q)):
                continue
            if re.search(r'[A-Za-z0-9]', old + by_f + by_q):
                continue  # spelling and case of names belong to the glossary
            if _core(old) in {_core(by_f), _core(by_q)}:
                continue  # only particles or punctuation differ
            if any(x < end and start < y for x, y in guarded):
                continue  # a glossary name is never reverted to a raw reading
            if by_f == by_q:
                found.append(((start, end), old, by_f, True, 'FireRed+Qwen'))
            elif SequenceMatcher(None, by_f, by_q, autojunk=False).ratio() >= .6:
                found.append(((start, end), old, by_f, False, 'FireRed'))
                found.append(((start, end), old, by_q, False, 'Qwen'))
    return found


def project_evidence(project, protected=()):
    """{cue_id: (recognized_text, occurrences)} for captions with a reading to offer."""
    from .studio_qc import model_evidence
    result = {}
    for cue in project.cues:
        texts = {}
        for row in model_evidence(project, cue):
            label = row.label.lower()
            for key in ('moss', 'firered', 'qwen'):
                if key in label:
                    texts.setdefault(key, row.text)
        # The model windows can reach into the neighbouring captions; compare
        # with the caption itself so edges and positions are its own.
        source = cue.text
        hits = evidence_occurrences(source, texts.get('firered', ''), texts.get('qwen', ''), protected=protected)
        if hits:
            result[cue.id] = (source, hits)
    return result
