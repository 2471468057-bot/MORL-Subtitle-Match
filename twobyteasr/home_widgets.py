"""Small home-page widgets (2026-10-08 home redesign)."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget

from .i18n import bind_text
from .i18n_widgets import user_text


class QuickPickRow(QWidget):
    """Recent content names as one-click chips on a single line.

    Chips that do not fit the current width are hidden instead of wrapping,
    so the content card keeps a stable height at every window size.
    """

    picked = Signal(str)
    GAP = 6

    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self.caption = QLabel(caption, self)
        self.caption.setObjectName("homeQuickCaption")
        self.chips: list[QPushButton] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_items(self, names, current: str = "") -> None:
        names = [str(name) for name in names if str(name).strip()]
        if names != [chip.property("contentName") for chip in self.chips]:
            for chip in self.chips:
                chip.deleteLater()
            self.chips = []
            for name in names:
                chip = QPushButton(self)
                chip.setObjectName("contentQuickChip")
                chip.setCheckable(True)
                chip.setCursor(Qt.CursorShape.PointingHandCursor)
                chip.setProperty("contentName", name)
                # Names are user data laid out here; skip the i18n width guard.
                chip.setProperty("flexibleWidth", True)
                text = name if len(name) <= 12 else name[:11] + "…"
                user_text(chip).setText(text)
                bind_text(chip, '设为本批内容', property='toolTip')
                chip.clicked.connect(lambda _=False, value=name: self.picked.emit(value))
                self.chips.append(chip)
        for chip in self.chips:
            chip.blockSignals(True)
            chip.setChecked(chip.property("contentName") == current)
            chip.blockSignals(False)
        self.setVisible(bool(self.chips))
        self.updateGeometry()
        self._relayout()

    CHIP = 32

    def _chip_height(self) -> int:
        # The chip's own height (its style sheet min/max-height, scaled by the
        # interface zoom), not a constant: a fixed 32 px row cut the bottom
        # border off 37 px chips at 110% zoom (2026-10-14 user screenshot).
        heights = [chip.sizeHint().expandedTo(chip.minimumSize()).height() for chip in self.chips]
        if not heights:
            from .ui_zoom import px
            return px(self.CHIP)
        return max(heights)

    def sizeHint(self):
        return QSize(320, self._chip_height() + 4)

    def minimumSizeHint(self):
        return QSize(0, self._chip_height() + 4)

    def event(self, event):
        if event.type() in (QEvent.Type.StyleChange, QEvent.Type.FontChange, QEvent.Type.LayoutRequest):
            self.updateGeometry()
            self._relayout()
        return super().event(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        chip_height = self._chip_height()
        if self.height() and self.height() < chip_height + 4:
            self.updateGeometry()  # the parent layout gives the taller row next pass
        height = self.height() or chip_height + 4
        chip_height = min(chip_height, height)
        caption = self.caption.sizeHint()
        self.caption.setGeometry(0, (height - caption.height()) // 2, caption.width(), caption.height())
        x = caption.width() + 10
        full = False
        for chip in self.chips:
            size = chip.sizeHint().expandedTo(chip.minimumSize())
            full = full or x + size.width() > self.width()
            if full:
                chip.hide()
                continue
            chip.setGeometry(x, (height - chip_height) // 2, size.width(), chip_height)
            chip.show()
            x += size.width() + self.GAP
