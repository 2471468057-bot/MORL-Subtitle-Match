"""Standalone startup splash: shown while the Studio builds, then fades out.

The main window takes several seconds to build its widget tree. Rather than
leaving the desktop blank, this small frameless card appears immediately,
animates while the editor loads, and dissolves as the real window fades in.
"""

from __future__ import annotations

import time

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class StartupSplash(QWidget):
    """Frameless always-on-top card with an indeterminate progress sweep."""

    finished = Signal()

    WIDTH = 420
    HEIGHT = 236
    CORNER = 18.0

    def __init__(self, project_name: str = ""):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        self._project = str(project_name or "")
        self._progress = 0.0
        self._status = "正在准备工作台…"
        self._closing = False

        # Indeterminate sweep: a highlight travels along the track.
        self._sweep = QVariantAnimation(self)
        self._sweep.setStartValue(0.0)
        self._sweep.setEndValue(1.0)
        self._sweep.setDuration(1250)
        self._sweep.setLoopCount(-1)
        self._sweep.valueChanged.connect(self._on_sweep)
        self._sweep.start()

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(320)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._after_fade)

        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._tick_dots)
        self._spin_timer.start(380)
        self._dots = 0

    # ------------------------------------------------------------ placement

    def center_on_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(
            area.center().x() - self.WIDTH // 2,
            area.center().y() - self.HEIGHT // 2 - 24,
        )

    # ------------------------------------------------------------ state

    def set_project(self, name: str) -> None:
        self._project = str(name or "")
        self.update()

    def set_status(self, text: str, progress: float | None = None) -> None:
        self._status = str(text or "")
        if progress is not None:
            self._progress = max(0.0, min(1.0, float(progress)))
        self.update()

    def _tick_dots(self) -> None:
        self._dots = (self._dots + 1) % 4
        self.update()

    def _on_sweep(self, value) -> None:
        self._sweep_value = float(value)
        self.update()

    # ------------------------------------------------------------ close

    def close_with_fade(self, delay_ms: int = 0) -> None:
        """Fade out (optionally after a delay) and disappear."""
        if self._closing:
            return
        self._closing = True
        if delay_ms > 0:
            QTimer.singleShot(delay_ms, self._start_fade)
        else:
            self._start_fade()

    def _start_fade(self) -> None:
        self._spin_timer.stop()
        self._sweep.stop()
        self._fade.setStartValue(float(self.windowOpacity()))
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _after_fade(self) -> None:
        if self._fade.endValue() == 0.0:
            self.finished.emit()
            self.hide()
            self.deleteLater()

    # ------------------------------------------------------------ paint

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        card = QRectF(0.5, 0.5, self.WIDTH - 1.0, self.HEIGHT - 1.0)
        path = QPainterPath()
        path.addRoundedRect(card, self.CORNER, self.CORNER)

        # Card body: a touch lighter than pure black so the shadow reads.
        painter.fillPath(path, QColor(23, 23, 28, 252))
        painter.setPen(QPen(QColor(255, 255, 255, 16), 1.0))
        painter.drawPath(path)

        # Logo tile.
        logo = QRectF(26.0, 26.0, 40.0, 40.0)
        grad = QLinearGradient(logo.topLeft(), logo.bottomRight())
        grad.setColorAt(0.0, QColor(226, 85, 127))
        grad.setColorAt(1.0, QColor(155, 77, 255))
        logo_path = QPainterPath()
        logo_path.addRoundedRect(logo, 11.0, 11.0)
        painter.fillPath(logo_path, grad)
        painter.setPen(QColor(255, 255, 255))
        font = QFont()
        font.setPixelSize(17)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(logo, Qt.AlignmentFlag.AlignCenter, "兔")

        # Titles.
        painter.setPen(QColor(240, 240, 246))
        title_font = QFont()
        title_font.setPixelSize(15)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(78.0, 26.0, self.WIDTH - 104.0, 20.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "兔白字幕",
        )

        painter.setPen(QColor(140, 140, 154))
        sub_font = QFont()
        sub_font.setPixelSize(11)
        painter.setFont(sub_font)
        project_text = self._project or "字幕工作台"
        painter.drawText(
            QRectF(78.0, 46.0, self.WIDTH - 104.0, 18.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            project_text,
        )

        # Progress track.
        track = QRectF(28.0, 104.0, self.WIDTH - 56.0, 5.0)
        track_path = QPainterPath()
        track_path.addRoundedRect(track, 2.5, 2.5)
        painter.fillPath(track_path, QColor(255, 255, 255, 20))

        # Sweep highlight.
        sweep = getattr(self, "_sweep_value", 0.0)
        band = 0.34
        start = sweep * (1.0 + band) - band
        visible = QRectF(
            track.left() + max(0.0, start) * track.width(),
            track.top(),
            min(track.width(), band * track.width()),
            track.height(),
        )
        if visible.width() > 0:
            fill_path = QPainterPath()
            fill_path.addRoundedRect(visible, 2.5, 2.5)
            fill_grad = QLinearGradient(visible.topLeft(), visible.topRight())
            fill_grad.setColorAt(0.0, QColor(226, 85, 127, 90))
            fill_grad.setColorAt(1.0, QColor(255, 111, 156, 255))
            painter.fillPath(fill_path, fill_grad)

        # Status line with animated dots.
        dots = "." * self._dots
        painter.setPen(QColor(150, 150, 164))
        status_font = QFont()
        status_font.setPixelSize(11)
        painter.setFont(status_font)
        painter.drawText(
            QRectF(28.0, 124.0, self.WIDTH - 56.0, 18.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{self._status}{dots}",
        )

        # Quiet footnote.
        painter.setPen(QColor(96, 96, 110))
        foot_font = QFont()
        foot_font.setPixelSize(10)
        painter.setFont(foot_font)
        painter.drawText(
            QRectF(28.0, self.HEIGHT - 40.0, self.WIDTH - 56.0, 18.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "调取素材与时间轴",
        )
