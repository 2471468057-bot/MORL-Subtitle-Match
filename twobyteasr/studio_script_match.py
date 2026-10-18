"""Studio 「匹配文稿」 (2026-10-14).

The user pastes a complete script that is already broken into subtitle lines.
Every line becomes one caption, timed only by the word timestamps this
project already has (see ``script_match``); no model, AI or network call is
made. The replacement is one undo step that also carries each new caption's
word receipt, so word timing, razor cuts and review keep working. Lines that
could not be heard are placed between their neighbours and marked 待检查.
"""
from __future__ import annotations

from collections import Counter
import copy
from dataclasses import asdict
from pathlib import Path
import uuid

from .i18n import tr
from .script_match import ScriptMatch, ScriptMatchError, match_script, parse_script, tokens_from_project
from .studio_commands import MutationOrigin, ReplaceCuesCommand

REVIEW_REASON = 'script_match_needs_review'


def read_script_file(path) -> str:
    raw = Path(path).read_bytes()
    for encoding in ('utf-8-sig', 'utf-16', 'gb18030'):
        try:
            text = raw.decode(encoding)
        except UnicodeError:
            continue
        if encoding == 'utf-16' and not raw.startswith((b'\xff\xfe', b'\xfe\xff')):
            continue
        return text
    raise ValueError(tr('无法识别文件编码，请另存为 UTF-8 文本'))


def match_project(project, text: str) -> tuple[list[str], ScriptMatch]:
    lines = parse_script(text)
    if not lines:
        raise ScriptMatchError(tr('文稿是空的：每行一条字幕'))
    tokens = tokens_from_project(project)
    if not tokens:
        raise ScriptMatchError(tr('这个工程还没有字级时间：请先识别，或在首页用「匹配文稿」生成'))
    # 2026-10-15: the project's spoken language picks the comparison rules
    # (Japanese kana/kanji, English letters); Chinese keeps homophone anchoring.
    from .language_rules import detect_language, project_language
    try:
        language = project_language(project) or detect_language(lines)[0]
    except Exception:
        language = ''
    return lines, match_script(lines, tokens, language=language)


def _overlap(cue, start, end) -> int:
    return min(cue.end_ms, end) - max(cue.start_ms, start)


def build_replacement(project, match: ScriptMatch):
    """New cues, their caption receipts and the ids to review."""
    from .studio_project import StudioCue
    originals = sorted(project.cues, key=lambda c: (c.start_ms, c.end_ms))
    speakers = [speaker.id for speaker in getattr(project, 'speakers', ())]
    fallback_speaker = (Counter(c.speaker_id for c in originals).most_common(1) or [(speakers[0] if speakers else 'S00', 0)])[0][0]
    cues, receipts, review = [], {}, []
    previous_speaker = fallback_speaker
    for line in match.lines:
        overlapping = [c for c in originals if _overlap(c, line.start_ms, line.end_ms) > 0]
        template = (max(overlapping, key=lambda c: _overlap(c, line.start_ms, line.end_ms)) if overlapping else
                    min(originals, key=lambda c: abs(c.start_ms - line.start_ms)) if originals else None)
        speaker = line.speaker or previous_speaker
        if speakers and speaker not in speakers:
            speaker = previous_speaker if previous_speaker in speakers else speakers[0]
        previous_speaker = speaker
        cue = StudioCue(id='script-' + uuid.uuid4().hex[:12], start_ms=line.start_ms, end_ms=line.end_ms,
                        text=line.text, speaker_id=speaker,
                        style_id=template.style_id if template else 'default',
                        base_preset_id=template.base_preset_id if template else '',
                        effect_id=template.effect_id if template else 'none',
                        original_text=line.text,
                        evidence_refs=[ref for ref in line.refs if not ref.startswith('cue-estimate:')])
        cue.validate()
        words = [asdict(word) for word in line.words]
        reason = line.word_reason if words else (line.word_reason or 'missing_word_timestamps')
        receipt = dict(text=line.text, words=words, word_alignment=reason,
                       word_base_interval=[cue.start_ms, cue.end_ms], word_base_words=copy.deepcopy(words),
                       word_base_alignment=reason, word_clock_offset_ms=0,
                       source_cue_ids=[c.id for c in overlapping], evidence_refs=list(cue.evidence_refs),
                       script_match=dict(version=1, placed_by=line.placed_by, coverage=round(line.coverage, 3),
                                         edges_estimated=line.edges_estimated))
        if line.needs_review:
            receipt['needs_review'] = REVIEW_REASON
            review.append(cue.id)
        receipts[cue.id] = receipt
        cues.append(cue)
    return cues, receipts, review


