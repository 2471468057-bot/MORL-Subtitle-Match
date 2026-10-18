"""Embedded Export Workspace 2.1 for subtitle-burned video delivery."""

from __future__ import annotations

import json
import re
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import os
from .typography import TITLE_FONT_STACK
from .design.tokens import WEIGHT_SCALE
from .design.presentation import button_role, field_width

from .i18n import current_language, bind_text

from .i18n import tr

_ASSETS_ROOT = Path(__file__).resolve().parents[1] / "assets"
_EXPORT_CHECK_ICON = (_ASSETS_ROOT / "check-dark.png").as_posix()
_EXPORT_DOT_ICON = (_ASSETS_ROOT / "dot-dark.png").as_posix()

from PySide6.QtCore import QSettings, QUrl, Qt, Signal, QTimer, QSize, QRectF
from PySide6.QtGui import QColor, QDesktopServices, QKeySequence, QMouseEvent, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QGridLayout, QLineEdit, QMenu, QPushButton, QProgressBar, QScrollArea, QSizePolicy, QSlider,
    QRadioButton, QSpinBox, QSplitter, QStackedWidget, QTextEdit, QToolButton, QVBoxLayout,
    QWidget,
)

from .studio_project import SubtitleProject
from .platform_media import ffmpeg_tool


def _workspace_theme() -> ThemeDefinition:
    return theme_definition(theme_key())


def _directory_is_writable(path: Path) -> bool:
    target = Path(path).expanduser()
    if target.exists():
        return target.is_dir() and os.access(target, os.W_OK)
    parent = target.parent
    while parent != parent.parent and not parent.exists():
        parent = parent.parent
    return parent.is_dir() and os.access(parent, os.W_OK)


def resolve_subtitle_export_destination(
    project: SubtitleProject,
    project_path: Path | None,
    mode: str,
    custom_directory: str = "",
) -> tuple[Path, str]:
    """Resolve ordinary-user subtitle delivery with a safe project fallback."""

    source_directory = Path(project.media.path).expanduser().parent
    project_exports = (
        Path(project_path).expanduser().parent / "exports"
        if project_path is not None
        else source_directory / "exports"
    )
    normalized = str(mode or "source")
    if normalized == "custom":
        custom = Path(str(custom_directory or "").strip()).expanduser()
        if not str(custom_directory or "").strip():
            raise ValueError("请先选择自定义字幕保存文件夹")
        if not _directory_is_writable(custom):
            raise PermissionError(f"自定义字幕目录不可写：{custom}")
        return custom, "自定义位置"
    if normalized == "project":
        return project_exports, "工程 exports 目录"
    if _directory_is_writable(source_directory):
        return source_directory, "与源媒体同目录"
    return project_exports, "源媒体目录不可写，已改用工程 exports 目录"


@dataclass(frozen=True)
class ExportTarget:
    directory: Path
    base_name: str
    extension: str = "mp4"

    @property
    def full_path(self) -> Path:
        extension = self.extension.lstrip(".") or "mp4"
        base_name = self.base_name.strip()
        return self.directory / (base_name if base_name.lower().endswith(f".{extension.lower()}") else f"{base_name}.{extension}")


