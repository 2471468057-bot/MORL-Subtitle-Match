"""Small home-page widgets (2026-10-08 home redesign)."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
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
        self._relayout()

    CHIP = 32

    def sizeHint(self):
        return QSize(320, self.CHIP + 2)

    def minimumSizeHint(self):
        return QSize(0, self.CHIP + 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        height = self.height() or self.CHIP + 2
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
            chip.setGeometry(x, (height - self.CHIP) // 2, size.width(), self.CHIP)
            chip.show()
            x += size.width() + self.GAP