class MatchScriptCommand(ReplaceCuesCommand):
    """All captions replaced by the script in one step, with their word receipts."""

    def __init__(self, project, cues, receipts, review_ids, changed=None):
        super().__init__(project, cues, tr('匹配文稿（{count} 条）', count=len(cues)), changed, MutationOrigin.IMPORT)
        from .studio_caption_timeline import KEY
        state = project.studio_state.get(KEY) or {}
        self._key = KEY
        self._receipts_before = copy.deepcopy(state.get('instances', {})) if KEY in project.studio_state else None
        self._receipts_after = copy.deepcopy(receipts)
        self._statuses_before = copy.deepcopy(project.studio_state.get('cue_statuses'))
        self._statuses_after = {cue_id: 'issue' for cue_id in review_ids}
        self._forward = True

    def _mutate(self, cues):
        super()._mutate(cues)
        state = self.project.studio_state
        if self._forward:
            if self._receipts_before is not None:
                instances = state[self._key].setdefault('instances', {})
                for cue_id in [c.id for c in self.before]:
                    instances.pop(cue_id, None)
                instances.update(copy.deepcopy(self._receipts_after))
            statuses = {k: v for k, v in (self._statuses_before or {}).items()
                        if k not in {c.id for c in self.before}}
            statuses.update(self._statuses_after)
            state['cue_statuses'] = statuses
        else:
            if self._receipts_before is not None:
                state[self._key]['instances'] = copy.deepcopy(self._receipts_before)
            if self._statuses_before is None:
                state.pop('cue_statuses', None)
            else:
                state['cue_statuses'] = copy.deepcopy(self._statuses_before)

    def redo(self):
        self._forward = True
        super().redo()

    def undo(self):
        self._forward = False
        super().undo()


def apply_match(page, match: ScriptMatch) -> MatchScriptCommand:
    cues, receipts, review = build_replacement(page.project, match)
    command = MatchScriptCommand(page.project, cues, receipts, review, getattr(page, '_changed', None))
    page.undo_stack.push(command)
    for refresh in ('cue_model', 'timeline'):
        target = getattr(page, refresh, None)
        if target is not None and hasattr(target, 'set_project'):
            target.set_project(page.project)
    if hasattr(page, '_populate_speakers'):
        page._populate_speakers()
    if cues and hasattr(page, 'select_cue'):
        page.select_cue(cues[0].id)
    return command


def _format_ms(value: int) -> str:
    seconds, ms = divmod(int(value), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}' if hours else f'{minutes:02d}:{seconds:02d}.{ms:03d}'


def line_status(line) -> str:
    if line.placed_by == 'estimated_between_neighbours':
        return tr('未听到 · 按前后估算')
    if line.placed_by == 'estimated_tokens':
        return tr('{value}% · 时间为估算', value=round(line.coverage * 100))
    if line.needs_review:
        return tr('{value}% · 待检查', value=round(line.coverage * 100))
    return tr('{value}%', value=round(line.coverage * 100))


