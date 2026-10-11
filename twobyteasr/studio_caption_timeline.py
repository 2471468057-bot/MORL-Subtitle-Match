"""Independent caption objects in integer project time, with immutable source receipts.

The additive studio_state receipt freezes the currently displayed legacy projection
once. It preserves original cues and acoustic evidence; video ownership never grants
or denies caption editing. All destructive interval edits use [start, end).
"""
from __future__ import annotations
import copy
import uuid
from dataclasses import asdict
from PySide6.QtGui import QUndoCommand

KEY = 'caption_timeline'
DISABLED_KEY = 'caption_ripple_disabled_speakers'
# Receipt field: project time minus the clock of the caption's evidence rows.
# Kept through moves, ripples, splits and merges; absent when unknown.
CLOCK = 'evidence_clock_offset_ms'


def independent_captions(project):
    return project.render_settings.get('_cue_domain') == 'timeline'


def ensure_independent_captions(project):
    """Idempotently freeze actual visible positions, never replay a historic cut."""
    if project is None or independent_captions(project):
        return False
    from .studio_edit_sequence import projected_cues, source_cue_id_of
    from .cue_word_alignment import cue_words
    original = copy.deepcopy(project.cues)
    visible = copy.deepcopy(projected_cues(project))
    sources = {c.id: c for c in original}
    instances = {}
    for cue in visible:
        source = sources.get(source_cue_id_of(cue.id), cue)
        words, reason = cue_words(project, cue)
        instances[cue.id] = {
            'source_cue_id': source.id,
            'source_start_ms': source.start_ms, 'source_end_ms': source.end_ms,
            'source_path': project.media.path,
            'evidence_refs': list(source.evidence_refs),
            'text': cue.text,
            'word_alignment': reason,
            'words': [asdict(w) for w in words],
            'word_base_interval': [cue.start_ms, cue.end_ms],
            'word_base_words': [asdict(w) for w in words],
            'word_base_alignment': reason,
        }
        if cue.end_ms - cue.start_ms == source.end_ms - source.start_ms:
            # An unclipped 1x projection: evidence time + this offset is
            # project time, so missing words can be re-derived later.
            instances[cue.id][CLOCK] = cue.start_ms - source.start_ms
        prior = (project.studio_state.get(KEY) or {}).get('instances', {}).get(source.id, {})
        if prior.get('source_spans'):
            instances[cue.id]['source_spans'] = copy.deepcopy(prior['source_spans'])
    project.studio_state[KEY] = {
        'version': 1, 'source_archive': [asdict(c) for c in original],
        'instances': instances,
    }
    project.cues = visible
    project.render_settings['_cue_domain'] = 'timeline'
    return True


def _word_clock(project, words, cache):
    """Most common project-minus-evidence offset of measured caption words."""
    from collections import Counter
    from .cue_word_alignment import evidence_tokens
    votes = Counter()
    for word in words:
        ref = word.evidence_ref
        if ref not in cache:
            records, _pending, _derived = evidence_tokens(project, [ref])
            index = {}
            for a, b, text, _ref in records:
                index.setdefault((text, b - a), []).append(a)
            cache[ref] = index
        starts = cache[ref].get((word.text, word.end_ms - word.start_ms), ())
        if len(starts) == 1:
            votes[word.start_ms - starts[0]] += 1
    if not votes:
        return None
    (offset, count), *rest = votes.most_common(2)
    return offset if count >= 2 and (not rest or rest[0][1] * 2 < count) else None


