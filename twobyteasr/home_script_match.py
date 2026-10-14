"""首页「匹配文稿」 (2026-10-14): new media plus the user's own script.

The user already has the complete text, broken into subtitle lines. Only the
character-timestamp model runs: the local FireRedASR2-AED worker reports the
characters it hears with their times, ``script_match`` places the user's lines
on those times, and the result opens in Studio. MOSS, Qwen3-ASR review, AI
proofreading and AI line breaking never run, and nothing is uploaded. The
heard characters are kept as the project's word evidence, so Studio's word
timing and razor cuts work on the new captions as usual.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import uuid

from PySide6.QtCore import QThread, Signal

from .i18n import tr
from .script_match import ScriptMatch, ScriptMatchError, Token, match_script, parse_script

TIMESTAMP_MODEL = 'FireRedASR2-AED'
MODEL_KEY = 'firered_aed'


def timestamp_model_ready() -> tuple[bool, str]:
    """Is the character-timestamp model installed with its runtime?"""
    try:
        from .model_registry import installed_model_keys
        from .runtime_paths import get_runtime_paths
        if MODEL_KEY not in installed_model_keys(get_runtime_paths().install_root):
            return False, tr('需要先在模型工坊安装 {model}（提供字级时间）', model=TIMESTAMP_MODEL)
        from .asr import _main_worker_python
        runtime = _main_worker_python()
        if not runtime or not Path(runtime).is_file():
            return False, tr('模型运行环境还没准备好，请在模型工坊准备 {model}', model=TIMESTAMP_MODEL)
    except Exception as exc:  # any probe failure reads as "not ready", with the reason
        return False, str(exc)
    return True, ''


def heard_tokens(media_path: str, progress=None) -> tuple[list[Token], dict[str, dict], list[tuple[int, int]]]:
    """FireRed's heard characters on the media clock, the evidence rows they came
    from, and the speech regions of a plain energy VAD (no model)."""
    from .asr import _transcribe_firered_worker
    from .cache import decode_audio_to_array
    from .runtime_paths import resolve_model_dir
    if progress:
        progress(tr('读取音频…'))
    audio = decode_audio_to_array(media_path)
    seconds = len(audio) / 16000.0
    if seconds <= 0.05:
        raise ScriptMatchError(tr('素材里没有可用的音频'))
    if progress:
        progress(tr('{model} 正在生成字级时间（只听字和时间，不改你的文稿）…', model=TIMESTAMP_MODEL))
    try:
        import moss_firered_pipeline
        regions = moss_firered_pipeline.detect_lightweight_vad(audio, SimpleNamespace(AUDIO_SAMPLE_RATE=16000))
        speech = [(round(r['start'] * 1000), round(r['end'] * 1000)) for r in regions]
    except Exception:  # no usable regions: lines keep FireRed's own edges
        speech = []
    normalized = _transcribe_firered_worker(audio, seconds, str(resolve_model_dir('FireRedASR2-AED')))
    tokens: list[Token] = []
    rows: dict[str, dict] = {}
    for index, segment in enumerate(normalized.get('segments', ()), 1):
        ref = f'firered:{index}'
        words = []
        for token in segment.get('tokens', ()):
            start, end = round(float(token['start']) * 1000), round(float(token['end']) * 1000)
            if end <= start or not str(token.get('text', '')).strip():
                continue
            words.append({'text': str(token['text']), 'start_ms': start, 'end_ms': end})
            tokens.append(Token(start, end, str(token['text']), ref, 'S00'))
        if words:
            rows[ref] = {'text': str(segment.get('text', '')), 'words': words,
                         'start_ms': words[0]['start_ms'], 'end_ms': words[-1]['end_ms'],
                         'final_timing_owner': TIMESTAMP_MODEL, 'source': 'script_match'}
    return tokens, rows, speech


def build_project(media_path: str, match: ScriptMatch, rows: dict[str, dict]):
    from .recognition_result import recognition_project_path
    from .studio_project import project_from_runtime_cues, save_project
    cues = [SimpleNamespace(cue_id=f'script-{line.index + 1}', start=line.start_ms / 1000, end=line.end_ms / 1000,
                            text=line.text, speaker='S00') for line in match.lines]
    review = [f'script-{line.index + 1}' for line in match.lines if line.needs_review]
    project = project_from_runtime_cues(media_path, cues, asr_evidence=rows, generation_metadata={
        'script_match': {'version': 1, 'timestamp_source': TIMESTAMP_MODEL, 'lines': len(match.lines),
                         'coverage': round(match.coverage, 4), 'review_cue_ids': review,
                         'note': '用户文稿按字级时间对齐；未调用其他识别模型或 AI。'},
        'language': {'code': 'zh', 'requested': 'zh', 'evidence': {'source': 'script_match'}},
    })
    by_id = {line_id: line for line_id, line in zip((c.cue_id for c in cues), match.lines)}
    for cue in project.cues:
        line = by_id.get(cue.id)
        if line is not None:
            cue.evidence_refs = [ref for ref in line.refs if ref in rows]
    if review:
        project.studio_state.setdefault('cue_statuses', {}).update({cue_id: 'issue' for cue_id in review})
    path = recognition_project_path(media_path, 'script-' + uuid.uuid4().hex[:16])
    path.parent.mkdir(parents=True, exist_ok=True)
    return save_project(project, path)


class ScriptMatchJob(QThread):
    progressed = Signal(str)
    succeeded = Signal(str, object)
    failed = Signal(str)

    def __init__(self, media_path: str, lines: list[str], parent=None):
        super().__init__(parent)
        self.media_path, self.lines = str(media_path), list(lines)

    def run(self):
        try:
            tokens, rows, speech = heard_tokens(self.media_path, self.progressed.emit)
            self.progressed.emit(tr('按字级时间对齐文稿…'))
            match = match_script(self.lines, tokens, speech_regions_ms=speech)
            path = build_project(self.media_path, match, rows)
            self.succeeded.emit(str(path), match)
        except Exception as exc:
            self.failed.emit(str(exc) or type(exc).__name__)


def open_home_script_match(window) -> None:
    from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar,
                                   QPushButton, QVBoxLayout)
    from .design.presentation import button_role
    from .studio_script_match import read_script_file
    media = [str(path) for path in getattr(window, 'media_paths', ()) if str(path).strip()]
    state = {'media': media[0] if media else '', 'job': None}

    class _Dialog(QDialog):
        def reject(self):  # ×, Esc and 取消 wait while the timestamp job runs
            if state['job'] is None:
                super().reject()

    dialog = _Dialog(window)
    dialog.setObjectName('homeScriptMatchDialog')
    dialog.setWindowTitle(tr('匹配文稿'))
    dialog.resize(760, 620)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(20, 18, 20, 16)
    layout.setSpacing(10)
    intro = QLabel(tr('你已经有完整文稿并断好句：每行一条字幕。这里只生成字级时间来对齐，文字保持你输入的样子。'))
    intro.setWordWrap(True)
    layout.addWidget(intro)
    media_row = QHBoxLayout()
    media_label = QLabel()
    media_label.setObjectName('homeScriptMatchMedia')
    media_label.setWordWrap(True)
    choose = button_role(QPushButton(tr('选择素材…')), 'secondary')
    media_row.addWidget(media_label, 1)
    media_row.addWidget(choose)
    layout.addLayout(media_row)
    script = QPlainTextEdit()
    script.setObjectName('homeScriptMatchInput')
    script.setPlaceholderText(tr('每行一条字幕，例如：\n大家好，欢迎回来\n今天我们继续打洛克王国'))
    layout.addWidget(script, 1)
    runs = QLabel(tr('只运行：{model} 字级时间（本机显卡）。不会运行 MOSS、Qwen3-ASR 复核、AI 校对与 AI 断句，也不上传。'
                     '适用于中文（含中英混合）。', model=TIMESTAMP_MODEL))
    runs.setObjectName('homeScriptMatchRuns')
    runs.setWordWrap(True)
    layout.addWidget(runs)
    status = QLabel('')
    status.setObjectName('homeScriptMatchStatus')
    status.setWordWrap(True)
    layout.addWidget(status)
    bar = QProgressBar()
    bar.setRange(0, 0)
    bar.setTextVisible(False)
    bar.setFixedHeight(6)
    bar.hide()
    layout.addWidget(bar)
    actions = QHBoxLayout()
    load = button_role(QPushButton(tr('从文件读取…')), 'secondary')
    workshop = button_role(QPushButton(tr('打开模型工坊')), 'secondary')
    cancel = button_role(QPushButton(tr('取消')), 'secondary')
    start = button_role(QPushButton(tr('开始匹配')), 'primary')
    actions.addWidget(load)
    actions.addWidget(workshop)
    actions.addStretch(1)
    actions.addWidget(cancel)
    actions.addWidget(start)
    layout.addLayout(actions)

    def refresh():
        name = Path(state['media']).name if state['media'] else ''
        media_label.setText(tr('素材：{name}', name=name) if name else tr('素材：还没选择'))
        if len(media) > 1 and state['media'] == media[0]:
            media_label.setText(media_label.text() + tr('（本批共 {count} 个，只匹配第一个）', count=len(media)))
        ready, reason = timestamp_model_ready()
        workshop.setVisible(not ready)
        if state['job'] is None:
            status.setText('' if ready else reason)
        start.setEnabled(bool(ready and state['media'] and state['job'] is None))

    def choose_media():
        from .main_ui_helpers import SUPPORTED_MEDIA_SUFFIXES
        pattern = ' '.join('*' + suffix for suffix in sorted(SUPPORTED_MEDIA_SUFFIXES))
        path, _ = QFileDialog.getOpenFileName(dialog, tr('选择素材'), '', tr('音视频 ({pattern})', pattern=pattern))
        if path:
            state['media'] = path
            refresh()

    def load_file():
        path, _ = QFileDialog.getOpenFileName(dialog, tr('选择文稿'), '', tr('文本文件 (*.txt);;所有文件 (*)'))
        if path:
            try:
                script.setPlainText(read_script_file(path))
            except (OSError, ValueError) as exc:
                status.setText(str(exc))

    def finished(path, match):
        bar.hide()
        state['job'] = None
        status.setText(tr('共 {count} 句；文稿 {coverage}% 的字对上了字级时间；{review} 句标为待检查。正在打开工作台…',
                          count=len(match.lines), coverage=round(match.coverage * 100), review=match.review_count))
        dialog.accept()
        window.open_studio_project(path, mode='edit', source='script_match')

    def failed(message):
        bar.hide()
        state['job'] = None
        status.setText(tr('匹配没有完成：{error}', error=message))
        for widget in (script, load, choose, cancel):
            widget.setEnabled(True)
        refresh()

    def begin():
        lines = parse_script(script.toPlainText())
        if not lines:
            status.setText(tr('文稿是空的：每行一条字幕'))
            return
        job = ScriptMatchJob(state['media'], lines, dialog)
        state['job'] = job
        job.progressed.connect(status.setText)
        job.succeeded.connect(finished)
        job.failed.connect(failed)
        for widget in (script, load, choose, start, cancel):
            widget.setEnabled(False)
        bar.show()
        job.start()

    choose.clicked.connect(choose_media)
    load.clicked.connect(load_file)
    workshop.clicked.connect(lambda: (dialog.reject(), window._open_model_workshop()))
    cancel.clicked.connect(dialog.reject)
    start.clicked.connect(begin)
    refresh()
    window._home_script_match_dialog = dialog
    dialog._begin = begin  # automated checks drive the real handlers
    dialog._script = script
    dialog._state = state
    try:
        dialog.exec()
    finally:
        window._home_script_match_dialog = None
        job = state['job']
        if job is not None:
            job.wait()


__all__ = ['ScriptMatchJob', 'build_project', 'heard_tokens', 'open_home_script_match', 'timestamp_model_ready']