class SubtitleExportDialog(QDialog):
    """Focused subtitle-only export dialog used by the Studio toolbar."""

    def __init__(self, project: SubtitleProject, project_path: str | Path | None = None, parent=None):
        super().__init__(parent)
        self.project = project
        self.project_path = Path(project_path).resolve() if project_path else None
        self._settings = QSettings("2ByteASR", "2ByteASR")
        bind_text(self, '导出字幕', property='windowTitle')
        self.setMinimumWidth(560)
        self.setObjectName("subtitleExportDialog")
        apply_secondary_surface_theme(self)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(12)
        title = QLabel("导出字幕")
        title.setObjectName("sectionTitle")
        root.addWidget(title)
        subtitle = QLabel("选择格式、说话人拆分方式和保存位置；导出后会自动回读验证。")
        subtitle.setObjectName("cardMeta")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        formats = QGroupBox("格式")
        format_layout = QHBoxLayout(formats)
        self.format_checks: dict[str, StyledCheckBox] = {}
        saved_formats = str(self._settings.value("subtitle/export_formats", "srt") or "srt").split(",")
        for label, name in (("SRT", "srt"), ("ASS", "ass"), ("TXT", "txt"), ("JSON", "json")):
            box = StyledCheckBox(label)
            box.setChecked(name in saved_formats)
            self.format_checks[name] = box
            format_layout.addWidget(box)
        format_layout.addStretch(1)
        root.addWidget(formats)

        speakers = QGroupBox("说话人")
        speaker_layout = QHBoxLayout(speakers)
        self.speaker_modes: dict[str, StyledRadio] = {}
        saved_speaker = str(self._settings.value("subtitle/export_speaker_mode", "combined") or "combined")
        for label, mode in (("合并", "combined"), ("分别导出", "per_speaker"), ("两者", "both")):
            radio = StyledRadio(label)
            radio.setChecked(mode == saved_speaker)
            self.speaker_modes[mode] = radio
            speaker_layout.addWidget(radio)
        speaker_layout.addStretch(1)
        root.addWidget(speakers)

        destination = QGroupBox("保存位置")
        destination_layout = QVBoxLayout(destination)
        self.destination_modes: dict[str, StyledRadio] = {}
        saved_destination = str(self._settings.value("subtitle/export_destination", "source") or "source")
        for label, mode in (("与源媒体同目录", "source"), ("工程 exports", "project"), ("自定义位置", "custom")):
            radio = StyledRadio(label)
            radio.setChecked(mode == saved_destination)
            radio.toggled.connect(lambda checked, selected=mode: self._destination_changed(selected if checked else ""))
            self.destination_modes[mode] = radio
            destination_layout.addWidget(radio)
        custom_row = QHBoxLayout()
        self.custom_directory = QLineEdit(str(self._settings.value("subtitle/custom_directory", "") or ""))
        self.custom_directory.setReadOnly(True)
        bind_text(self.custom_directory, '选择自定义文件夹', property='placeholderText')
        choose = QPushButton("选择文件夹")
        choose.clicked.connect(self._choose_custom_directory)
        custom_row.addWidget(self.custom_directory, 1)
        custom_row.addWidget(choose)
        destination_layout.addLayout(custom_row)
        self.destination_status = QLabel()
        self.destination_status.setObjectName("cardMeta")
        self.destination_status.setWordWrap(True)
        destination_layout.addWidget(self.destination_status)
        root.addWidget(destination)

        self.warning = QLabel()
        self.warning.setObjectName("checkWarning")
        self.warning.setWordWrap(True)
        self.warning.hide()
        root.addWidget(self.warning)
        footer = QHBoxLayout()
        footer.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("studioButton")
        cancel.clicked.connect(self.reject)
        export = QPushButton("导出字幕")
        export.setObjectName("studioPrimary")
        export.clicked.connect(self._accept)
        footer.addWidget(cancel)
        footer.addWidget(export)
        root.addLayout(footer)
        self._destination_changed(saved_destination, persist=False)

    def _selected_destination(self) -> str:
        return next((mode for mode, radio in self.destination_modes.items() if radio.isChecked()), "source")

    def _destination_changed(self, mode: str, *, persist: bool = True) -> None:
        if not mode:
            return
        if persist:
            self._settings.setValue("subtitle/export_destination", mode)
        try:
            destination, reason = resolve_subtitle_export_destination(
                self.project, self.project_path, mode, self.custom_directory.text()
            )
            self.destination_status.setText(f"{reason} · {destination}")
        except (ValueError, PermissionError) as exc:
            self.destination_status.setText(str(exc))

    def _choose_custom_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr('选择字幕保存文件夹'), self.custom_directory.text() or str(Path(self.project.media.path).parent))
        if path:
            self.custom_directory.setText(path)
            self._settings.setValue("subtitle/custom_directory", path)
            self.destination_modes["custom"].setChecked(True)
            self._destination_changed("custom")

    def _accept(self) -> None:
        if not any(box.isChecked() for box in self.format_checks.values()):
            bind_text(self.warning, '至少选择一种字幕格式')
            self.warning.show()
            return
        try:
            resolve_subtitle_export_destination(self.project, self.project_path, self._selected_destination(), self.custom_directory.text())
        except (ValueError, PermissionError) as exc:
            self.warning.setText(str(exc))
            self.warning.show()
            return
        self._settings.setValue("subtitle/export_formats", ",".join(name for name, box in self.format_checks.items() if box.isChecked()))
        self._settings.setValue("subtitle/export_speaker_mode", self.selected_speaker_mode())
        self.accept()

    def selected_speaker_mode(self) -> str:
        return next((mode for mode, radio in self.speaker_modes.items() if radio.isChecked()), "combined")

    def selected_options(self) -> SubtitleExportOptions:
        return SubtitleExportOptions(
            frozenset(name for name, box in self.format_checks.items() if box.isChecked()),
            self.selected_speaker_mode(),
        )

    def selected_destination(self) -> tuple[Path, str]:
        return resolve_subtitle_export_destination(self.project, self.project_path, self._selected_destination(), self.custom_directory.text())