def recover_caption_words(project):
    """Re-derive missing caption words from the project's saved evidence.

    Earlier builds froze an empty word list whenever an edited spelling,
    a removed filler or a duplicated FireRed token blocked an exact match,
    and a split of such a caption stayed empty forever. The evidence is still
    in the project. Each caption is re-aligned on a clock taken from its own
    receipt, else from the nearest captions whose words map back to evidence,
    else zero; a clock counts only when the text aligns on the caption itself.
    Recovered receipts say so in ``word_recovery``. Returns the count.
    """
    if project is None or not independent_captions(project) or KEY not in project.studio_state:
        return 0
    import bisect
    from .cue_word_alignment import cue_words, recover_words_from_evidence
    receipts = project.studio_state[KEY].setdefault('instances', {})
    ordered = sorted(project.cues, key=lambda c: (c.start_ms, c.end_ms, c.id))
    cache = {}
    clocks = []
    missing = []
    for cue in ordered:
        receipt = receipts.get(cue.id)
        if not receipt:
            continue
        words, _reason = cue_words(project, cue)
        if not words:
            missing.append(cue)
        elif CLOCK in receipt:
            clocks.append((cue.start_ms, cue.speaker_id, int(receipt[CLOCK])))
        else:
            offset = _word_clock(project, words, cache)
            if offset is not None:
                clocks.append((cue.start_ms, cue.speaker_id, offset))
    starts = [row[0] for row in clocks]
    recovered = 0
    for cue in missing:
        receipt = receipts[cue.id]
        if CLOCK in receipt:
            candidates = [int(receipt[CLOCK])]
        else:
            at = bisect.bisect_left(starts, cue.start_ms)
            nearby = sorted(clocks[max(0, at - 4):at + 4],
                            key=lambda row: (row[1] != cue.speaker_id, abs(row[0] - cue.start_ms)))
            candidates = list(dict.fromkeys([row[2] for row in nearby] + [0]))
        words, reason, offset = recover_words_from_evidence(project, cue, receipt, candidates)
        if not words:
            continue
        previous = receipt.get('word_alignment', '')
        rows = [asdict(w) for w in words]
        receipt.update(text=cue.text, words=rows, word_alignment=reason,
                       word_base_interval=[cue.start_ms, cue.end_ms], word_base_words=copy.deepcopy(rows),
                       word_base_alignment=reason, word_clock_offset_ms=0)
        receipt[CLOCK] = offset
        receipt['word_recovery'] = {'source': 'project_asr_evidence', 'clock_offset_ms': offset,
                                    'previous_alignment': previous}
        recovered += 1
    return recovered


def locked_caption_speakers(project, page=None, explicit=()):
    locked = set(explicit) | set(project.studio_state.get('locked_speakers', ()))
    if page is not None:
        locked.update(getattr(page.timeline, 'locked_speakers', ()))
    return locked


def caption_ripple_skipped(project, locked=()):
    present = {c.speaker_id for c in project.cues}
    return present.intersection(set(locked) | set(project.studio_state.get(DISABLED_KEY, ())))


def _words(project, cue):
    from .cue_word_alignment import cue_words
    words, reason = cue_words(project, cue)
    return [asdict(w) for w in words], reason


def _remember(project, cue, parent, words, reason, review=None, clock_delta=0):
    state = project.studio_state.setdefault(KEY, {'version': 1, 'instances': {}})
    receipts = state.setdefault('instances', {})
    receipt = copy.deepcopy(receipts.get(parent.id, {}))
    receipt.update(text=cue.text, words=copy.deepcopy(words), word_alignment=reason,
                   word_base_interval=[cue.start_ms, cue.end_ms], word_base_words=copy.deepcopy(words),
                   word_base_alignment=reason, word_clock_offset_ms=0)
    if CLOCK in receipt:
        receipt[CLOCK] = int(receipt[CLOCK]) + int(clock_delta)
    if review:
        receipt['needs_review'] = review
        from .studio_edit_sequence import source_cue_id_of
        statuses = project.studio_state.setdefault('cue_statuses', {})
        statuses[source_cue_id_of(cue.id)] = 'issue'
    receipts[cue.id] = receipt


def shift_caption(project, cue, delta):
    words, reason = _words(project, cue)
    for word in words:
        word['start_ms'] += delta; word['end_ms'] += delta
    cue.start_ms += delta; cue.end_ms += delta
    _remember(project, cue, cue, words, reason, clock_delta=delta)


