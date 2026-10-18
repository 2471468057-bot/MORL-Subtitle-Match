"""Shared logical-pixel geometry for Subtitle Studio's ASS preview overlay."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF


@dataclass(frozen=True)
class SubtitleCoordinateMapper:
    """Map ASS PlayRes coordinates to a letterboxed Qt viewport.

    All preview values are Qt logical pixels. Device-pixel conversion belongs
    to mpv/Qt's native rendering boundary and must not leak into overlay input.
    """

    viewport_rect: QRectF
    play_res_x: int = 1920
    play_res_y: int = 1080
    video_width: int = 1920
    video_height: int = 1080

    @property
    def video_content_rect(self) -> QRectF:
        viewport = QRectF(self.viewport_rect)
        if viewport.width() <= 0 or viewport.height() <= 0:
            return viewport
        # 2026-10-18（用户："达芬奇里是竖屏，这里变成横屏了"）：画面框必须按
        # **工程画幅（play_res = 达芬奇时间线分辨率）** 定比例，而不是按素材的
        # 显示比例。竖屏时间线 + 横屏素材（1080x1920 画幅 / 1920x1080 素材）时，
        # 用素材比例会把字幕映射到一个横着的框里，位置与大小全错。
        target_aspect = max(1, int(self.play_res_x)) / max(1, int(self.play_res_y))
        viewport_aspect = viewport.width() / viewport.height()
        if viewport_aspect > target_aspect:
            height = viewport.height()
            width = height * target_aspect
            return QRectF(
                viewport.left() + (viewport.width() - width) / 2.0,
                viewport.top(),
                width,
                height,
            )
        width = viewport.width()
        height = width / target_aspect
        return QRectF(
            viewport.left(),
            viewport.top() + (viewport.height() - height) / 2.0,
            width,
            height,
        )

    @property
    def scale_x(self) -> float:
        return self.video_content_rect.width() / max(1, int(self.play_res_x))

    @property
    def scale_y(self) -> float:
        return self.video_content_rect.height() / max(1, int(self.play_res_y))

    def subtitle_to_preview(self, point: QPointF) -> QPointF:
        content = self.video_content_rect
        return QPointF(
            content.left() + point.x() * self.scale_x,
            content.top() + point.y() * self.scale_y,
        )

    def preview_to_subtitle(self, point: QPointF) -> QPointF:
        content = self.video_content_rect
        return QPointF(
            (point.x() - content.left()) / max(self.scale_x, 1e-12),
            (point.y() - content.top()) / max(self.scale_y, 1e-12),
        )

    def preview_delta_to_subtitle(self, delta: QPointF) -> QPointF:
        return QPointF(
            delta.x() / max(self.scale_x, 1e-12),
            delta.y() / max(self.scale_y, 1e-12),
        )

    def subtitle_rect_to_preview(self, rect: QRectF) -> QRectF:
        top_left = self.subtitle_to_preview(rect.topLeft())
        bottom_right = self.subtitle_to_preview(rect.bottomRight())
        return QRectF(top_left, bottom_right).normalized()
