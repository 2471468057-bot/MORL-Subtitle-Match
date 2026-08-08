"""PySide6 desktop shell for the 2ByteASR settings, progress, and result flow."""

from __future__ import annotations

import os
import sys
import time
import html
import threading
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import qtawesome as qta
import requests
from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSettings,
    QSize,
    QStandardPaths,
    Qt,
    QThread,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QTextOption
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from twobyteasr.i18n import apply_ui_language, current_language, save_language, translate
from twobyteasr.llm_config import PROVIDER_PRESETS, endpoint_from_settings, normalize_base_url, resolve_api_key, validate_endpoint
from twobyteasr.service import CancellationToken, RunOptions, run_media_queue


IVORY = "#f8f5ee"
PARCHMENT = "#f2ebdc"
SURFACE = "#fffdf8"
INK = "#343532"
MUTED = "#6f716b"
LINE = "#d8cdbc"
CHARCOAL = "#3c3d3a"
GREEN = "#4b7f4d"
AMBER = "#c58a32"
BLUE = "#397da0"
CORAL = "#d56d54"
PURPLE = "#9b65a0"
MINT = "#dcebd9"
APP_ROOT = Path(__file__).resolve().parents[1]
APP_ICON_SOURCE_PATH = APP_ROOT / "assets" / "2byteasr-icon-transparent.png"
APP_ICON_FALLBACK_PATH = APP_ROOT / "assets" / "2byteasr-icon.jpg"
APP_ICON_PATH = APP_ROOT / "assets" / "2byteasr.ico"
LAST_MEDIA_DIRECTORY_KEY = "paths/last_media_directory"
SUPPORTED_MEDIA_SUFFIXES = frozenset(
    {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".flac", ".aac"}
)


def _icon(name: str, color: str = INK) -> QIcon:
    return qta.icon(name, color=color)


def _app_icon() -> QIcon:
    if APP_ICON_PATH.is_file():
        return QIcon(str(APP_ICON_PATH))
    if APP_ICON_SOURCE_PATH.is_file():
        return QIcon(str(APP_ICON_SOURCE_PATH))
    if APP_ICON_FALLBACK_PATH.is_file():
        return QIcon(str(APP_ICON_FALLBACK_PATH))
    return _icon("fa5s.closed-captioning", GREEN)


def _completion_notification_spec(result):
    """Build a concise, user-visible completion message for every queue outcome."""
    success_count = len(result.successes)
    failure_count = len(result.failures)
    cancel_count = len(result.cancelled)
    skipped_count = len(result.skipped)
    if failure_count:
        title = "字幕生成部分失败" if success_count else "字幕生成失败"
        icon = (
            QMessageBox.Icon.Warning
            if success_count
            else QMessageBox.Icon.Critical
        )
        message = (
            f"本批任务已结束：成功 {success_count} 个，失败 {failure_count} 个。"
            "请查看结果页中的失败原因。"
        )
        details = "\n".join(
            f"{Path(item.media_path).name}：{item.error or '未提供错误详情'}"
            for item in result.failures[:3]
        )
    elif cancel_count:
        title = "字幕任务已取消"
        icon = QMessageBox.Icon.Warning
        message = (
            f"任务已安全停止：成功 {success_count} 个，取消 {cancel_count} 个。"
        )
        details = "已完成的字幕会保留，尚未开始或未完成的素材不会写入成片。"
    else:
        title = "字幕生成完成"
        icon = QMessageBox.Icon.Information
        message = (
            f"已成功生成 {success_count} 个素材的字幕。"
            if success_count
            else f"任务已完成，跳过 {skipped_count} 个已有结果。"
        )
        details = "可以在结果页查看字幕、分轨和任务报告路径。"
    return title, message, icon, details