def sync_caption_interval_words(project, cue, previous):
    """Trim only the display envelope; move measured words by a rigid offset."""
    if not independent_captions(project):
        return
    receipt = project.studio_state.get(KEY, {}).get('instances', {}).get(cue.id)
    if not receipt:
        return
    base_start, base_end = receipt.setdefault('word_base_interval', list(previous))
    base_words = receipt.setdefault('word_base_words', copy.deepcopy(receipt.get('words', ())))
    base_alignment = receipt.setdefault('word_base_alignment', receipt.get('word_alignment', 'missing_word_timestamps'))
    offset = int(receipt.get('word_clock_offset_ms', 0))
    if cue.end_ms-cue.start_ms == previous[1]-previous[0]:
        offset += cue.start_ms-previous[0]
        if CLOCK in receipt:
            receipt[CLOCK] = int(receipt[CLOCK]) + cue.start_ms-previous[0]
    receipt['word_clock_offset_ms'] = offset
    receipt['words'] = copy.deepcopy(base_words)
    for word in receipt['words']:
        word['start_ms'] += offset; word['end_ms'] += offset
    receipt['word_alignment'] = base_alignment
    receipt['display_interval'] = [cue.start_ms, cue.end_ms]



def caption_replacement_receipts(project, removed, inserted):
    """Keep proven token order for structural splits/merges, with local undo data."""
    if not independent_captions(project) or KEY not in project.studio_state:
        return None, None
    from .cue_word_alignment import content_positions
    receipts=project.studio_state[KEY].get('instances', {})
    keys={c.id for c in (*removed,*inserted)}
    before={key:copy.deepcopy(receipts.get(key)) for key in keys}
    after=copy.deepcopy(before)
    stream=[];tokens=[];cursor=0;derived=False
    for cue in removed:
        positions=content_positions(cue.text);stream.extend(char for _,char in positions)
        words,source_reason=_words(project,cue)
        derived=derived or source_reason=='derived_term_source_span'
        for word in words:
            lo=cursor+sum(index<word['char_start'] for index,_ in positions)
            hi=cursor+sum(index<word['char_end'] for index,_ in positions)
            tokens.append((lo,hi,word))
        cursor+=len(positions)
    wanted=[char for cue in inserted for _,char in content_positions(cue.text)]
    conserved=wanted==stream and bool(tokens)
    cursor=0
    for cue in inserted:
        positions=content_positions(cue.text);end=cursor+len(positions)
        rows=[(lo,hi,word) for lo,hi,word in tokens if cursor<=lo<hi<=end]
        complete=bool(rows) and rows[0][0]==cursor and rows[-1][1]==end and all(
            b[0]==a[1] for a,b in zip(rows,rows[1:]))
        words=[]
        if conserved and complete:
            for lo,hi,word in rows:
                item=copy.deepcopy(word)
                item['char_start']=positions[lo-cursor][0]
                item['char_end']=positions[hi-cursor-1][0]+1
                words.append(item)
        parent=next((c for c in removed if c.id==cue.id),removed[0] if removed else None)
        receipt=copy.deepcopy(receipts.get(parent.id,{})) if parent else {}
        ids=list(dict.fromkeys(source for c in removed for source in receipts.get(c.id,{}).get(
            'source_cue_ids',[receipts.get(c.id,{}).get('source_cue_id',c.id)])))
        spans = []
        for original in removed:
            for span in receipts.get(original.id, {}).get('source_spans', []):
                if span not in spans:
                    spans.append(copy.deepcopy(span))
        if spans:
            receipt['source_spans'] = spans
        clocks={receipts.get(c.id,{}).get(CLOCK) for c in removed}
        if len(clocks)==1 and None not in clocks:
            receipt[CLOCK]=next(iter(clocks))
        else:
            receipt.pop(CLOCK,None)
        # A split keeps the measured basis of its parent words, including
        # whole replaced spans; it never re-allocates them.
        reason=('derived_term_source_span' if derived else 'exact_token_text') if words else 'structural_edit_requires_acoustic_alignment'
        receipt.update(text=cue.text,words=words,word_alignment=reason,
            word_base_interval=[cue.start_ms,cue.end_ms],word_base_words=copy.deepcopy(words),
            word_base_alignment=reason,source_cue_ids=ids,word_clock_offset_ms=0)
        after[cue.id]=receipt;cursor=end
    return before,after

