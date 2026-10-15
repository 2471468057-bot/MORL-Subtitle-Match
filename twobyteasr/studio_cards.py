"""Small studio card/editor widgets shared by the AI panel, review flow,
and canvas inline editing."""

from __future__ import annotations

import difflib
import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
)

from .studio_qc import QCCandidate

class AIDesignVariantCard(QFrame):
    """Clickable AI design card: clicking anywhere on the card selects it."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiDesignVariant")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ReviewCandidateCard(QFrame):
    """Distinct selectable card for a review candidate.

    Shows:
    - Large keyboard number badge
    - Source badges (secondary)
    - Full readable candidate text
    - Click to adopt
    Visual states: hover ring, selected green border.

    2026-10-15: card 1 (the current caption) may carry click-to-fix marks
    (``subtitle_rules.review_suggestions``): a click on a mark changes only
    that part (``suggestion_activated``), right-click or a mark with several
    options asks (``suggestion_menu_requested``); a click elsewhere still
    adopts the whole card.
    """
    clicked = Signal(int)
    suggestion_activated = Signal(int, int)  # mark index, option index
    suggestion_menu_requested = Signal(int, object)  # mark index, global QPoint

    def __init__(
        self,
        index: int,
        candidate: "QCCandidate",
        is_current: bool = False,
        current_text: str = "",
        parent=None,
        suggestions=(),
    ):
        super().__init__(parent)
        self._index = index
        self._candidate = candidate
        self._current_text = current_text
        self._is_current = is_current
        self._selected = bool(is_current)
        self._suggestions = tuple(suggestions or ())
        self._pressed_mark = -1
        self._hover_mark = -2
        self._mirror = None
        self.setObjectName("reviewCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(86)
        self.setMaximumHeight(124)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 9)
        lay.setSpacing(9)

        # Number badge
        num = QLabel(str(index + 1))
        num.setObjectName("reviewCardNum")
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setFixedSize(30, 30)
        lay.addWidget(num, 0, Qt.AlignmentFlag.AlignTop)

        # Body
        body = QVBoxLayout()
        body.setSpacing(5)

        # Source row (badges)
        src_row = QHBoxLayout()
        src_row.setSpacing(4)
        for src in (candidate.sources or ("?",)):
            label = "当前" if str(src) == "Current" else str(src)
            badge = QLabel(label)
            badge.setObjectName("reviewSourceBadge")
            badge.setProperty("current", label == "当前")
            src_row.addWidget(badge, 0)
        if candidate.context_only:
            context = QLabel("原始段上下文 · 仅供参考")
            context.setObjectName("reviewSourceContext")
            src_row.addWidget(context, 0)
            self.setEnabled(False)
            self.setToolTip("包含未能精确对齐本条的原始段落，请结合原音编辑。")
        src_row.addStretch(1)
        body.addLayout(src_row)

        # Text (readable size, not crushed)
        self.text_label = QLabel(self._markup())
        self.text_label.setTextFormat(Qt.TextFormat.RichText)
        self.text_label.setWordWrap(True)
        self.text_label.setMinimumHeight(34)
        self.text_label.setMaximumHeight(62)
        self.text_label.setObjectName("reviewCandidateText")
        if self._suggestions:
            # The card hit-tests the marks itself (``_mark_at``); the label only paints.
            self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setMouseTracking(True)
        body.addWidget(self.text_label)

        lay.addLayout(body, 1)

        # Click anywhere adopts
        self.set_selected(self._selected)

    @staticmethod
    def _diff_markup(candidate: str, current: str) -> str:
        if not current or candidate == current:
            return html.escape(candidate).replace("\n", "<br>")
        from .theme_manager import theme_key
        from .ui_theme import theme_definition
        theme = theme_definition(theme_key())
        chunks: list[str] = []
        matcher = difflib.SequenceMatcher(None, current, candidate, autojunk=False)
        for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
            text = html.escape(candidate[j1:j2]).replace("\n", "<br>")
            if tag == "equal":
                chunks.append(text)
            elif text:
                chunks.append(f"<span style='background:{theme.warning_soft}; color:{theme.warning}; border-radius:3px; padding:1px 2px;'>{text}</span>")
        return "".join(chunks)

    def _markup(self) -> str:
        if self._suggestions:
            return self._suggestion_markup(self._current_text or self._candidate.text or "", self._suggestions)
        return self._diff_markup(self._candidate.text or "", self._current_text)

    @staticmethod
    def _suggestion_markup(text: str, suggestions) -> str:
        """The current caption with each mark as an anchor ``m:<index>``: the
        original on the same highlight as the other cards' differences plus
        the suggestion as a solid accent chip; 他/她/它 underlined.

        (Real-window check 2026-10-15: a strike-out inside the anchor was not
        painted and an accent_soft fill vanished on the selected card.)"""
        from .theme_manager import theme_key
        from .ui_theme import theme_definition
        theme = theme_definition(theme_key())
        escape = lambda value: html.escape(value).replace("\n", "<br>")
        chunks, cursor = [], 0
        for index, row in enumerate(suggestions):
            if row.start < cursor or row.end > len(text):
                continue
            chunks.append(escape(text[cursor:row.start]))
            if row.kind == "pronoun":
                inner = (f"<span style='color:{theme.accent}; text-decoration:underline;'>"
                         f"{escape(row.original)}</span>")
            else:
                options = [option.text for option in row.options]
                shown = " / ".join(escape(value) or "∅" for value in options[:2]) + ("…" if len(options) > 2 else "")
                old = (f"<span style='background:{theme.warning_soft}; color:{theme.warning};'>{escape(row.original)}</span>"
                       if row.original else "")
                inner = (old + f"<span style='background:{theme.accent}; color:{theme.text_on_accent}; "
                         f"font-weight:600;'>&nbsp;→{shown}&nbsp;</span>")
            chunks.append(f"<a href='m:{index}' style='text-decoration:none; color:{theme.text};'>{inner}</a>")
            cursor = row.end
        chunks.append(escape(text[cursor:]))
        return "".join(chunks)

    # click-to-fix marks ------------------------------------------------------
    def _mark_at(self, pos) -> int:
        """Index of the mark under ``pos`` (card coordinates), or -1.

        A text document laid out like QLabel lays out rich text (no margin,
        the label's font, wrap width and alignment) answers ``anchorAt``."""
        if not self._suggestions:
            return -1
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QTextDocument, QTextOption
        label = self.text_label
        local = label.mapFrom(self, pos)
        rect = label.contentsRect()
        key = (label.text(), rect.width(), label.font().key())
        if self._mirror is None or self._mirror[0] != key:
            document = QTextDocument()
            document.setDefaultFont(label.font())
            option = QTextOption(Qt.AlignmentFlag.AlignLeft)
            option.setWrapMode(QTextOption.WrapMode.WordWrap)
            document.setDefaultTextOption(option)
            document.setHtml(label.text())
            frame = document.rootFrame().frameFormat()
            frame.setMargin(0)
            document.rootFrame().setFrameFormat(frame)
            document.setTextWidth(rect.width())
            self._mirror = (key, document)
        document = self._mirror[1]
        y = local.y() - rect.top()
        align = label.alignment()
        spare = rect.height() - document.size().height()
        if spare > 0 and align & Qt.AlignmentFlag.AlignVCenter:
            y -= spare / 2
        elif spare > 0 and align & Qt.AlignmentFlag.AlignBottom:
            y -= spare
        anchor = document.documentLayout().anchorAt(QPointF(local.x() - rect.left(), y))
        if not anchor.startswith("m:"):
            return -1
        try:
            index = int(anchor[2:])
        except ValueError:
            return -1
        return index if 0 <= index < len(self._suggestions) else -1

    def _mark_tip(self, index: int) -> str:
        from .i18n import tr
        row = self._suggestions[index]
        if row.kind == "pronoun":
            return tr("点一下：{old} → {new}；右键选择 他 / 她 / 它；按 P 切换整条的人称",
                      old=row.original, new=row.options[0].text)
        sources = " · ".join(dict.fromkeys(source for option in row.options for source in option.sources))
        label = tr("词库规范写法") if row.kind == "glossary" else (sources or tr("其他识别结果"))
        if len(row.options) > 1:
            return tr("{source}：这里有 {count} 种写法，点一下选择（可撤销）", source=label, count=len(row.options))
        return tr("{source}：「{old}」→「{new}」，点一下只改这一处（可撤销）",
                  source=label, old=row.original or "∅", new=row.options[0].text or "∅")

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._suggestions:
            index = self._mark_at(event.position().toPoint())
            if index != self._hover_mark:
                self._hover_mark = index
                self.setToolTip(self._mark_tip(index) if index >= 0 else "")
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            index = self._mark_at(event.position().toPoint())
            if index >= 0:
                # A mark acts on release, so a press never also adopts the card.
                self._pressed_mark = index
                event.accept()
                return
            self.clicked.emit(self._index)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        pressed, self._pressed_mark = self._pressed_mark, -1
        if pressed >= 0 and event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            if self._mark_at(event.position().toPoint()) != pressed:
                return
            if self._suggestions[pressed].kind != "pronoun" and len(self._suggestions[pressed].options) > 1:
                self.suggestion_menu_requested.emit(pressed, event.globalPosition().toPoint())
            else:
                self.suggestion_activated.emit(pressed, 0)
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        index = self._mark_at(event.pos())
        if index >= 0:
            self.suggestion_menu_requested.emit(index, event.globalPos())
            event.accept()
            return
        super().contextMenuEvent(event)

    def set_selected(self, on: bool):
        self._selected = bool(on)
        self.setProperty("selected", bool(on))
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def refresh_theme_palette(self):
        self._mirror = None
        self.text_label.setText(self._markup())



class _SubtitleEditCardEditor(QPlainTextEdit):
    """IME-safe editor hosted in the Qt layout, never over mpv's HWND."""

    commit_requested = Signal(bool)
    cancel_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
                return
            self.commit_requested.emit(bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _CanvasInlineEdit(QPlainTextEdit):
    """Visible Studio canvas editor with explicit IME diagnostics."""

    input_method_received = Signal(str, str, str)
    diagnostic = Signal(str, object)

    def inputMethodEvent(self, event) -> None:
        preedit = str(event.preeditString())
        commit = str(event.commitString())
        super().inputMethodEvent(event)
        self.input_method_received.emit(preedit, commit, self.toPlainText())