def build_script_match_widget(page, parent=None, *, on_done=None):
    """构建文稿匹配界面，返回 (root_widget, api)。

    2026-10-18（用户："将文稿匹配也做到工具面板内"）：原来只能以对话框打开，
    这里把界面构建抽出来，工具面板与（保留的）对话框共用同一份实现，避免两套 UI
    各自演化。``on_done`` 在成功替换全部字幕后调用（对话框用它关闭自己）。
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout, QHeaderView,
                                   QLabel, QPlainTextEdit, QPushButton, QSizePolicy, QSplitter,
                                   QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
    from .i18n_widgets import bind_text
    from .design.presentation import button_role

    project = getattr(page, 'project', None)
    root = QWidget(parent)
    root.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    intro = QLabel(tr('粘贴已断好句的完整文稿，每行一条字幕。只用工程里已有的字级时间对齐，'
                      '不调用识别模型或 AI；文字保持你输入的样子。'))
    intro.setWordWrap(True)
    # 说明文字与底栏固定高度，优先保证「匹配预览 / 替换全部字幕」按钮不被挤出可视区。
    intro.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
    layout.addWidget(intro, 0)
    split = QSplitter(Qt.Orientation.Vertical, root)
    split.setChildrenCollapsible(False)
    left = QPlainTextEdit(split)
    left.setObjectName('scriptMatchInput')
    left.setMinimumHeight(72)
    left.setPlaceholderText(tr('每行一条字幕，例如：\n大家好，欢迎回来\n今天我们继续打洛克王国'))
    table = QTableWidget(0, 3, split)
    table.setObjectName('scriptMatchPreview')
    table.setHorizontalHeaderLabels([tr('开始'), tr('文稿'), tr('匹配')])
    table.verticalHeader().hide()
    table.setMinimumHeight(64)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    split.setSizes([220, 240])
    layout.addWidget(split, 1)
    summary = QLabel(tr('贴上文稿后点「匹配预览」。'))
    summary.setObjectName('scriptMatchSummary')
    summary.setWordWrap(True)
    summary.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
    layout.addWidget(summary, 0)
    # 2026-10-18（用户："文稿匹配使用项目原有的逻辑 可以进行替换和直接生成"）：
    # 两种方式都复用手头已有的实现，不新造识别逻辑——
    #   替换：match_project + apply_match（用工程里已有的字级时间，一步可撤销）
    #   生成：home_script_match.ScriptMatchJob（现听写字级时间，再建新工程）
    # 默认"替换"；工程里没有字级时间时，替换会提示改用生成。
    mode_row = QHBoxLayout()
    mode_row.addWidget(QLabel(tr('方式')))
    mode_box = QComboBox()
    mode_box.setObjectName('scriptMatchMode')
    mode_box.addItem(tr('替换工程字幕（用已有字级时间）'), 'replace')
    mode_box.addItem(tr('直接生成（现听写字级时间）'), 'create')
    mode_row.addWidget(mode_box, 1)
    mode_wrap = QWidget(root)
    mode_wrap.setLayout(mode_row)
    mode_wrap.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    layout.addWidget(mode_wrap, 0)
    actions = QHBoxLayout()
    load = button_role(QPushButton(tr('从文件读取…')), 'secondary')
    preview = button_role(QPushButton(tr('匹配预览')), 'secondary')
    apply = button_role(QPushButton(tr('替换全部字幕')), 'primary')
    apply.setEnabled(False)
    actions.addWidget(load)
    actions.addStretch(1)
    actions.addWidget(preview)
    actions.addWidget(apply)
    action_row = QWidget(root)
    action_row.setLayout(actions)
    action_row.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    layout.addWidget(action_row, 0)
    state = {'match': None, 'text': None, 'job': None}

    def load_file():
        path, _ = QFileDialog.getOpenFileName(root, tr('选择文稿'), '', tr('文本文件 (*.txt);;所有文件 (*)'))
        if path:
            try:
                left.setPlainText(read_script_file(path))
            except (OSError, ValueError) as exc:
                summary.setText(str(exc))

    def run_preview():
        current = getattr(page, 'project', None)
        if current is None:
            summary.setText(tr('请先打开工程'))
            return
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            text = left.toPlainText()
            _lines, match = match_project(current, text)
        except ScriptMatchError as exc:
            state['match'] = None
            apply.setEnabled(False)
            table.setRowCount(0)
            summary.setText(str(exc))
            return
        finally:
            QGuiApplication.restoreOverrideCursor()
        state['match'], state['text'] = match, text
        table.setRowCount(len(match.lines))
        for row, line in enumerate(match.lines):
            values = (_format_ms(line.start_ms), line.text, line_status(line))
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 2 and line.needs_review:
                    font = item.font(); font.setBold(True); item.setFont(font)
                table.setItem(row, column, item)
        summary.setText(tr('共 {count} 句；文稿 {coverage}% 的字对上了字级时间；{review} 句标为待检查。'
                           '替换后可用 Ctrl+Z 一步恢复。', count=len(match.lines),
                           coverage=round(match.coverage * 100), review=match.review_count))
        apply.setEnabled(True)

    def accept():
        if state['match'] is None or state['text'] != left.toPlainText():
            run_preview()
            if state['match'] is None:
                return
        apply_match(page, state['match'])
        if callable(on_done):
            on_done()

    # ── 直接生成：现听写字级时间，再建新工程 ──────────────────────────────
    def run_generate():
        project_current = getattr(page, 'project', None)
        media_path = str(getattr(getattr(project_current, 'media', None), 'path', '') or '')
        if not media_path:
            summary.setText(tr('请先在达芬奇里选择素材'))
            return
        lines = parse_script(left.toPlainText())
        if not lines:
            summary.setText(tr('文稿是空的：每行一条字幕'))
            return
        from .home_script_match import ScriptMatchJob
        job = ScriptMatchJob(media_path, lines, root)
        state['job'] = job
        apply.setEnabled(False)
        preview.setEnabled(False)
        load.setEnabled(False)
        mode_box.setEnabled(False)
        summary.setText(tr('正在听写字级时间…'))

        def on_progress(text):
            summary.setText(str(text))

        def on_done_generate(path, match):
            state['job'] = None
            apply.setEnabled(True)
            preview.setEnabled(True)
            load.setEnabled(True)
            mode_box.setEnabled(True)
            table.setRowCount(len(match.lines))
            for row, line in enumerate(match.lines):
                values = (_format_ms(line.start_ms), line.text, line_status(line))
                for column, value in enumerate(values):
                    table.setItem(row, column, QTableWidgetItem(value))
            summary.setText(tr('已生成新工程：{name}（{count} 句）',
                               name=Path(str(path)).name, count=len(match.lines)))
            opener = getattr(page, 'open_studio_project', None)
            if callable(opener):
                opener(str(path), mode='edit', source='script_match')

        def on_failed(reason, detail=''):
            state['job'] = None
            apply.setEnabled(True)
            preview.setEnabled(True)
            load.setEnabled(True)
            mode_box.setEnabled(True)
            summary.setText(tr('生成没有完成：{reason}', reason=reason))

        job.progressed.connect(on_progress)
        job.succeeded.connect(on_done_generate)
        job.failed.connect(on_failed)
        job.start()

    def run_primary():
        """主按钮：替换模式 → 替换字幕；生成模式 → 现听写并生成新工程。"""
        if str(mode_box.currentData() or 'replace') == 'create':
            run_generate()
        else:
            accept()

    def mode_changed():
        creating = str(mode_box.currentData() or 'replace') == 'create'
        bind_text(apply, '直接生成' if creating else '替换全部字幕')
        bind_text(preview, '试听对齐（不写入）' if creating else '匹配预览')
        preview.setVisible(not creating)
        apply.setEnabled(True if creating else (state['match'] is not None))

    def refresh_project():
        """工程切换后清掉旧预览，避免用另一个工程的匹配结果去替换字幕。"""
        state['match'] = None
        state['text'] = None
        table.setRowCount(0)
        apply.setEnabled(False)
        summary.setText(tr('贴上文稿后点「匹配预览」。'))

    left.textChanged.connect(lambda: apply.setEnabled(False) if state['text'] != left.toPlainText() and str(mode_box.currentData()) != 'create' else None)
    load.clicked.connect(load_file)
    preview.clicked.connect(run_preview)
    apply.clicked.connect(run_primary)
    mode_box.currentIndexChanged.connect(lambda _i: mode_changed())
    mode_changed()
    api = dict(run_preview=run_preview, accept=run_primary, refresh_project=refresh_project,
               input=left, table=table, summary=summary, apply=apply,
               mode=mode_box, generate=run_generate)
    return root, api


def open_script_match_dialog(page) -> bool:
    from PySide6.QtWidgets import QDialog, QVBoxLayout

    project = getattr(page, 'project', None)
    if project is None:
        return False
    dialog = QDialog(page.window() or page)
    dialog.setObjectName('scriptMatchDialog')
    dialog.setWindowTitle(tr('匹配文稿'))
    dialog.resize(940, 660)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(0)
    root, api = build_script_match_widget(page, dialog, on_done=dialog.accept)
    layout.addWidget(root, 1)
    dialog._run_preview = api['run_preview']  # automated checks drive the real buttons' handlers
    dialog._accept_match = api['accept']
    page._script_match_dialog = dialog
    try:
        return dialog.exec() == QDialog.DialogCode.Accepted
    finally:
        page._script_match_dialog = None


def open_simple_script_sheet(page) -> bool:
    """左侧「文稿匹配」按钮：只输入文稿 + 一个生成按钮，自动决定替换还是生成。

    2026-10-18（用户："点击出现一个窗口进行输入文稿 然后点击生成就好了 自动确认
    如有字幕就自动进行替换 如没有就进行生成"）。判断规则：
      · 工程里已有字幕（且有字级时间）→ 用 match_project + apply_match 直接替换
      · 没有字幕（或没有字级时间）→ 用 ScriptMatchJob 现听写并生成
    全程自动确认，不再让用户选方式或点预览。
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                                   QProgressBar, QPushButton, QVBoxLayout)
    from .design.presentation import button_role
    from .i18n_widgets import bind_text

    project = getattr(page, 'project', None)
    if project is None:
        return False

    dialog = QDialog(page.window() or page)
    dialog.setObjectName('simpleScriptMatchDialog')
    dialog.setWindowTitle(tr('文稿匹配'))
    dialog.resize(680, 560)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(18, 16, 18, 14)
    layout.setSpacing(10)

    intro = QLabel(tr('粘贴已断好句的完整文稿，每行一条字幕。点「生成」即可：'
                      '有字幕会按已有字级时间替换，没有字幕会自动听写后生成。'))
    intro.setWordWrap(True)
    layout.addWidget(intro)

    editor = QPlainTextEdit()
    editor.setObjectName('simpleScriptInput')
    editor.setPlaceholderText(tr('每行一条字幕，例如：\n大家好，欢迎回来\n今天我们继续打洛克王国'))
    layout.addWidget(editor, 1)

    status = QLabel('')
    status.setObjectName('simpleScriptStatus')
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
    run = button_role(QPushButton(tr('生成')), 'primary')
    actions.addWidget(load)
    actions.addStretch(1)
    actions.addWidget(run)
    layout.addLayout(actions)

    state = {'job': None}

    def load_file():
        path, _ = QFileDialog.getOpenFileName(dialog, tr('选择文稿'), '', tr('文本文件 (*.txt);;所有文件 (*)'))
        if path:
            try:
                editor.setPlainText(read_script_file(path))
            except (OSError, ValueError) as exc:
                status.setText(str(exc))

    def has_project_captions() -> bool:
        """工程里是否已有可用的字级时间（决定替换还是生成）。"""
        current = getattr(page, 'project', None)
        if current is None or not getattr(current, 'cues', None):
            return False
        try:
            return bool(tokens_from_project(current))
        except Exception:  # noqa: BLE001
            return False

    def set_busy(busy: bool) -> None:
        for widget in (editor, load, run):
            widget.setEnabled(not busy)
        bar.setVisible(busy)

    def do_replace():
        current = getattr(page, 'project', None)
        try:
            _lines, match = match_project(current, editor.toPlainText())
        except ScriptMatchError as exc:
            set_busy(False)
            status.setText(str(exc))
            return
        apply_match(page, match)
        set_busy(False)
        status.setText(tr('已替换 {count} 条字幕（Ctrl+Z 可撤销）。', count=len(match.lines)))
        dialog.accept()

    def do_create():
        current = getattr(page, 'project', None)
        media_path = str(getattr(getattr(current, 'media', None), 'path', '') or '')
        if not media_path:
            set_busy(False)
            status.setText(tr('请先在达芬奇里选择素材'))
            return
        lines = parse_script(editor.toPlainText())
        if not lines:
            set_busy(False)
            status.setText(tr('文稿是空的：每行一条字幕'))
            return
        from .home_script_match import ScriptMatchJob
        job = ScriptMatchJob(media_path, lines, dialog)
        state['job'] = job
        job.progressed.connect(lambda text: status.setText(str(text)))

        def ok(path, match):
            state['job'] = None
            set_busy(False)
            status.setText(tr('已生成工程（{count} 句），正在打开…', count=len(match.lines)))
            opener = getattr(page, 'open_studio_project', None)
            if callable(opener):
                opener(str(path), mode='edit', source='script_match')
            dialog.accept()

        def bad(reason, detail=''):
            state['job'] = None
            set_busy(False)
            status.setText(tr('生成没有完成：{reason}', reason=reason))

        job.succeeded.connect(ok)
        job.failed.connect(bad)
        job.start()

    def generate():
        if not parse_script(editor.toPlainText()):
            status.setText(tr('文稿是空的：每行一条字幕'))
            return
        set_busy(True)
        status.setText(tr('正在处理…'))
        if has_project_captions():
            status.setText(tr('检测到已有字幕：按已有字级时间替换…'))
            do_replace()
        else:
            status.setText(tr('没有可用字幕：正在听写生成…'))
            do_create()

    load.clicked.connect(load_file)
    run.clicked.connect(generate)
    dialog._generate = generate  # automated checks drive the real handler
    page._script_match_dialog = dialog
    try:
        return dialog.exec() == QDialog.DialogCode.Accepted
    finally:
        page._script_match_dialog = None
        job = state['job']
        if job is not None:
            job.wait()


__all__ = ['MatchScriptCommand', 'apply_match', 'build_replacement', 'match_project', 'open_script_match_dialog',
           'read_script_file']