def ripple_caption_range(project, start, end, *, locked=()):
    """Apply one deletion once to all eligible caption tracks.

    Exact tokens remain indivisible. Without an exact token stream, retain text
    once in the surviving compressed interval and mark it for manual review.
    This never distributes text proportionally or duplicates a whole sentence.
    """
    ensure_independent_captions(project)
    delta = end-start
    skipped = caption_ripple_skipped(project, locked)
    output = []
    for cue in project.cues:
        a, b = cue.start_ms, cue.end_ms
        if cue.speaker_id in skipped or b <= start:
            output.append(cue); continue
        if a >= end:
            shift_caption(project, cue, -delta); output.append(cue); continue
        if start <= a and b <= end:
            continue
        words, reason = _words(project, cue)
        if words:
            left = [w for w in words if w['end_ms'] <= start]
            right = [w for w in words if w['start_ms'] >= end]
            removed_boundary_words = any(w['start_ms'] < end and w['end_ms'] > start for w in words)
            groups = [(left, 0), (right, -delta)]
            kept = 0
            for rows, offset in groups:
                if not rows:
                    continue
                item = copy.deepcopy(cue)
                if kept:
                    item.id = cue.id + '-part-' + uuid.uuid4().hex[:10]
                lo, hi = rows[0]['char_start'], rows[-1]['char_end']
                if rows[0] is words[0]: lo = 0
                if rows[-1] is words[-1]: hi = len(cue.text)
                item.text = cue.text[lo:hi]
                item.start_ms = max(a, rows[0]['start_ms']) + offset
                item.end_ms = min(b, rows[-1]['end_ms']) + offset
                if item.end_ms <= item.start_ms or not item.text.strip():
                    continue
                adjusted = copy.deepcopy(rows)
                for w in adjusted:
                    w['char_start'] -= lo; w['char_end'] -= lo
                    w['start_ms'] += offset; w['end_ms'] += offset
                _remember(project, item, cue, adjusted, reason,
                          'word_crosses_deleted_boundary' if removed_boundary_words else None,
                          clock_delta=offset)
                output.append(item); kept += 1
            if kept:
                continue
            # No complete token survives, but surviving speech time is still
            # retained once with an explicit review receipt.
            reason = 'no_complete_surviving_token'
        item = copy.deepcopy(cue)
        item.start_ms = a if a < start else start
        item.end_ms = b-delta if b > end else start
        if item.end_ms > item.start_ms:
            _remember(project, item, cue, [], reason,
                      'ripple_boundary_requires_manual_text_review:' + reason)
            if a < start and b > end:
                # Text spans both sides of the deleted range: no single clock.
                project.studio_state[KEY]['instances'][item.id].pop(CLOCK, None)
            elif a >= start and CLOCK in project.studio_state[KEY]['instances'][item.id]:
                project.studio_state[KEY]['instances'][item.id][CLOCK] -= delta
            output.append(item)
    project.cues = sorted(output, key=lambda c: (c.start_ms, c.end_ms, c.id))
    return skipped


class SetCaptionRippleCommand(QUndoCommand):
    def __init__(self, project, speaker_id, enabled, changed=None):
        super().__init__('跟随波纹编辑' if enabled else '停止跟随波纹编辑')
        self.project, self.changed = project, changed
        self.before = list(project.studio_state.get(DISABLED_KEY, ()))
        disabled = set(self.before)
        disabled.discard(speaker_id) if enabled else disabled.add(speaker_id)
        self.after = sorted(disabled)

    def _apply(self, values):
        from .studio_runtime_state import state_for, DirtyDomain as D
        with state_for(self.project).transaction(self.project, action_id=self.text(),
                dirty=D.PROJECT_METADATA | D.TIMELINE_PIXELS | D.AUTOSAVE):
            self.project.studio_state[DISABLED_KEY] = list(values)
        if self.changed: self.changed()

    def redo(self): self._apply(self.after)
    def undo(self): self._apply(self.before)


def set_caption_ripple_command(project, speaker_id, enabled, changed=None):
    return SetCaptionRippleCommand(project, speaker_id, enabled, changed)