def _configure_windows_app_identity() -> None:
    """Give the Qt window its own taskbar identity instead of Python's icon."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "2ByteASR.Desktop.2026"
        )
    except (AttributeError, OSError):
        pass


APP_QSS = f"""
QWidget {{
    color: {INK};
    font-family: "Microsoft YaHei UI", "Segoe UI", "Yu Gothic UI", "PingFang SC";
    font-size: 13px;
}}
QMainWindow, QWidget#appRoot {{ background: {IVORY}; }}
QFrame#workflow, QFrame#accordion, QFrame#mediaRow {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 12px;
}}
QFrame#settingsSurface {{
    background: {PARCHMENT};
    border: 1px solid #d6c5aa;
    border-radius: 12px;
}}
QFrame#mediaRow[dropActive="true"] {{
    background: #eef6ea;
    border: 2px dashed {GREEN};
}}
QFrame#mediaRow[empty="true"] {{
    background: #fffaf1;
    border: 2px dashed #c7ad84;
}}
QFrame#dropOverlay {{
    background: rgba(248, 245, 238, 238);
    border: 3px dashed {GREEN};
    border-radius: 24px;
}}
QLabel#dropOverlayTitle {{
    color: {INK}; font-size: 26px; font-weight: 800;
}}
QLabel#dropOverlayHint {{
    color: {MUTED}; font-size: 13px;
}}
QLabel#dropHint {{ color: {MUTED}; font-size: 12px; }}
QFrame#endpointCard {{
    background: rgba(255, 253, 248, 0.82);
    border: 1px solid {LINE};
    border-radius: 10px;
}}
QFrame#progressHero {{
    background: #f0e7d8;
    border: 1px solid #d6c5aa;
    border-radius: 14px;
}}
QFrame#phaseCard, QFrame#currentStageCard, QFrame#eventFeedCard, QFrame#consoleCard,
QFrame#resultSummaryCard, QFrame#resultFilesCard, QFrame#resultLogCard {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 12px;
}}
QLabel#progressPercent {{
    background: {CHARCOAL}; color: white; border-radius: 15px;
    font-size: 16px; font-weight: 800; padding: 6px 12px;
}}
QLabel#stageEyebrow {{ color: {AMBER}; font-size: 12px; font-weight: 800; }}
QLabel#stageLarge {{ font-size: 20px; font-weight: 800; }}
QLabel#consoleBadge {{
    background: #e9dfcf; color: #5b4a36; border-radius: 9px;
    padding: 4px 9px; font-size: 11px; font-weight: 700;
}}
QListWidget#eventFeed {{
    background: #fffaf1; border: 0; border-radius: 11px; padding: 5px;
    outline: 0;
}}
QListWidget#eventFeed::item {{
    border: 0; margin: 3px 1px; padding: 0;
}}
QTextEdit#consoleLog {{
    background: #30332f; color: #edf0e9; border: 0; border-radius: 9px;
    padding: 9px; font-family: "Cascadia Mono", "Microsoft YaHei UI"; font-size: 12px;
    selection-background-color: #6d8d67;
}}
QTextEdit#resultFiles {{
    background: #fffaf1; border: 0; border-radius: 9px; padding: 9px;
}}
QTextEdit#resultConsole {{
    background: #30332f; color: #edf0e9; border: 0; border-radius: 9px;
    padding: 9px; font-family: "Cascadia Mono", "Microsoft YaHei UI"; font-size: 12px;
}}
QLineEdit, QComboBox, QPlainTextEdit, QListWidget {{
    background: #ffffff;
    border: 1px solid #bdb8ae;
    border-radius: 8px;
    padding: 8px 10px;
    min-height: 20px;
    selection-background-color: {GREEN};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QListWidget:focus {{
    border: 1px solid {GREEN};
}}
QComboBox::drop-down {{ border: 0; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px;
    padding: 5px; selection-background-color: #e5eee2; selection-color: {INK};
}}
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #fffefa, stop:1 #f2ede4);
    border: 1px solid #beb8ad;
    border-radius: 8px;
    padding: 8px 16px;
    min-height: 18px;
}}
QPushButton:hover {{ background: #fffaf0; border-color: {AMBER}; }}
QPushButton:pressed {{ background: #e8e0d2; border-color: #9e7a45; }}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #618f5f, stop:1 #416f45);
    color: white; border: 1px solid #365f3a; border-radius: 9px;
    font-size: 15px; font-weight: 700; padding: 11px 28px;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6b9b68, stop:1 #497b4c);
    border-color: #294e2c;
}}
QPushButton#outline {{
    background: transparent;
    border: 1px solid {GREEN};
    color: {GREEN};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton#outline:hover {{ background: #eef6ea; border-color: #3a6d3e; }}
QPushButton#linkButton {{
    border: 0; background: transparent; color: {GREEN};
    font-weight: 600; padding: 6px 10px; border-radius: 6px;
}}
QPushButton#linkButton:hover {{ background: #eef6ea; color: #3a6d3e; }}
QPushButton:disabled {{ color: #99958d; background: #ece7de; border-color: #d2cbc0; }}
QPushButton#danger {{ color: #8a6524; }}
QPushButton#flat {{ border: 0; background: transparent; padding: 5px; }}
QPushButton#accordionButton {{
    border: 0; background: transparent; text-align: left; padding: 11px 14px;
    font-size: 14px; font-weight: 600;
}}
QPushButton#accordionButton:hover {{ background: rgba(196, 171, 131, 0.12); }}
QLabel#brand {{ font-size: 26px; font-weight: 800; padding: 4px 7px; border-radius: 8px; }}
QLabel#brand:hover {{ background: #eee7d9; color: #365f3a; }}
QLabel#title {{ font-size: 18px; font-weight: 700; }}
QLabel#sectionTitle {{
    color: {INK};
    font-size: 15px; font-weight: 700;
    padding: 0 0 8px 0;
    border-left: 3px solid {AMBER};
    padding-left: 9px;
}}
QLabel#muted {{ color: {MUTED}; font-size: 12px; }}
QLabel#statusGood {{ color: {GREEN}; font-weight: 600; }}
QLabel#statusWarn {{ color: {AMBER}; font-weight: 600; }}
QProgressBar {{
    background: #e4dccf; border: 0; border-radius: 7px; height: 14px; text-align: center;
}}
QProgressBar::chunk {{ background: {GREEN}; border-radius: 7px; }}
QScrollArea, QWidget#qt_scrollarea_viewport, QWidget#settingsPage {{
    border: 0; background: {IVORY};
}}
QScrollBar:vertical {{
    background: #eee7dc; width: 10px; margin: 0; border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: #b9ad9d; min-height: 36px; border-radius: 5px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


class BrandLabel(QLabel):
    hover_entered = Signal()
    hover_left = Signal()

    def enterEvent(self, event):
        self.hover_entered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_left.emit()
        super().leaveEvent(event)


class SwitchControl(QAbstractButton):
    """Accessible animated switch that keeps QAbstractButton's checked API."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumHeight(34)
        self._hovered = False
        self._progress = 0.0
        self._animation = QVariantAnimation(self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._set_progress)
        self.toggled.connect(self._animate_to_state)
        self.setAccessibleName(text)

    def sizeHint(self):
        width = 62 + self.fontMetrics().horizontalAdvance(self.text())
        return QSize(max(155, width), 36)

    def _set_progress(self, value):
        self._progress = float(value)
        self.update()

    def _animate_to_state(self, checked: bool):
        target = 1.0 if checked else 0.0
        if not self.isVisible():
            self._set_progress(target)
            return
        self._animation.stop()
        self._animation.setStartValue(self._progress)
        self._animation.setEndValue(target)
        self._animation.start()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#fff9ef"))
            painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 8, 8)

        track = QRectF(2, (self.height() - 24) / 2, 44, 24)
        if self.isChecked():
            fill, edge, thumb = QColor("#dcebdc"), QColor(GREEN), QColor(GREEN)
        else:
            fill, edge, thumb = QColor("#eee9df"), QColor("#aaa69d"), QColor("#7f7c75")
        if not self.isEnabled():
            fill, edge, thumb = QColor("#efede8"), QColor("#d2cec6"), QColor("#bcb8b0")
        elif self._hovered:
            edge = QColor(AMBER)
        painter.setPen(QPen(edge, 1.4))
        painter.setBrush(fill)
        painter.drawRoundedRect(track, 12, 12)

        knob_x = 5 + self._progress * 20
        knob = QRectF(knob_x, track.y() + 3, 18, 18)
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.setBrush(thumb)
        painter.drawEllipse(knob)

        font = painter.font()
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(QColor(INK if self.isEnabled() else "#99958d"))
        painter.drawText(QRectF(58, 0, self.width() - 58, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            focus_pen = QPen(QColor(AMBER), 1)
            focus_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(focus_pen)
            painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 8, 8)


class EditableHistoryCombo(QComboBox):
    """Editable combo with an explicit, reliable history dropdown affordance."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(9)
        self.setMinimumHeight(42)
        self.lineEdit().setClearButtonEnabled(True)
        self._history_action = self.lineEdit().addAction(
            _icon("fa5s.chevron-down", "#5f625c"),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        self._history_action.setToolTip("展开历史记录与内置游戏")
        self._history_action.triggered.connect(self.showPopup)
        self.setStyleSheet("QComboBox::drop-down { width: 0px; border: 0; }")

    def setPlaceholderText(self, text: str):
        self.lineEdit().setPlaceholderText(text)


class AnimatedButton(QPushButton):
    """Native button with lightweight animated elevation feedback."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._motion_shadow = QGraphicsDropShadowEffect(self)
        self._motion_shadow.setBlurRadius(0)
        self._motion_shadow.setOffset(0, 0)
        self._motion_shadow.setColor(QColor(54, 50, 42, 0))
        self.setGraphicsEffect(self._motion_shadow)
        self._blur_motion = QPropertyAnimation(self._motion_shadow, b"blurRadius", self)
        self._offset_motion = QPropertyAnimation(self._motion_shadow, b"offset", self)
        self._color_motion = QPropertyAnimation(self._motion_shadow, b"color", self)
        for animation in (self._blur_motion, self._offset_motion, self._color_motion):
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _animate_elevation(self, blur: float, offset_y: float, alpha: int, duration: int):
        subtle = self.objectName() in {"flat", "accordionButton"}
        if subtle:
            blur = min(blur, 7)
            offset_y = min(offset_y, 1)
            alpha = min(alpha, 36)
        targets = (
            (self._blur_motion, self._motion_shadow.blurRadius(), blur),
            (self._offset_motion, self._motion_shadow.offset(), QPointF(0, offset_y)),
            (self._color_motion, self._motion_shadow.color(), QColor(54, 50, 42, alpha)),
        )
        for animation, start, end in targets:
            animation.stop()
            animation.setDuration(duration)
            animation.setStartValue(start)
            animation.setEndValue(end)
            animation.start()

    def enterEvent(self, event):
        if self.isEnabled():
            self._animate_elevation(17, 3, 78, 180)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_elevation(0, 0, 0, 160)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._animate_elevation(5, 0, 48, 75)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.isEnabled() and self.underMouse():
            self._animate_elevation(17, 3, 78, 150)
        else:
            self._animate_elevation(0, 0, 0, 130)


class CompletionDialog(QDialog):
    """Theme-stable completion card that does not inherit native dark dialogs."""

    _VISUALS = {
        QMessageBox.Icon.Information: (GREEN, "#edf5e9", "fa5s.check", "处理完成"),
        QMessageBox.Icon.Warning: (AMBER, "#fff5df", "fa5s.exclamation", "任务提醒"),
        QMessageBox.Icon.Critical: (CORAL, "#fff0eb", "fa5s.exclamation", "需要处理"),
    }

    def __init__(self, title: str, message: str, icon, details: str = "", parent=None):
        super().__init__(parent)
        self.accent, self.tint, icon_name, badge_text = self._VISUALS.get(
            icon,
            self._VISUALS[QMessageBox.Icon.Information],
        )
        self.setObjectName("completionDialog")
        self.setWindowTitle(f"2ByteASR｜{title}")
        self.setWindowIcon(_app_icon())
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumWidth(480)
        self.setMaximumWidth(580)
        self.setSizeGripEnabled(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("completionCard")
        self.card.setStyleSheet(
            f"QFrame#completionCard {{ background: {SURFACE}; border: 1px solid {LINE}; "
            "border-radius: 22px; }}"
        )
        outer.addWidget(self.card)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 20, 24, 22)
        card_layout.setSpacing(17)

        header = QHBoxLayout()
        header.setSpacing(9)
        brand_icon = QLabel()
        brand_icon.setFixedSize(30, 30)
        brand_icon.setPixmap(_app_icon().pixmap(QSize(30, 30)))
        brand_icon.setStyleSheet("border: 0; background: transparent;")
        header.addWidget(brand_icon)

        brand = QLabel("2ByteASR")
        brand.setStyleSheet(f"color: {INK}; font-size: 15px; font-weight: 800; border: 0;")
        header.addWidget(brand)
        header.addSpacing(4)

        self.status_badge = QLabel(badge_text)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet(
            f"color: {self.accent}; background: {self.tint}; border: 1px solid {self.accent}; "
            "border-radius: 11px; padding: 3px 10px; font-size: 11px; font-weight: 800;"
        )
        header.addWidget(self.status_badge)
        header.addStretch(1)

        close_button = AnimatedButton("×")
        close_button.setObjectName("flat")
        close_button.setAccessibleName("关闭提示")
        close_button.setToolTip("关闭")
        close_button.setFixedSize(32, 32)
        close_button.setStyleSheet(
            f"QPushButton {{ color: {MUTED}; background: transparent; border: 0; "
            "border-radius: 16px; font-size: 22px; font-weight: 500; padding: 0; }}"
            f"QPushButton:hover {{ color: {INK}; background: {PARCHMENT}; }}"
            "QPushButton:pressed { background: #e8dfd0; }"
        )
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button)
        card_layout.addLayout(header)

        body = QHBoxLayout()
        body.setContentsMargins(2, 0, 2, 0)
        body.setSpacing(18)
        icon_well = QLabel()
        icon_well.setFixedSize(72, 72)
        icon_well.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_well.setPixmap(_icon(icon_name, self.accent).pixmap(QSize(34, 34)))
        icon_well.setStyleSheet(
            f"background: {self.tint}; border: 2px solid {self.accent}; border-radius: 36px;"
        )
        body.addWidget(icon_well, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setSpacing(7)
        self.title_label = QLabel(title)
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            f"color: {INK}; font-size: 22px; font-weight: 900; border: 0; background: transparent;"
        )
        copy.addWidget(self.title_label)
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message_label.setStyleSheet(
            f"color: {MUTED}; font-size: 14px; border: 0; background: transparent;"
        )
        copy.addWidget(self.message_label)
        body.addLayout(copy, 1)
        card_layout.addLayout(body)

        self.details_label = QLabel(details)
        self.details_label.setWordWrap(True)
        self.details_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details_label.setVisible(bool(details))
        self.details_label.setStyleSheet(
            f"color: {INK}; background: {self.tint}; border: 1px solid {LINE}; border-radius: 12px; "
            "padding: 10px 12px; font-size: 12px;"
        )
        card_layout.addWidget(self.details_label)

        footer = QHBoxLayout()
        footer.setSpacing(12)
        hint = QLabel("任务结果已同步到工作台")
        hint.setStyleSheet(f"color: {MUTED}; font-size: 11px; border: 0; background: transparent;")
        footer.addWidget(hint)
        footer.addStretch(1)
        self.confirm_button = AnimatedButton("知道了")
        self.confirm_button.setDefault(True)
        self.confirm_button.setMinimumSize(112, 42)
        self.confirm_button.setStyleSheet(
            f"QPushButton {{ color: white; background: {self.accent}; border: 1px solid {self.accent}; "
            "border-radius: 12px; padding: 8px 22px; font-size: 14px; font-weight: 800; }}"
            "QPushButton:hover { background: #3f7042; border-color: #3f7042; }"
            "QPushButton:pressed { background: #355f38; border-color: #355f38; padding-top: 10px; }"
        )
        if self.accent != GREEN:
            hover = "#ad7629" if self.accent == AMBER else "#bb5d48"
            pressed = "#92601f" if self.accent == AMBER else "#9f4d3c"
            self.confirm_button.setStyleSheet(
                f"QPushButton {{ color: white; background: {self.accent}; border: 1px solid {self.accent}; "
                "border-radius: 12px; padding: 8px 22px; font-size: 14px; font-weight: 800; }}"
                f"QPushButton:hover {{ background: {hover}; border-color: {hover}; }}"
                f"QPushButton:pressed {{ background: {pressed}; border-color: {pressed}; padding-top: 10px; }}"
            )
        self.confirm_button.clicked.connect(self.accept)
        footer.addWidget(self.confirm_button)
        card_layout.addLayout(footer)

        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(190)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        apply_ui_language(self)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            geometry = self.frameGeometry()
            geometry.moveCenter(parent.window().frameGeometry().center())
            self.move(geometry.topLeft())
        self.setWindowOpacity(0.0)
        self._fade_in.stop()
        self._fade_in.start()
        self.confirm_button.setFocus(Qt.FocusReason.ActiveWindowFocusReason)


class SignalTextStream:
    """Tee text written by the pipeline to both the GUI and the original console."""

    def __init__(self, signal, level: str, fallback=None):
        self.signal = signal
        self.level = level
        self.fallback = fallback
        self._buffer = ""
        self._lock = threading.RLock()

    @property
    def encoding(self):
        return "utf-8"

    def isatty(self):
        return False

    def writable(self):
        return True

    def write(self, value):
        text = str(value or "")
        if not text:
            return 0
        with self._lock:
            if self.fallback is not None:
                try:
                    self.fallback.write(text)
                except Exception:
                    pass
            self._buffer += text.replace("\r\n", "\n").replace("\r", "\n")
            lines = self._buffer.split("\n")
            self._buffer = lines.pop()
            for line in lines:
                if line.strip():
                    self.signal.emit(line, self.level)
        return len(text)

    def flush(self):
        with self._lock:
            if self._buffer.strip():
                self.signal.emit(self._buffer, self.level)
            self._buffer = ""
            if self.fallback is not None:
                try:
                    self.fallback.flush()
                except Exception:
                    pass


class ProgressPhaseCard(QFrame):
    """Compact cartoon-like phase card with explicit pending/active/done states."""

    def __init__(self, icon_name: str, title: str, subtitle: str, accent: str):
        super().__init__()
        self.setObjectName("phaseCard")
        self.icon_name = icon_name
        self.accent = accent
        self.setMinimumHeight(84)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 11, 12, 11)
        layout.setSpacing(10)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(42, 42)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 800;")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("muted")
        self.state_label = QLabel("等待")
        self.state_label.setStyleSheet("font-size: 11px; font-weight: 700;")
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.subtitle_label)
        text_layout.addWidget(self.state_label)
        layout.addLayout(text_layout, 1)
        self._state = ""
        self._pulse = QVariantAnimation(self)
        self._pulse.setDuration(1800)
        self._pulse.setLoopCount(-1)
        self._pulse.setEasingCurve(QEasingCurve.Type.InOutSine)
        # Close the color loop at the same value so the active card eases back
        # instead of snapping from yellow to white at the loop boundary.
        self._pulse.setStartValue(QColor("#fff9ef"))
        self._pulse.setKeyValueAt(0.5, QColor("#ffe7b9"))
        self._pulse.setEndValue(QColor("#fff9ef"))
        self._pulse.valueChanged.connect(self._paint_active)
        self.set_state("pending")

    def _paint_active(self, background):
        if self._state != "active":
            return
        color = background.name() if isinstance(background, QColor) else "#fff5df"
        self.setStyleSheet(
            f"QFrame#phaseCard {{ background: {color}; border: 2px solid {self.accent}; "
            "border-radius: 17px; }}"
        )

    def set_state(self, state: str):
        if state == self._state:
            return
        self._state = state
        palettes = {
            "pending": ("#fffdf8", "#d8cdbc", "#8b8a84", "等待"),
            "active": ("#fff5df", self.accent, self.accent, "进行中"),
            "done": ("#edf5e9", "#8eb08b", GREEN, "已完成"),
            "failed": ("#fff0eb", CORAL, CORAL, "需处理"),
        }
        background, border, icon_color, label = palettes.get(state, palettes["pending"])
        self.setStyleSheet(
            f"QFrame#phaseCard {{ background: {background}; border: 1px solid {border}; "
            "border-radius: 17px; }}"
        )
        self.icon_label.setPixmap(_icon(self.icon_name, icon_color).pixmap(QSize(25, 25)))
        self.icon_label.setStyleSheet(
            f"background: #fffdf8; border: 2px solid {icon_color}; border-radius: 21px;"
        )
        self.state_label.setText(label)
        self.state_label.setStyleSheet(f"color: {icon_color}; font-size: 11px; font-weight: 800;")
        if state == "active":
            self._pulse.start()
        else:
            self._pulse.stop()


class RunningIndicator(QLabel):
    """Small animated status pill that remains readable without relying on motion."""

    def __init__(self, parent=None):
        super().__init__("运行中", parent)
        self._step = 0
        self._running = False
        self.setStyleSheet(
            f"background:#fff2d7; color:{AMBER}; border:1px solid #e7c27f; "
            "border-radius:11px; padding:4px 10px; font-size:11px; font-weight:800;"
        )
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(320)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._step = (self._step + 1) % 4
        self.setText("运行中" + " ·" * self._step)

    def set_running(self, running: bool):
        running = bool(running)
        if running == self._running:
            return
        self._running = running
        if running:
            self._timer.start()
            self._tick()
        else:
            self._timer.stop()
            self._step = 0
            self.setText("阶段衔接")


class TaskEventCard(QFrame):
    """Rounded, glanceable representation of one structured pipeline event."""

    ICONS = {
        "准备": "fa5s.hourglass-start",
        "开始": "fa5s.play",
        "完成": "fa5s.check",
        "失败": "fa5s.exclamation",
        "缓存": "fa5s.database",
        "并行": "fa5s.project-diagram",
        "批次": "fa5s.layer-group",
        "素材": "fa5s.file-video",
        "取消": "fa5s.stop",
        "自愈": "fa5s.shield-alt",
    }

    def __init__(self, badge: str, message: str, color: str, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(48)
        self.setStyleSheet(
            f"QFrame {{ background:#fffdf8; border:1px solid #e4dac9; border-radius:13px; }}"
            f"QLabel#eventIcon {{ background:{color}; border:0; border-radius:10px; }}"
            f"QLabel#eventBadge {{ color:{color}; border:0; font-size:11px; font-weight:800; }}"
            f"QLabel#eventMessage {{ color:{INK}; border:0; font-size:12px; }}"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 7, 10, 7)
        row.setSpacing(9)
        icon = QLabel()
        icon.setObjectName("eventIcon")
        icon.setFixedSize(28, 28)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(_icon(self.ICONS.get(badge, "fa5s.circle"), "#ffffff").pixmap(QSize(12, 12)))
        row.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(0)
        badge_label = QLabel(str(badge))
        badge_label.setObjectName("eventBadge")
        message_label = QLabel(str(message))
        message_label.setObjectName("eventMessage")
        message_label.setWordWrap(True)
        text.addWidget(badge_label)
        text.addWidget(message_label)
        row.addLayout(text, 1)


class FlowStage(QWidget):
    def __init__(self, icon_name: str, title: str, subtitle: str, color: str):
        super().__init__()
        self.color = color
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(50, 50)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setPixmap(_icon(icon_name, color).pixmap(QSize(31, 31)))
        self.icon_label.setStyleSheet(
            f"border: 2px solid {color}; border-radius: 25px; background: #fffdf8;"
        )
        self.title_label = QLabel(title)
        self.title_label.setObjectName("title")
        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("muted")
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(self.title_label)
        text.addWidget(self.subtitle_label)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.icon_label)
        layout.addLayout(text)

    def set_state(self, state: str):
        opacity = "1.0" if state in {"active", "done"} else "0.68"
        fill = "#edf5ed" if state == "done" else ("#fff8e9" if state == "active" else "#fffdf8")
        self.setStyleSheet(f"opacity: {opacity};")
        self.icon_label.setStyleSheet(
            f"border: 2px solid {self.color}; border-radius: 25px; background: {fill};"
        )


class WorkflowStrip(QFrame):
    hover_entered = Signal()
    hover_left = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workflow")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 10, 18, 15)
        outer.setSpacing(7)
        ribbon = QLabel("  字幕生成流程  ")
        ribbon.setObjectName("sectionTitle")
        ribbon.setFixedHeight(42)
        ribbon.setMaximumWidth(174)
        outer.addWidget(ribbon, 0, Qt.AlignmentFlag.AlignLeft)
        row = QHBoxLayout()
        row.setSpacing(17)
        specs = [
            ("fa5s.wave-square", "本地识别", "语音转写", GREEN),
            ("fa5s.pen-nib", "字幕校对", "识别错误修正", AMBER),
            ("fa5s.comment-alt", "全文断句", "添加标点与分句", BLUE),
            ("fa5s.file-export", "导出", "生成字幕文件", CORAL),
        ]
        self.stages = []
        for index, spec in enumerate(specs):
            stage = FlowStage(*spec)
            self.stages.append(stage)
            row.addWidget(stage, 1)
            if index < len(specs) - 1:
                arrow = QLabel()
                arrow.setPixmap(_icon("fa5s.arrow-right", "#99978f").pixmap(QSize(22, 22)))
                row.addWidget(arrow)
        outer.addLayout(row)
        self.set_active(0)

    def enterEvent(self, event):
        self.hover_entered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_left.emit()
        super().leaveEvent(event)

    def set_active(self, index: int, finished: bool = False):
        for stage_index, stage in enumerate(self.stages):
            if finished or stage_index < index:
                state = "done"
            elif stage_index == index:
                state = "active"
            else:
                state = "pending"
            stage.set_state(state)


class CollapsibleFrame(QFrame):
    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        icon_name: str,
        summary: str = "",
        expanded: bool = False,
        action_text: str = "",
    ):
        super().__init__()
        self.setObjectName("accordion")
        self._expanded = bool(expanded)
        self.header = QWidget()
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(10, 4, 10, 4)
        header_layout.setSpacing(10)
        self.title_button = AnimatedButton(title)
        self.title_button.setObjectName("accordionButton")
        self.title_button.setIcon(_icon(icon_name))
        self.title_button.setIconSize(QSize(21, 21))
        self.title_button.clicked.connect(lambda: self.set_expanded(not self._expanded))
        header_layout.addWidget(self.title_button)
        self.summary_label = QLabel(summary)
        self.summary_label.setObjectName("muted")
        header_layout.addWidget(self.summary_label, 1)
        if action_text:
            self.action_button = AnimatedButton(action_text)
            self.action_button.clicked.connect(lambda: self.set_expanded(True))
            header_layout.addWidget(self.action_button)
        else:
            self.action_button = None
        self.chevron = AnimatedButton()
        self.chevron.setObjectName("flat")
        self.chevron.setFixedSize(34, 34)
        self.chevron.clicked.connect(lambda: self.set_expanded(not self._expanded))
        header_layout.addWidget(self.chevron)
        self._title = title
        self._summary = summary
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(16, 3, 16, 15)
        self.content_layout.setSpacing(10)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addWidget(self.content)
        self.animation = QPropertyAnimation(self.content, b"maximumHeight", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.set_expanded(expanded, animate=False)

    def set_summary(self, summary: str):
        self._summary = summary
        self._refresh_header()

    def _refresh_header(self):
        self.summary_label.setText(self._summary)
        icon_name = "fa5s.chevron-up" if self._expanded else "fa5s.chevron-down"
        self.chevron.setIcon(_icon(icon_name))
        self.chevron.setIconSize(QSize(14, 14))

    def set_expanded(self, expanded: bool, animate: bool = True):
        self._expanded = bool(expanded)
        target = self.content.sizeHint().height() if expanded else 0
        self.content.setVisible(True)
        self.content.setMinimumHeight(0)
        if animate:
            self.animation.stop()
            self.animation.setStartValue(self.content.maximumHeight())
            self.animation.setEndValue(target)
            self.animation.start()
        else:
            self.content.setMaximumHeight(target)
        self._refresh_header()
        self.toggled.emit(bool(expanded))


class EndpointEditor(QFrame):
    def __init__(self, title: str, accent: str, stage: str, settings: dict):
        super().__init__()
        self.setObjectName("endpointCard")
        self.stage = stage
        self.accent = accent
        models = settings["models"]
        prefix = "polish" if stage == "polish" else "group"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 13)
        self.title_label = QLabel(f"●  {title}")
        self.title_label.setStyleSheet(f"color: {accent}; font-size: 15px; font-weight: 700;")
        layout.addWidget(self.title_label)
        form = QFormLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self.provider = QComboBox()
        for key, spec in PROVIDER_PRESETS.items():
            self.provider.addItem(spec["label"], key)
        current_provider = models.get(f"{prefix}_provider", "bailian")
        self.provider.setCurrentIndex(max(0, self.provider.findData(current_provider)))
        self.model = QComboBox()
        self.model.setEditable(True)
        defaults = [
            "qwen3.7-flash-2026-07-15",
            "qwen3-max",
            "glm-5.2",
        ]
        self.model.addItems(defaults)
        self.model.setCurrentText(models.get(f"{prefix}_model", ""))
        self.base_url = QLineEdit(models.get(f"{prefix}_base_url", ""))
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        existing, source = resolve_api_key(stage)
        self.key.setPlaceholderText(f"已配置：{source}" if existing else "请输入 API Key")
        self.test_button = AnimatedButton("测试连接")
        self.status = QLabel("已配置" if existing else "未配置密钥")
        self.status.setObjectName("statusGood" if existing else "statusWarn")
        key_row = QHBoxLayout()
        key_row.addWidget(self.key, 1)
        key_row.addWidget(self.test_button)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status)
        status_row.addStretch(1)
        form.addRow("服务商预设", self.provider)
        form.addRow("模型名称", self.model)
        form.addRow("API 地址", self.base_url)
        form.addRow("API 密钥", key_row)
        form.addRow("", status_row)
        layout.addLayout(form)
        self.provider.currentIndexChanged.connect(self._provider_changed)
        self.test_button.clicked.connect(self.test_connection)
        self._tester = None

    def refresh_secret_status(self):
        existing, source = resolve_api_key(self.stage)
        self.key.setPlaceholderText(f"已配置：{source}" if existing else "请输入 API Key")
        self.status.setObjectName("statusGood" if existing else "statusWarn")
        self.status.setText("密钥已保存" if existing else "尚未配置密钥")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _provider_changed(self):
        provider = self.provider.currentData()
        preset = PROVIDER_PRESETS.get(provider, {})
        if provider != "custom":
            self.base_url.setText(preset.get("base_url", ""))

    def values(self) -> dict:
        return {
            "provider": str(self.provider.currentData()),
            "model": self.model.currentText().strip(),
            "base_url": normalize_base_url(self.base_url.text()),
            "key": self.key.text().strip(),
        }

    def test_connection(self):
        values = self.values()
        key = values["key"] or resolve_api_key(self.stage)[0]
        endpoint = {
            **values,
            "api_key": key,
            "url": f"{values['base_url']}/chat/completions" if values["base_url"] else "",
        }
        try:
            validate_endpoint(endpoint, "当前模型")
        except RuntimeError as exc:
            self.status.setObjectName("statusWarn")
            self.status.setText(str(exc))
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            return
        self.test_button.setEnabled(False)
        self.status.setText("正在测试…")
        self._tester = ConnectionTester(endpoint)
        self._tester.finished_status.connect(self._connection_finished)
        self._tester.start()

    def _connection_finished(self, ok: bool, message: str):
        self.test_button.setEnabled(True)
        self.status.setObjectName("statusGood" if ok else "statusWarn")
        self.status.setText(message)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)


def persist_ai_configuration(
    legacy,
    polish: dict,
    group: dict,
    *,
    unified: bool,
    share_key: bool,
    require_ready: bool,
) -> dict:
    """Validate and persist AI form values without requiring a subtitle run."""
    polish = dict(group) if unified else dict(polish)
    group = dict(group)
    polish_key = str(polish.get("key", "") or "").strip()
    group_key = str(group.get("key", "") or "").strip()
    existing_polish_key = resolve_api_key("polish")[0]
    existing_group_key = resolve_api_key("group")[0]
    effective_polish_key = (
        group_key or existing_group_key
        if unified
        else polish_key or existing_polish_key
    )
    effective_group_key = (
        polish_key
        if share_key and not unified and polish_key
        else group_key or existing_group_key
    )
    missing_keys = []
    for label, values, api_key in (
        ("字幕校对模型", polish, effective_polish_key),
        ("全文断句模型", group, effective_group_key),
    ):
        if not api_key:
            missing_keys.append(label)
        validate_endpoint(
            {
                **values,
                "api_key": api_key or ("save-without-key" if not require_ready else ""),
            },
            label,
        )
    models = {
        "polish_provider": polish["provider"],
        "polish_model": polish["model"],
        "polish_base_url": polish["base_url"],
        "group_provider": group["provider"],
        "group_model": group["model"],
        "group_base_url": group["base_url"],
    }
    legacy.configure_runtime_llms(
        models,
        polish_key=("" if unified else polish_key),
        group_key=group_key,
        share_key=(share_key and not unified),
        unified_glm_processing=unified,
    )
    return {"models": models, "missing_keys": tuple(missing_keys)}


class ConnectionTester(QThread):
    finished_status = Signal(bool, str)

    def __init__(self, endpoint: dict):
        super().__init__()
        self.endpoint = endpoint

    def run(self):
        try:
            response = requests.post(
                self.endpoint["url"],
                headers={"Authorization": f"Bearer {self.endpoint['api_key']}", "Content-Type": "application/json"},
                json={
                    "model": self.endpoint["model"],
                    "messages": [{"role": "user", "content": "只回复 OK"}],
                    "temperature": 0,
                    "max_tokens": 4,
                },
                timeout=(6, 20),
            )
            response.raise_for_status()
            self.finished_status.emit(True, "连接成功")
        except Exception as exc:
            compact = " ".join(str(exc).split())[:90]
            self.finished_status.emit(False, f"连接失败：{compact}")


class PipelineWorker(QThread):
    event_received = Signal(object)
    console_received = Signal(str, str)
    result_ready = Signal(object)
    unexpected_error = Signal(str)

    def __init__(self, media_paths, options, token, legacy, pipeline, startup_self_test):
        super().__init__()
        self.media_paths = list(media_paths)
        self.options = options
        self.token = token
        self.legacy = legacy
        self.pipeline = pipeline
        self.startup_self_test = startup_self_test

    def run(self):
        stdout_stream = SignalTextStream(self.console_received, "stdout", sys.stdout)
        stderr_stream = SignalTextStream(self.console_received, "stderr", sys.stderr)
        try:
            with redirect_stdout(stdout_stream), redirect_stderr(stderr_stream):
                startup_self_test = self.startup_self_test
                if startup_self_test is None:
                    print("[后台自测] 首次开始任务，正在检查字幕护栏……")
                    startup_self_test = self.legacy.run_startup_self_test()
                    print(
                        f"[后台自测通过] {startup_self_test['id']}："
                        f"{startup_self_test['checks']} 项关键护栏正常"
                    )
                result = run_media_queue(
                    self.media_paths,
                    self.options,
                    event_sink=self.event_received.emit,
                    cancel_token=self.token,
                    _legacy=self.legacy,
                    _pipeline=self.pipeline,
                    _startup_self_test=startup_self_test,
                )
            self.result_ready.emit(result)
        except BaseException as exc:
            self.unexpected_error.emit(" ".join(str(exc).split()) or exc.__class__.__name__)
        finally:
            stdout_stream.flush()
            stderr_stream.flush()


class PromptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("项目内置提示词")
        self.resize(720, 480)
        layout = QVBoxLayout(self)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "字幕校对提示词（项目内置，只读）\n\n"
            "模型会收到 MOSS 主稿、FireRed/Qwen3-ASR 独立证据、项目背景、术语候选和严格安全规则；"
            "只能返回结构化修正，不允许自由改写原话。\n\n"
            "全文断句提示词（项目内置，只读）\n\n"
            "模型只能在已经校对的原文中插入字幕边界；不得增删改字，必须保留硬边界、完整词、"
            "说话人切换与真实停顿。更换服务商或模型不会移除这些提示词。"
        )
        layout.addWidget(text)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        apply_ui_language(self)


class DropOverlay(QFrame):
    """Full-window drag target that dims the workbench without stealing drops."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch(1)
        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(_icon("fa5s.file-upload", GREEN).pixmap(QSize(82, 82)))
        layout.addWidget(icon)
        layout.addSpacing(12)
        self.title = QLabel("把文件放入这里")
        self.title.setObjectName("dropOverlayTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        self.hint = QLabel("松开鼠标即可添加视频或音频 · 支持多选")
        self.hint.setObjectName("dropOverlayHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.hint)
        layout.addStretch(1)

        self.opacity = QGraphicsOpacityEffect(self)
        self.opacity.setOpacity(0.0)
        self.setGraphicsEffect(self.opacity)
        self.animation = QPropertyAnimation(self.opacity, b"opacity", self)
        self.animation.setDuration(150)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self._finish_animation)
        self._requested_visible = False
        self.hide()

    def set_file_count(self, count: int):
        self.hint.setText(
            f"松开鼠标即可放入 {count} 个可用文件"
            if count > 1
            else "松开鼠标即可添加这个视频或音频"
        )

    def set_active(self, active: bool):
        self._requested_visible = bool(active)
        self.animation.stop()
        if active:
            self.show()
            self.raise_()
            start = max(0.0, float(self.opacity.opacity()))
            self.animation.setDuration(150)
            self.animation.setStartValue(start)
            self.animation.setEndValue(1.0)
        else:
            self.animation.setDuration(105)
            self.animation.setStartValue(float(self.opacity.opacity()))
            self.animation.setEndValue(0.0)
        self.animation.start()

    def _finish_animation(self):
        if not self._requested_visible:
            self.hide()


class MainWindow(QWidget):
    def __init__(self, media_paths, legacy, pipeline, startup_self_test):
        super().__init__()
        self.media_paths = list(media_paths)
        self.legacy = legacy
        self.pipeline = pipeline
        self.startup_self_test = startup_self_test
        self.token = None
        self.worker = None
        self.started_at = 0.0
        self.result_exit_code = 0
        self._completion_dialog = None
        self.setAcceptDrops(True)
        self.setObjectName("appRoot")
        self.setWindowTitle("2ByteASR｜智能游戏字幕工作台")
        self.setWindowIcon(_app_icon())
        self.resize(1180, 840)
        self.setMinimumSize(1020, 720)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 22)
        root.setSpacing(13)
        root.addLayout(self._header())
        self.workflow = WorkflowStrip(self)
        self.workflow.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.workflow.setMinimumHeight(0)
        self.workflow.setMaximumHeight(0)
        self.workflow.hide()
        workflow_shadow = QGraphicsDropShadowEffect(self.workflow)
        workflow_shadow.setBlurRadius(24)
        workflow_shadow.setOffset(0, 7)
        workflow_shadow.setColor(QColor(52, 53, 50, 70))
        self.workflow.setGraphicsEffect(workflow_shadow)
        root.addWidget(self.workflow)
        self._workflow_expanded = False
        self._workflow_target_height = max(132, self.workflow.sizeHint().height())
        self._workflow_animation = QPropertyAnimation(self.workflow, b"maximumHeight", self)
        self._workflow_animation.finished.connect(self._workflow_animation_finished)
        self._workflow_show_timer = QTimer(self)
        self._workflow_show_timer.setSingleShot(True)
        self._workflow_show_timer.setInterval(100)
        self._workflow_show_timer.timeout.connect(self.show_workflow_popover)
        self._workflow_hide_timer = QTimer(self)
        self._workflow_hide_timer.setSingleShot(True)
        self._workflow_hide_timer.setInterval(380)
        self._workflow_hide_timer.timeout.connect(self._collapse_workflow)
        self.brand.hover_entered.connect(self._queue_workflow_show)
        self.brand.hover_left.connect(self._queue_workflow_hide)
        self.workflow.hover_entered.connect(self._keep_workflow_open)
        self.workflow.hover_left.connect(self._queue_workflow_hide)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._scrollable(self._settings_page()))
        self.pages.addWidget(self._progress_page())
        self.pages.addWidget(self._result_page())
        root.addWidget(self.pages, 1)
        self.drop_overlay = DropOverlay(self)
        self.drop_overlay.setGeometry(self.rect().adjusted(16, 16, -16, -16))
        self.drop_overlay.hide()
        self._refresh_ai_summary()
        self._apply_ui_language()

    def _apply_ui_language(self):
        code = current_language()
        self._ui_language = code
        self.setWindowTitle("2ByteASR｜" + translate("智能游戏字幕工作台", code))
        apply_ui_language(self, code)

    def _change_language(self, index):
        code = self.language_combo.itemData(index) or "zh"
        save_language(code)
        self._apply_ui_language()

    def _scrollable(self, widget: QWidget) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        area.setWidget(widget)
        return area

    def _header(self):
        row = QHBoxLayout()
        mascot = QLabel()
        mascot.setFixedSize(50, 50)
        if APP_ICON_SOURCE_PATH.is_file():
            pixmap = QPixmap(str(APP_ICON_SOURCE_PATH)).scaled(
                QSize(50, 50),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            mascot.setPixmap(pixmap)
        elif APP_ICON_FALLBACK_PATH.is_file():
            mascot.setPixmap(
                QPixmap(str(APP_ICON_FALLBACK_PATH)).scaled(
                    QSize(50, 50),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        mascot.setStyleSheet("border: 0; background: transparent;")
        mascot.setToolTip("2ByteASR")
        self.brand = BrandLabel("2ByteASR")
        self.brand.setObjectName("brand")
        self.brand.setCursor(Qt.CursorShape.PointingHandCursor)
        self.brand.setToolTip("悬停查看字幕生成流程")
        subtitle = QLabel("智能游戏字幕工作台")
        subtitle.setStyleSheet("font-size: 16px;")
        self.header_status = QLabel("")
        self.header_status.setObjectName("statusGood")
        row.addWidget(mascot)
        row.addWidget(self.brand)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet(f"color: {LINE};")
        row.addWidget(separator)
        row.addWidget(subtitle)
        row.addSpacing(10)
        row.addWidget(self.header_status)
        row.addStretch(1)
        self.language_combo = QComboBox()
        self.language_combo.addItem("中文", "zh")
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("日本語", "ja")
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(current_language()))
        )
        self.language_combo.currentIndexChanged.connect(self._change_language)
        row.addWidget(self.language_combo)
        return row

    def _queue_workflow_show(self):
        self._workflow_hide_timer.stop()
        self._workflow_show_timer.start()

    def _queue_workflow_hide(self):
        self._workflow_show_timer.stop()
        self._workflow_hide_timer.start()

    def _keep_workflow_open(self):
        self._workflow_hide_timer.stop()

    def show_workflow_popover(self):
        self._workflow_hide_timer.stop()
        if self._workflow_expanded and self.workflow.isVisible():
            return
        self._workflow_expanded = True
        self.workflow.show()
        start = max(0, self.workflow.maximumHeight())
        self._workflow_animation.stop()
        self._workflow_animation.setDuration(430)
        self._workflow_animation.setEasingCurve(QEasingCurve.Type.OutBack)
        self._workflow_animation.setStartValue(start)
        self._workflow_animation.setEndValue(self._workflow_target_height)
        self._workflow_animation.start()

    def _collapse_workflow(self):
        if self.brand.underMouse() or self.workflow.underMouse():
            self._workflow_hide_timer.start()
            return
        if not self.workflow.isVisible():
            return
        self._workflow_expanded = False
        self._workflow_animation.stop()
        self._workflow_animation.setDuration(280)
        self._workflow_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._workflow_animation.setStartValue(self.workflow.maximumHeight())
        self._workflow_animation.setEndValue(0)
        self._workflow_animation.start()

    def _workflow_animation_finished(self):
        if not self._workflow_expanded and self.workflow.maximumHeight() <= 0:
            self.workflow.hide()

    def _settings_page(self):
        page = QWidget()
        page.setObjectName("settingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        title = QLabel("本批字幕内容设置")
        title.setObjectName("sectionTitle")
        title.setMaximumWidth(245)
        layout.addWidget(title)
        # 素材区放在最上方：用户应先放入素材，再配置内容设置。
        self.media_frame = QFrame()
        self.media_frame.setObjectName("mediaRow")
        self.media_frame.setProperty("dropActive", False)
        self.media_frame.setMinimumHeight(68)
        media_row = QHBoxLayout(self.media_frame)
        media_row.setContentsMargins(16, 11, 13, 11)
        media_icon = QLabel()
        media_icon.setPixmap(_icon("fa5s.file-audio").pixmap(QSize(20, 20)))
        media_row.addWidget(media_icon)
        media_row.addWidget(QLabel("本地素材"))
        media_row.addSpacing(20)
        media_text = QVBoxLayout()
        media_text.setSpacing(1)
        self.media_name = QLabel("")
        self.media_name.setStyleSheet("font-weight: 700; color: #5d3e20;")
        self.media_drop_hint = QLabel("可把视频 / 音频拖到窗口，或点击右侧选择")
        self.media_drop_hint.setObjectName("dropHint")
        media_text.addWidget(self.media_name)
        media_text.addWidget(self.media_drop_hint)
        media_row.addLayout(media_text, 1)
        choose_media = AnimatedButton("选择素材")
        choose_media.setIcon(_icon("fa5s.folder-open"))
        choose_media.clicked.connect(self._choose_media)
        media_row.addWidget(choose_media)
        layout.addWidget(self.media_frame)
        surface = QFrame()
        surface.setObjectName("settingsSurface")
        surface_layout = QHBoxLayout(surface)
        surface_layout.setContentsMargins(18, 14, 18, 14)
        surface_layout.setSpacing(24)
        left = QVBoxLayout()
        left.setSpacing(10)
        name_label = QLabel("●  游戏 / 内容名称")
        name_label.setStyleSheet("font-weight: 700; color: #5b564c;")
        left.addWidget(name_label)
        self.game_box = EditableHistoryCombo()
        choices = []
        seen = set()
        for value in (*self.legacy.load_runtime_game_history(), *self.legacy.BUILTIN_GAME_PROFILES):
            canonical = self.legacy.canonicalize_runtime_game_name(value)
            identity = self.legacy.runtime_game_identity(canonical)
            if canonical and identity not in seen:
                choices.append(canonical)
                seen.add(identity)
        self.game_box.addItems(choices)
        self.game_box.setCurrentIndex(-1)
        self.game_box.setPlaceholderText("选择历史记录或内置游戏，也可以直接输入；留空为通用模式")
        self.game_box.setToolTip("点击右侧箭头选择历史记录或内置游戏；输入新名称也会自动保存")
        left.addWidget(self.game_box)
        left.addSpacing(8)
        self.terms = SwitchControl("游戏术语增强")
        self.terms.setToolTip("本地图鉴候选 + 联网复核；PVP 内容建议开启")
        self.game_box.currentTextChanged.connect(self._auto_enable_terms)
        left.addWidget(self.terms)
        terms_note = QLabel("启用术语增强（本地图鉴候选 + 联网复核，PVP 时勾选）")
        terms_note.setObjectName("muted")
        terms_note.setWordWrap(True)
        left.addWidget(terms_note)
        # 手动添加术语：输入角色名 / 技能名等专名，立即写入该游戏的术语表
        term_row = QHBoxLayout()
        self.term_input = QLineEdit()
        self.term_input.setPlaceholderText("添加专名（角色名 / 技能名 / 物品名），回车确认")
        self.term_input.setToolTip("手动确认的专名会作为强参考参与本地校对，也会进入联网复核候选")
        self.term_input.returnPressed.connect(self._add_custom_term)
        add_term = AnimatedButton("添加术语")
        add_term.setIcon(_icon("fa5s.plus"))
        add_term.setMaximumWidth(120)
        add_term.clicked.connect(self._add_custom_term)
        term_row.addWidget(self.term_input, 1)
        term_row.addWidget(add_term)
        left.addLayout(term_row)
        term_hint = QLabel("内置词表（角色 / 技能名）可在“管理已学习术语”中查看")
        term_hint.setObjectName("muted")
        left.addWidget(term_hint)
        self.term_hint = term_hint
        right = QVBoxLayout()
        right.setSpacing(10)
        self.review_track = SwitchControl("输出疑似吞字幕复核轨")
        self.review_track.setChecked(self.legacy.RUNTIME_SETTINGS["switches"]["output_review_track"])
        right.addWidget(self.review_track)
        review_note = QLabel("默认关闭，不影响主播分轨；复核轨保存到项目 review_tracks/")
        review_note.setObjectName("muted")
        right.addWidget(review_note)
        speaker_label = QLabel("预计主播人数")
        speaker_label.setStyleSheet("font-weight: 600;")
        right.addWidget(speaker_label)
        self.expected_speakers = QComboBox()
        self.expected_speakers.addItems(["自动", "1", "2", "3", "4", "5", "6"])
        self.expected_speakers.setMaximumWidth(190)
        right.addWidget(self.expected_speakers)
        manage = AnimatedButton("管理已学习术语")
        manage.setIcon(_icon("fa5s.book-open"))
        manage.clicked.connect(self._manage_terms)
        manage.setMaximumWidth(190)
        right.addWidget(manage)
        surface_layout.addLayout(left, 62)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet(f"color: {LINE};")
        surface_layout.addWidget(divider)
        surface_layout.addLayout(right, 38)
        layout.addWidget(surface)

        settings = self.legacy.RUNTIME_SETTINGS
        self.ai_panel = CollapsibleFrame(
            "AI 模型与密钥",
            "fa5s.project-diagram",
            expanded=True,
        )
        self.unified_glm = SwitchControl("同一云端模型负责字幕校对与全文断句（推荐）")
        self.unified_glm.setChecked(
            settings["switches"].get("unified_glm_processing", True)
        )
        self.ai_panel.content_layout.addWidget(self.unified_glm)
        endpoint_row = QHBoxLayout()
        self.polish_editor = EndpointEditor("字幕校对模型", CORAL, "polish", settings)
        self.group_editor = EndpointEditor("全文断句模型", BLUE, "group", settings)
        endpoint_row.addWidget(self.polish_editor, 1)
        endpoint_row.addWidget(self.group_editor, 1)
        self.ai_panel.content_layout.addLayout(endpoint_row)
        prompt_row = QHBoxLayout()
        self.share_key = SwitchControl("两阶段共用新填写的校对密钥")
        self.share_key.setChecked(True)
        prompt_button = AnimatedButton("查看项目内置提示词")
        prompt_button.setObjectName("linkButton")
        prompt_button.setIcon(_icon("fa5s.info-circle"))
        prompt_button.clicked.connect(lambda: PromptDialog(self).exec())
        self.save_ai_button = AnimatedButton("保存 AI 配置")
        self.save_ai_button.setObjectName("outline")
        self.save_ai_button.setIcon(_icon("fa5s.save"))
        self.save_ai_button.clicked.connect(
            lambda: self._save_ai_configuration(show_feedback=True)
        )
        prompt_row.addWidget(self.share_key)
        prompt_row.addStretch(1)
        prompt_row.addWidget(prompt_button)
        prompt_row.addWidget(self.save_ai_button)
        self.ai_panel.content_layout.addLayout(prompt_row)
        self.ai_save_status = QLabel("供应商、模型、地址和新填写的密钥可在这里单独保存")
        self.ai_save_status.setObjectName("muted")
        self.ai_panel.content_layout.addWidget(self.ai_save_status)
        self.unified_glm.toggled.connect(self._apply_unified_glm_mode)
        self.polish_editor.model.currentTextChanged.connect(self._refresh_ai_summary)
        self.group_editor.model.currentTextChanged.connect(self._refresh_ai_summary)
        for editor in (self.polish_editor, self.group_editor):
            editor.provider.currentIndexChanged.connect(self._mark_ai_configuration_dirty)
            editor.provider.currentIndexChanged.connect(self._refresh_ai_summary)
            editor.model.currentTextChanged.connect(self._mark_ai_configuration_dirty)
            editor.base_url.textChanged.connect(self._mark_ai_configuration_dirty)
            editor.key.textChanged.connect(self._mark_ai_configuration_dirty)
        self.unified_glm.toggled.connect(self._mark_ai_configuration_dirty)
        self.share_key.toggled.connect(self._mark_ai_configuration_dirty)
        self._apply_unified_glm_mode(self.unified_glm.isChecked())
        layout.addWidget(self.ai_panel)
        # CollapsibleFrame 在构造时内容为空，展开高度会被锁死；
        # 内容添加完毕后重新计算一次，避免“收起再打开才正常”的假死状态。
        self.ai_panel.set_expanded(True, animate=False)

        self.advanced_panel = CollapsibleFrame("高级设置（缓存与覆盖）", "fa5s.cog", expanded=False)
        advanced_row = QHBoxLayout()
        self.refresh_polish = SwitchControl("刷新字幕校对缓存")
        self.refresh_polish.setChecked(settings["cache"]["force_refresh_polish"])
        self.refresh_group = SwitchControl("刷新全文断句缓存")
        self.refresh_group.setChecked(settings["cache"]["force_refresh_group"])
        self.overwrite = QComboBox()
        self.overwrite.addItem("覆盖已有结果", "overwrite")
        self.overwrite.addItem("跳过已有结果", "skip")
        self.overwrite.addItem("已有结果则报错", "error")
        advanced_row.addWidget(self.refresh_polish)
        advanced_row.addWidget(self.refresh_group)
        advanced_row.addStretch(1)
        advanced_row.addWidget(QLabel("已有字幕："))
        advanced_row.addWidget(self.overwrite)
        self.advanced_panel.content_layout.addLayout(advanced_row)
        layout.addWidget(self.advanced_panel)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self.start_button = AnimatedButton("开始生成字幕")
        self.start_button.setObjectName("primary")
        self.start_button.setIcon(_icon("fa5s.play-circle", "white"))
        self.start_button.setIconSize(QSize(24, 24))
        self.start_button.clicked.connect(self._start_run)
        cancel = AnimatedButton("取消")
        cancel.clicked.connect(self.close)
        action_row.addWidget(self.start_button)
        action_row.addSpacing(20)
        action_row.addWidget(cancel)
        action_row.addStretch(1)
        layout.addLayout(action_row)
        self._refresh_media_summary()
        has_required_keys = bool(resolve_api_key("group")[0]) if self.unified_glm.isChecked() else bool(
            resolve_api_key("polish")[0] and resolve_api_key("group")[0]
        )
        if not has_required_keys:
            self.ai_panel.set_expanded(True, animate=False)
        return page

    def _progress_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 14, 24, 16)
        layout.setSpacing(10)

        hero = QFrame()
        hero.setObjectName("progressHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 15, 16, 15)
        hero_layout.setSpacing(13)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        title = QLabel("2ByteASR 正在制作字幕")
        title.setStyleSheet("font-size: 22px; font-weight: 800;")
        hero_text.addWidget(title)
        self.progress_context = QLabel("正在准备任务…")
        self.progress_context.setObjectName("muted")
        hero_text.addWidget(self.progress_context)
        hero_layout.addLayout(hero_text, 1)
        self.progress_percent = QLabel("0%")
        self.progress_percent.setObjectName("progressPercent")
        hero_layout.addWidget(self.progress_percent)
        layout.addWidget(hero)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        self._progress_motion = QPropertyAnimation(self.progress_bar, b"value", self)
        self._progress_motion.setDuration(460)
        self._progress_motion.setEasingCurve(QEasingCurve.Type.OutCubic)

        phase_row = QHBoxLayout()
        phase_row.setSpacing(8)
        self.phase_cards = [
            ProgressPhaseCard("fa5s.wave-square", "本地识别", "转写与主播", GREEN),
            ProgressPhaseCard("fa5s.magic", "字幕校对", "模型安全纠错", AMBER),
            ProgressPhaseCard("fa5s.comment-alt", "全文断句", "语义与时间轴", BLUE),
            ProgressPhaseCard("fa5s.file-export", "字幕导出", "文稿与报告", CORAL),
        ]
        for card in self.phase_cards:
            phase_row.addWidget(card, 1)
        layout.addLayout(phase_row)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(10)
        left_column = QVBoxLayout()
        left_column.setSpacing(10)

        current_card = QFrame()
        current_card.setObjectName("currentStageCard")
        current_layout = QVBoxLayout(current_card)
        current_layout.setContentsMargins(15, 12, 15, 13)
        current_layout.setSpacing(4)
        eyebrow_row = QHBoxLayout()
        eyebrow = QLabel("●  当前步骤")
        eyebrow.setObjectName("stageEyebrow")
        eyebrow_row.addWidget(eyebrow)
        self.running_indicator = RunningIndicator()
        eyebrow_row.addWidget(self.running_indicator)
        eyebrow_row.addStretch(1)
        self.stage_elapsed = QLabel("00:00")
        self.stage_elapsed.setObjectName("consoleBadge")
        eyebrow_row.addWidget(self.stage_elapsed)
        current_layout.addLayout(eyebrow_row)
        self.progress_stage = QLabel("等待启动")
        self.progress_stage.setObjectName("stageLarge")
        self.progress_stage.setWordWrap(True)
        current_layout.addWidget(self.progress_stage)
        self.progress_resource = QLabel("准备检查运行环境")
        self.progress_resource.setObjectName("muted")
        self.progress_resource.setWordWrap(True)
        current_layout.addWidget(self.progress_resource)
        self.active_tasks_label = QLabel("尚无运行中的子任务")
        self.active_tasks_label.setWordWrap(True)
        self.active_tasks_label.setStyleSheet(
            "background: #f6efe3; border-radius: 8px; padding: 7px 9px; color: #5f5d58;"
        )
        current_layout.addWidget(self.active_tasks_label)
        left_column.addWidget(current_card)

        feed_card = QFrame()
        feed_card.setObjectName("eventFeedCard")
        feed_layout = QVBoxLayout(feed_card)
        feed_layout.setContentsMargins(13, 10, 13, 11)
        feed_header = QHBoxLayout()
        feed_title = QLabel("任务动态")
        feed_title.setStyleSheet("font-size: 15px; font-weight: 800;")
        feed_header.addWidget(feed_title)
        feed_header.addStretch(1)
        feed_note = QLabel("结构化进度")
        feed_note.setObjectName("consoleBadge")
        feed_header.addWidget(feed_note)
        feed_layout.addLayout(feed_header)
        self.event_log = QListWidget()
        self.event_log.setObjectName("eventFeed")
        self.event_log.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.event_log.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.event_log.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        feed_layout.addWidget(self.event_log, 1)
        left_column.addWidget(feed_card, 1)
        detail_row.addLayout(left_column, 5)

        console_card = QFrame()
        console_card.setObjectName("consoleCard")
        console_layout = QVBoxLayout(console_card)
        console_layout.setContentsMargins(13, 10, 13, 11)
        console_header = QHBoxLayout()
        console_title = QLabel("完整运行日志")
        console_title.setStyleSheet("font-size: 15px; font-weight: 800;")
        console_header.addWidget(console_title)
        console_header.addStretch(1)
        console_badge = QLabel("已接入原 CMD 输出")
        console_badge.setObjectName("consoleBadge")
        console_header.addWidget(console_badge)
        console_layout.addLayout(console_header)
        self.console_log = QTextEdit()
        self.console_log.setObjectName("consoleLog")
        self.console_log.setReadOnly(True)
        self.console_log.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self.console_log.document().setMaximumBlockCount(800)
        console_layout.addWidget(self.console_log, 1)
        detail_row.addWidget(console_card, 7)
        layout.addLayout(detail_row, 1)

        row = QHBoxLayout()
        self.progress_hint = QLabel("运行日志会同步保存在项目报告中")
        self.progress_hint.setObjectName("muted")
        row.addWidget(self.progress_hint)
        row.addStretch(1)
        self.cancel_run_button = AnimatedButton("安全取消")
        self.cancel_run_button.setObjectName("danger")
        self.cancel_run_button.clicked.connect(self._cancel_run)
        row.addWidget(self.cancel_run_button)
        layout.addLayout(row)

        self._active_stages = {}
        self._completed_stages = set()
        self._failed_stages = set()
        self._stage_total = 11
        self._current_media_index = 1
        self._current_media_total = max(1, len(self.media_paths))
        self._progress_timer = QTimer(self)
        # A precise 200 ms heartbeat makes the displayed integer second advance
        # reliably once per second even when the UI thread briefly handles a burst
        # of log events. A coarse 1000 ms timer can visibly jump by two seconds.
        self._progress_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._progress_timer.setInterval(200)
        self._progress_timer.timeout.connect(self._update_progress_clock)
        return page

    def _result_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 18, 28, 20)
        layout.setSpacing(11)
        summary_card = QFrame()
        summary_card.setObjectName("resultSummaryCard")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(18, 14, 18, 14)
        self.result_icon = QLabel()
        self.result_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_layout.addWidget(self.result_icon)
        self.result_title = QLabel("任务完成")
        self.result_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_title.setStyleSheet("font-size: 26px; font-weight: 800;")
        summary_layout.addWidget(self.result_title)
        self.result_summary = QLabel("")
        self.result_summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_summary.setObjectName("muted")
        summary_layout.addWidget(self.result_summary)
        layout.addWidget(summary_card)

        detail_row = QHBoxLayout()
        detail_row.setSpacing(11)
        files_card = QFrame()
        files_card.setObjectName("resultFilesCard")
        files_layout = QVBoxLayout(files_card)
        files_layout.setContentsMargins(13, 10, 13, 12)
        files_title = QLabel("任务与输出")
        files_title.setStyleSheet("font-size: 15px; font-weight: 800;")
        files_layout.addWidget(files_title)
        self.result_files = QTextEdit()
        self.result_files.setObjectName("resultFiles")
        self.result_files.setReadOnly(True)
        files_layout.addWidget(self.result_files, 1)
        detail_row.addWidget(files_card, 5)

        log_card = QFrame()
        log_card.setObjectName("resultLogCard")
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(13, 10, 13, 12)
        result_log_header = QHBoxLayout()
        result_log_title = QLabel("本次完整运行日志")
        result_log_title.setStyleSheet("font-size: 15px; font-weight: 800;")
        result_log_header.addWidget(result_log_title)
        result_log_header.addStretch(1)
        result_log_badge = QLabel("成功与失败均保留")
        result_log_badge.setObjectName("consoleBadge")
        result_log_header.addWidget(result_log_badge)
        log_layout.addLayout(result_log_header)
        self.result_console = QTextEdit()
        self.result_console.setObjectName("resultConsole")
        self.result_console.setReadOnly(True)
        self.result_console.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        log_layout.addWidget(self.result_console, 1)
        detail_row.addWidget(log_card, 7)
        layout.addLayout(detail_row, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        open_reports = AnimatedButton("打开报告目录")
        open_reports.setIcon(_icon("fa5s.folder-open"))
        open_reports.clicked.connect(lambda: os.startfile(str(Path(self.legacy.SCRIPT_DIR) / "reports")))
        close = AnimatedButton("完成")
        close.setObjectName("primary")
        close.clicked.connect(self.close)
        row.addWidget(open_reports)
        row.addWidget(close)
        row.addStretch(1)
        layout.addLayout(row)
        return page

    @staticmethod
    def _supported_paths(paths):
        accepted = []
        seen = set()
        for raw_path in paths or ():
            path = Path(str(raw_path)).expanduser()
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_MEDIA_SUFFIXES:
                continue
            resolved = str(path.resolve())
            identity = os.path.normcase(resolved)
            if identity not in seen:
                accepted.append(resolved)
                seen.add(identity)
        return accepted

    def _set_drop_active(self, active: bool):
        if not hasattr(self, "media_frame"):
            return
        self.media_frame.setProperty("dropActive", bool(active))
        self.media_frame.style().unpolish(self.media_frame)
        self.media_frame.style().polish(self.media_frame)
        if hasattr(self, "drop_overlay"):
            self.drop_overlay.set_active(bool(active))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "drop_overlay"):
            self.drop_overlay.setGeometry(self.rect().adjusted(16, 16, -16, -16))

    def _refresh_media_summary(self):
        ready = bool(self.media_paths)
        self.media_frame.setProperty("empty", not ready)
        self.media_frame.style().unpolish(self.media_frame)
        self.media_frame.style().polish(self.media_frame)
        if ready:
            preview = "、".join(Path(path).name for path in self.media_paths[:2])
            if len(self.media_paths) > 2:
                preview += f" 等 {len(self.media_paths)} 个文件"
            self.media_name.setText(preview)
            self.media_name.setToolTip("\n".join(self.media_paths))
            self.media_drop_hint.setText("可继续拖入另一批素材，或点击右侧重新选择")
            self.header_status.setText(f"●  {len(self.media_paths)} 个素材已就绪")
        else:
            self.media_name.setText("把视频或音频拖到这里")
            self.media_name.setToolTip("")
            self.media_drop_hint.setText("支持多选；也可以点击右侧“选择素材”")
            self.header_status.setText("●  等待素材")
        self.start_button.setEnabled(ready)

    def _choose_media(self):
        paths = _select_media_paths(self)
        if paths:
            self.media_paths = self._supported_paths(paths)
            self._refresh_media_summary()

    def dragEnterEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        accepted = self._supported_paths(paths)
        if accepted and not (self.worker and self.worker.isRunning()):
            event.acceptProposedAction()
            self.drop_overlay.set_file_count(len(accepted))
            self._set_drop_active(True)
            return
        event.ignore()

    def dragMoveEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        accepted = self._supported_paths(paths)
        if accepted and not (self.worker and self.worker.isRunning()):
            self.drop_overlay.set_file_count(len(accepted))
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drop_active(False)
        event.accept()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        accepted = self._supported_paths(paths)
        self._set_drop_active(False)
        if not accepted:
            event.ignore()
            return
        self.media_paths = accepted
        _remember_media_directory(accepted)
        self._refresh_media_summary()
        event.acceptProposedAction()

    def _auto_enable_terms(self, value: str):
        if self.legacy.clean_subtitle_text(value):
            self.terms.setChecked(True)

    def _refresh_ai_summary(self):
        polish = self.polish_editor.model.currentText().strip()
        group = self.group_editor.model.currentText().strip()
        if hasattr(self, "unified_glm") and self.unified_glm.isChecked():
            configured = int(bool(resolve_api_key("group")[0]))
            provider = self.group_editor.provider.currentText()
            summary = (
                f"统一模型：{provider} / {group}    |    {configured} 个密钥已配置"
                "    |    校对与断句共用项目内置提示词"
            )
        else:
            configured = int(bool(resolve_api_key("polish")[0])) + int(bool(resolve_api_key("group")[0]))
            summary = (
                f"字幕校对：{polish}    |    全文断句：{group}    |    "
                f"{configured} 个密钥已配置    |    项目内置提示词"
            )
        self.ai_panel.set_summary(summary)

    def _mark_ai_configuration_dirty(self, *_args):
        if not hasattr(self, "ai_save_status"):
            return
        self.ai_save_status.setObjectName("statusWarn")
        self.ai_save_status.setText("有未保存的 AI 配置修改")
        self.ai_save_status.style().unpolish(self.ai_save_status)
        self.ai_save_status.style().polish(self.ai_save_status)

    def _save_ai_configuration(self, *, show_feedback: bool, require_ready: bool = False) -> bool:
        try:
            result = persist_ai_configuration(
                self.legacy,
                self.polish_editor.values(),
                self.group_editor.values(),
                unified=self.unified_glm.isChecked(),
                share_key=self.share_key.isChecked(),
                require_ready=require_ready,
            )
        except Exception as exc:
            self.ai_panel.set_expanded(True)
            self.ai_save_status.setObjectName("statusWarn")
            self.ai_save_status.setText(f"保存失败：{exc}")
            self.ai_save_status.style().unpolish(self.ai_save_status)
            self.ai_save_status.style().polish(self.ai_save_status)
            if show_feedback:
                QMessageBox.warning(self, "AI 配置未保存", str(exc))
            return False
        self.polish_editor.key.clear()
        self.group_editor.key.clear()
        self.polish_editor.refresh_secret_status()
        self.group_editor.refresh_secret_status()
        self._refresh_ai_summary()
        missing = result["missing_keys"]
        self.ai_save_status.setObjectName("statusWarn" if missing else "statusGood")
        self.ai_save_status.setText(
            "配置已保存；运行前还需填写：" + "、".join(missing)
            if missing
            else "AI 配置与密钥已保存，重启后仍会保留"
        )
        self.ai_save_status.style().unpolish(self.ai_save_status)
        self.ai_save_status.style().polish(self.ai_save_status)
        return True

    def _apply_unified_glm_mode(self, checked: bool):
        unified = bool(checked)
        self.polish_editor.setVisible(not unified)
        self.share_key.setVisible(not unified)
        self.group_editor.title_label.setText(
            "●  统一校对与断句模型" if unified else "●  全文断句模型"
        )
        self.group_editor.setToolTip(
            "这一套模型、地址和密钥将同时用于字幕校对与全文断句。"
            if unified
            else "仅用于全文断句。"
        )
        self._refresh_ai_summary()

    def _add_custom_term(self):
        game_name = self.legacy.canonicalize_runtime_game_name(self.game_box.currentText())
        if not game_name:
            QMessageBox.information(self, "添加术语", "请先输入或选择游戏 / 内容名称。")
            return
        value = self.term_input.text().strip()
        if not value:
            return
        if self.legacy.add_learned_mapping(game_name, value, value):
            self.term_input.clear()
            self.term_hint.setText(f"已添加术语：{value}（可在“管理已学习术语”中删除）")
        else:
            QMessageBox.information(self, "添加术语", "该术语已存在或内容为空。")

    def _manage_terms(self):
        game_name = self.legacy.canonicalize_runtime_game_name(self.game_box.currentText())
        if not game_name:
            QMessageBox.information(self, "已学习术语", "请先输入或选择游戏 / 内容名称。")
            return
        mappings = self.legacy.learned_mappings_for_game(game_name)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"已学习术语｜{game_name}")
        dialog.resize(680, 480)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("●  已学习 / 手动添加的术语"))
        listing = QListWidget()
        listing.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        for item in mappings:
            marker = "已确认" if item.get("confirmed") else "联网核验"
            listing.addItem(f"{item.get('from')} → {item.get('to')}  [{marker}]")
        layout.addWidget(listing)
        # 内置图鉴词条（角色名 / 技能名等），按当前所选游戏读取
        saved_game = self.legacy.RUNTIME_GAME_NAME
        self.legacy.RUNTIME_GAME_NAME = game_name
        try:
            builtin_names, loaded = self.legacy.load_active_game_lexicon_names()
        finally:
            self.legacy.RUNTIME_GAME_NAME = saved_game
        if loaded:
            summary = "、".join(
                f"{label} {count} 条" for label, count, _ in loaded
            )
            layout.addWidget(QLabel(f"●  内置图鉴（{summary}）"))
            builtin = QListWidget()
            builtin.setSelectionMode(QListWidget.SelectionMode.NoSelection)
            for name in builtin_names[:300]:
                builtin.addItem(name)
            layout.addWidget(builtin)
        row = QHBoxLayout()
        remove = AnimatedButton("删除所选")
        close = AnimatedButton("关闭")
        row.addStretch(1)
        row.addWidget(remove)
        row.addWidget(close)
        layout.addLayout(row)

        def remove_selected():
            indexes = sorted({listing.row(item) for item in listing.selectedItems()}, reverse=True)
            keys = [(mappings[index]["from"], mappings[index]["to"]) for index in indexes]
            if self.legacy.delete_learned_mappings(game_name, keys):
                for index in indexes:
                    listing.takeItem(index)
                    mappings.pop(index)

        remove.clicked.connect(remove_selected)
        close.clicked.connect(dialog.accept)
        dialog.exec()

    def _start_run(self):
        if not self.media_paths:
            QMessageBox.information(self, "还没有素材", "请先拖入或选择视频 / 音频文件。")
            return
        if not self._save_ai_configuration(show_feedback=True, require_ready=True):
            return
        game_name = self.legacy.canonicalize_runtime_game_name(self.game_box.currentText())
        if game_name:
            self.legacy.save_runtime_game_history(game_name)
        options = RunOptions(
            content_name=game_name,
            enable_domain_terms=bool(game_name and self.terms.isChecked()),
            output_review_track=self.review_track.isChecked(),
            force_refresh_polish=self.refresh_polish.isChecked(),
            force_refresh_group=self.refresh_group.isChecked(),
            expected_speakers=(
                int(self.expected_speakers.currentText())
                if self.expected_speakers.currentText().isdigit()
                else 0
            ),
            overwrite_policy=str(self.overwrite.currentData()),
        )
        self.token = CancellationToken()
        self.worker = PipelineWorker(
            self.media_paths,
            options,
            self.token,
            self.legacy,
            self.pipeline,
            self.startup_self_test,
        )
        self.worker.event_received.connect(self._handle_event)
        self.worker.console_received.connect(self._append_console_line)
        self.worker.result_ready.connect(self._handle_result)
        self.worker.unexpected_error.connect(self._handle_unexpected_error)
        self.started_at = time.perf_counter()
        self._active_stages.clear()
        self._completed_stages.clear()
        self._failed_stages.clear()
        self.event_log.clear()
        self.console_log.clear()
        self.progress_bar.setValue(0)
        self.progress_percent.setText("0%")
        self.cancel_run_button.setEnabled(True)
        self._append_feed("准备", "配置已确认，正在建立任务队列", GREEN)
        self._progress_timer.start()
        self.workflow.set_active(0)
        self.pages.setCurrentIndex(1)
        self.worker.start()

    def _stage_group(self, stage_index: int) -> int:
        if stage_index <= 7:
            return 0
        if stage_index == 8:
            return 1
        if stage_index <= 10:
            return 2
        return 3

    def _append_feed(self, badge: str, message: str, color: str = MUTED):
        item = QListWidgetItem()
        card = TaskEventCard(str(badge), str(message), color)
        item.setSizeHint(QSize(0, max(50, card.sizeHint().height())))
        self.event_log.addItem(item)
        self.event_log.setItemWidget(item, card)
        while self.event_log.count() > 60:
            self.event_log.takeItem(0)
        self.event_log.scrollToBottom()
        # 运行期间新建的卡片也应用当前界面语言
        apply_ui_language(self, getattr(self, "_ui_language", "zh"))

    def _append_console_line(self, line: str, level: str = "stdout"):
        compact = str(line or "").rstrip()
        if not compact:
            return
        lowered = compact.lower()
        fatal_markers = (
            "traceback",
            "[文件失败]",
            "[阶段失败]",
            "已停止写入",
            "fatal error",
            "致命",
        )
        recoverable_markers = (
            "警告",
            "warning",
            "回退",
            "重试",
            "校对失败",
            "403",
            "forbidden",
        )
        if any(marker in lowered for marker in fatal_markers):
            color, background = "#ffb09d", "#47332e"
        elif any(marker in lowered for marker in recoverable_markers):
            color, background = "#f2c66d", "#3d392c"
        elif level == "stderr":
            color, background = "#c7d3c5", "#303530"
        elif "缓存命中" in compact or "缓存写入" in compact:
            color, background = "#a8d5ef", "#2f383b"
        elif "完成" in compact or "成功" in compact:
            color, background = "#a9d8a4", "#303a30"
        elif compact.startswith("[阶段") or compact.startswith("===="):
            color, background = "#f4e7bd", "#393832"
        else:
            color, background = "#edf0e9", "transparent"
        safe = html.escape(compact).replace(" ", "&nbsp;")
        self.console_log.append(
            f'<div style="color:{color}; background:{background}; margin:1px 0; '
            f'padding:2px 4px; white-space:pre;">{safe}</div>'
        )
        self.console_log.verticalScrollBar().setValue(
            self.console_log.verticalScrollBar().maximum()
        )

    def _refresh_progress_cards(self):
        phase_stages = (
            set(range(1, 8)),
            {8},
            {9, 10},
            {11},
        )
        active_ids = set(self._active_stages)
        for index, (card, ids) in enumerate(zip(self.phase_cards, phase_stages)):
            if ids & self._failed_stages:
                state = "failed"
            elif ids <= self._completed_stages:
                state = "done"
            elif ids & active_ids:
                state = "active"
            else:
                state = "pending"
            card.set_state(state)
        if active_ids:
            focus_id = max(active_ids)
            focus = self._active_stages[focus_id]
            self.progress_stage.setText(focus["label"])
            self.progress_resource.setText(focus["resource"])
            rows = [
                f'{item["label"]}  ·  {item["resource"]}'
                for _, item in sorted(self._active_stages.items())
            ]
            prefix = "并行运行中" if len(rows) > 1 else "运行中"
            self.active_tasks_label.setText(prefix + "\n" + "\n".join(rows))
            self.running_indicator.set_running(True)
            self.workflow.set_active(self._stage_group(focus_id))
        elif self._completed_stages:
            last_id = max(self._completed_stages)
            self.progress_stage.setText("正在衔接下一阶段")
            self.progress_resource.setText(f"阶段 {last_id} 已完成，正在准备后续资源")
            self.active_tasks_label.setText("当前没有并行子任务，正在进行阶段切换")
            self.running_indicator.set_running(False)
        else:
            self.running_indicator.set_running(False)
        apply_ui_language(self, getattr(self, "_ui_language", "zh"))

        total_stages = max(1, self._stage_total)
        finished = len(self._completed_stages)
        media_total = max(1, self._current_media_total)
        media_index = max(1, self._current_media_index)
        fraction = ((media_index - 1) + finished / total_stages) / media_total
        value = max(0, min(1000, int(round(fraction * 1000))))
        if self.progress_bar.value() != value:
            self._progress_motion.stop()
            self._progress_motion.setStartValue(self.progress_bar.value())
            self._progress_motion.setEndValue(value)
            self._progress_motion.start()
        self.progress_percent.setText(f"{round(value / 10):.0f}%")
        self.progress_context.setText(
            f"素材 {media_index} / {media_total}  ·  已完成 {finished} / {total_stages} 个阶段"
        )

    def _update_progress_clock(self):
        if not self.started_at:
            return
        elapsed = max(0, int(time.perf_counter() - self.started_at))
        minutes, seconds = divmod(elapsed, 60)
        self.stage_elapsed.setText(f"{minutes:02d}:{seconds:02d}")

    def _handle_event(self, event):
        if event.kind == "stage_started":
            self._stage_total = max(1, event.stage_total)
            self._current_media_index = max(1, event.media_index)
            self._current_media_total = max(1, event.media_total)
            self._active_stages[event.stage_index] = {
                "label": event.label,
                "resource": event.resource,
                "started": time.perf_counter(),
            }
            self._append_feed("开始", f"{event.label} · {event.resource}", self.phase_cards[self._stage_group(event.stage_index)].accent)
        elif event.kind == "stage_completed":
            self._active_stages.pop(event.stage_index, None)
            self._completed_stages.add(event.stage_index)
            self._append_feed("完成", f"{event.label} · {event.elapsed_seconds:.1f} 秒", GREEN)
        elif event.kind in {"stage_failed", "media_failed"}:
            if event.stage_index:
                self._active_stages.pop(event.stage_index, None)
                self._failed_stages.add(event.stage_index)
            self._append_feed("失败", f"{event.label or Path(event.media_path).name} · {event.error}", CORAL)
        elif event.kind == "cache_hit":
            stage = event.payload.get("stage", "")
            self._append_feed("缓存", f"复用 {stage}，跳过重复计算", BLUE)
        elif event.kind == "cloud_batches_parallel":
            self._append_feed(
                "并行",
                f"{event.payload.get('batches', 0)} 个云端批次，最多 {event.payload.get('workers', 1)} 路",
                PURPLE,
            )
        elif event.kind == "cloud_batch_completed":
            self._append_feed(
                "批次",
                f"{event.payload.get('batch_index', 0)} / {event.payload.get('batch_total', 0)} 完成 · {event.elapsed_seconds:.1f} 秒",
                BLUE,
            )
        elif event.kind == "final_text_conservation_recovery":
            self._append_feed(
                "自愈",
                "检测到断句调序，已从校对源段安全重建并重新校验",
                GREEN,
            )
        elif event.kind == "media_completed":
            self._append_feed("素材", f"已完成 {Path(event.media_path).name}", GREEN)
        self._refresh_progress_cards()

    def _cancel_run(self):
        if self.token:
            self.token.cancel()
            self.cancel_run_button.setEnabled(False)
            self.progress_stage.setText("正在安全取消…")
            self.progress_resource.setText("将在当前可安全停止的阶段边界退出")
            self._append_feed("取消", "已发出安全取消请求，正在等待当前阶段收尾", AMBER)

    def _show_task_notification(self, title, message, icon, details=""):
        """Raise a modal completion alert even when the workbench is minimized."""
        previous = self._completion_dialog
        if previous is not None:
            previous.close()
        QApplication.beep()
        QApplication.alert(self, 0)
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

        dialog = CompletionDialog(title, message, icon, details, self)
        self._completion_dialog = dialog

        def clear_dialog(_result):
            if self._completion_dialog is dialog:
                self._completion_dialog = None

        dialog.finished.connect(clear_dialog)
        dialog.open()

    def _handle_result(self, result):
        self._progress_timer.stop()
        self.result_exit_code = result.exit_code
        self.progress_bar.setValue(1000)
        self.workflow.set_active(3, finished=True)
        success_count = len(result.successes)
        failure_count = len(result.failures)
        cancel_count = len(result.cancelled)
        if failure_count:
            color, icon_name, title = CORAL, "fa5s.exclamation-circle", "部分任务失败"
        elif cancel_count:
            color, icon_name, title = AMBER, "fa5s.stop-circle", "任务已取消"
        else:
            color, icon_name, title = GREEN, "fa5s.check-circle", "字幕生成完成"
        self.result_icon.setPixmap(_icon(icon_name, color).pixmap(QSize(72, 72)))
        self.result_title.setText(title)
        self.result_summary.setText(
            f"成功 {success_count} 个 · 失败 {failure_count} 个 · 取消 {cancel_count} 个 · 总耗时 {result.elapsed_seconds:.1f} 秒"
        )
        rows = []
        for item in result.results:
            status_spec = {
                "success": ("完成", GREEN, "#edf5e9"),
                "failed": ("失败", CORAL, "#fff0eb"),
                "cancelled": ("取消", AMBER, "#fff5df"),
                "skipped": ("跳过", BLUE, "#eaf4f8"),
            }.get(item.status, (item.status, MUTED, "#f1eee8"))
            status_text, status_color, background = status_spec
            details = []
            if item.srt_path:
                details.append(f"字幕：{html.escape(item.srt_path)}")
            if item.report_text_path:
                details.append(f"报告：{html.escape(item.report_text_path)}")
            if item.error:
                details.append(f"原因：{html.escape(item.error)}")
            detail_html = "<br>".join(details) or "没有额外输出信息"
            rows.append(
                f'<div style="background:{background}; border-left:4px solid {status_color}; '
                f'margin:4px 0 10px 0; padding:9px 11px; border-radius:7px;">'
                f'<span style="color:{status_color}; font-weight:800;">{html.escape(status_text)}</span>'
                f'<span style="font-weight:700; color:{INK};">&nbsp;&nbsp;{html.escape(Path(item.media_path).name)}</span>'
                f'<div style="color:{MUTED}; margin-top:5px; line-height:1.55;">{detail_html}</div>'
                "</div>"
            )
        self.result_files.setHtml("".join(rows))
        self.result_console.setHtml(self.console_log.toHtml())
        self.pages.setCurrentIndex(2)
        self._show_task_notification(*_completion_notification_spec(result))

    def _handle_unexpected_error(self, message: str):
        self._progress_timer.stop()
        self.result_icon.setPixmap(_icon("fa5s.exclamation-circle", CORAL).pixmap(QSize(72, 72)))
        self.result_title.setText("任务未能启动")
        self.result_summary.setText(message)
        self.result_files.setHtml(
            f'<div style="background:#fff0eb; border-left:4px solid {CORAL}; '
            f'padding:10px; border-radius:7px;"><b>启动失败</b><br>{html.escape(message)}</div>'
        )
        self.result_console.setHtml(self.console_log.toHtml())
        self.pages.setCurrentIndex(2)
        apply_ui_language(self, getattr(self, "_ui_language", "zh"))
        self._show_task_notification(
            "字幕任务异常中止",
            "任务未能正常完成，请查看结果页和运行日志。",
            QMessageBox.Icon.Critical,
            message,
        )

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            answer = QMessageBox.question(
                self,
                "任务仍在运行",
                "要安全取消当前任务并关闭窗口吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.token.cancel()
            event.ignore()
            self.worker.finished.connect(self.close)
            return
        event.accept()


def _media_dialog_initial_directory(settings=None):
    settings = settings or QSettings("2ByteASR", "2ByteASR")
    remembered = str(settings.value(LAST_MEDIA_DIRECTORY_KEY, "") or "").strip()
    if remembered and Path(remembered).is_dir():
        return str(Path(remembered).resolve())
    desktop = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DesktopLocation
    )
    if desktop and Path(desktop).is_dir():
        return str(Path(desktop).resolve())
    fallback = Path.home() / "Desktop"
    return str(fallback if fallback.is_dir() else Path.home())


def _remember_media_directory(paths, settings=None):
    if not paths:
        return
    directory = Path(paths[0]).expanduser().resolve().parent
    if not directory.is_dir():
        return
    settings = settings or QSettings("2ByteASR", "2ByteASR")
    settings.setValue(LAST_MEDIA_DIRECTORY_KEY, str(directory))
    settings.sync()


def _select_media_paths(parent=None, settings=None):
    settings = settings or QSettings("2ByteASR", "2ByteASR")
    paths, _ = QFileDialog.getOpenFileNames(
        parent,
        "请选择一个或多个原视频 / 音频文件",
        _media_dialog_initial_directory(settings),
        "视频 / 音频 (*.mp4 *.mov *.mkv *.webm *.mp3 *.wav *.m4a *.flac *.aac)",
    )
    _remember_media_directory(paths, settings)
    return list(paths)


def run_desktop_app(
    legacy,
    pipeline,
    startup_self_test,
    *,
    select_media: bool = True,
    initial_paths=(),
) -> int:
    _configure_windows_app_identity()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("2ByteASR")
    app.setApplicationDisplayName("2ByteASR")
    app.setWindowIcon(_app_icon())
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    app_font = QFont("Microsoft YaHei UI", 9)
    app_font.setFamilies(["Microsoft YaHei UI", "Segoe UI", "Yu Gothic UI", "PingFang SC"])
    app.setFont(app_font)
    media_paths = MainWindow._supported_paths(initial_paths)
    if select_media and not media_paths:
        media_paths = _select_media_paths()
        if not media_paths:
            return 0
    window = MainWindow(media_paths, legacy, pipeline, startup_self_test)
    window.show()
    app.exec()
    return int(window.result_exit_code)


def _preview(screenshot_path: str, state: str = "settings") -> int:
    import moss_firered_pipeline
    import subtitle_core

    _configure_windows_app_identity()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("2ByteASR")
    app.setWindowIcon(_app_icon())
    app.setStyle("Fusion")
    app.setStyleSheet(APP_QSS)
    app_font = QFont("Microsoft YaHei UI", 9)
    app_font.setFamilies(["Microsoft YaHei UI", "Segoe UI", "Yu Gothic UI", "PingFang SC"])
    app.setFont(app_font)
    preview_media = [] if state == "empty" else [
        r"F:\直播回放\舰礼有等身抱枕～代刮刮刮乐～_vocal.wav"
    ]
    window = MainWindow(
        preview_media,
        subtitle_core,
        moss_firered_pipeline,
        {"id": "preview", "checks": 0},
    )
    if preview_media:
        window.game_box.setCurrentText("舰礼有等身抱枕～代刮刮刮乐～")
    show_workflow_after_show = state == "workflow"
    if state == "ai":
        window.ai_panel.set_expanded(True, animate=False)
    elif state == "progress":
        window.pages.setCurrentIndex(1)
        window.started_at = time.perf_counter() - 89
        for stage_index in range(1, 8):
            window._completed_stages.add(stage_index)
        window._active_stages[8] = {
            "label": "云端模型受限校对",
            "resource": "OpenAI 兼容 API + 本地安全裁决",
            "started": time.perf_counter(),
        }
        window._append_feed("完成", "本地识别与说话人筛选 · 40.5 秒", GREEN)
        window._append_feed("并行", "3 个字幕校对批次正在运行", PURPLE)
        window._append_feed("自愈", "异常断句会回退源段重建并重新校验", GREEN)
        window._append_console_line("[阶段 8/11] 云端模型受限校对（OpenAI 兼容 API+本地安全裁决）")
        window._append_console_line("   [并行加速] 3 个校对批次，最多 4 路并发。")
        window._append_console_line("   校对批次 1/3")
        window._append_console_line("   [缓存命中] polished_batch，复用已完成批次。")
        window._refresh_progress_cards()
        window._progress_motion.setCurrentTime(window._progress_motion.duration())
        window.phase_cards[1]._pulse.setCurrentTime(
            window.phase_cards[1]._pulse.duration() // 2
        )
        window._update_progress_clock()
    elif state == "result":
        window.pages.setCurrentIndex(2)
        window.workflow.set_active(3, finished=True)
        window.result_icon.setPixmap(_icon("fa5s.check-circle", GREEN).pixmap(QSize(72, 72)))
        window.result_title.setText("字幕生成完成")
        window.result_summary.setText("成功 1 个 · 失败 0 个 · 取消 0 个 · 总耗时 168.4 秒")
        window.result_files.setHtml(
            f'<div style="background:#edf5e9; border-left:4px solid {GREEN}; '
            f'padding:10px; border-radius:7px;"><b style="color:{GREEN};">完成</b>'
            "&nbsp;&nbsp;<b>示例素材.wav</b><br>字幕：桌面\\示例素材_剪映文稿.srt"
            "<br>报告：项目\\reports\\示例素材_字幕任务报告.txt</div>"
        )
        window._append_console_line("[完成] 断句：35 条，中位 5 字/1.22 秒。")
        window._append_console_line("[阶段 11/11] 写入剪映文稿、总SRT与分轨SRT（磁盘）")
        window._append_console_line("[文件完成 1/1] 168.4秒")
        window.result_console.setHtml(window.console_log.toHtml())
    window.show()
    app.processEvents()
    if state == "drop":
        window.drop_overlay.set_file_count(2)
        window._set_drop_active(True)
        window.drop_overlay.animation.setCurrentTime(window.drop_overlay.animation.duration())
        app.processEvents()
    if show_workflow_after_show:
        window.show_workflow_popover()
        window._workflow_animation.setCurrentTime(window._workflow_animation.duration())
        app.processEvents()
    target = Path(screenshot_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ok = window.grab().save(str(target), "PNG")
    window.close()
    return 0 if ok else 1


if __name__ == "__main__":
    if len(sys.argv) in {3, 4} and sys.argv[1] == "--screenshot":
        raise SystemExit(_preview(sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else "settings"))
    raise SystemExit("请通过 2ByteASR.bat 启动 2ByteASR。")
