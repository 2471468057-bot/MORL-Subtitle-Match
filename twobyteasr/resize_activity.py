# -*- coding: utf-8 -*-
"""窗口缩放活跃期标记（live-resize guard）。

用户快速拖拽窗口边缘时，Qt 会连续派发大量 resize + paint。时间轴每次重绘都要
重建波形包络贴片（``_waveform_envelope_tiles``，按 ms_per_px 做缓存键，缩放中
每帧都 miss），视频轨还要解缩略图——这些活会在拖拽过程中堆积成卡顿。

这里提供一个全局标记：任何 resizeEvent 调 ``mark()``，``active()`` 在最后一次
resize 之后 ``settle_ms`` 内返回 True。重绘路径据此跳过"贵但可以稍后补"的工作，
等风暴停下来（``settled`` 回调）再完整画一遍。

纯 GUI 线程使用，不做跨线程共享。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer


class ResizeActivity(QObject):
    """Tracks whether the top-level window is being resized right now."""

    def __init__(self, settle_ms: int = 250, parent=None) -> None:
        super().__init__(parent)
        self._settle_ms = max(60, int(settle_ms))
        self._active = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self._settle_ms)
        self._timer.timeout.connect(self._on_settled)
        self._callbacks: list = []

    # ------------------------------------------------------------------ 状态

    def active(self) -> bool:
        return self._active

    def mark(self) -> None:
        """Call from any resizeEvent; keeps the guard active until things settle."""
        self._active = True
        self._timer.start()

    def on_settled(self, callback) -> None:
        """Register a one-shot-per-storm callback used to repaint fully.

        同一个回调只登记一次（含绑定方法）。注意：不要传临时 lambda——每次都是
        新对象，去重失效后会堆积，settle 时全部执行又触发新 resize，形成放大
        循环（这就是"卡卡的巨慢"的成因之一）。
        """
        for existing in self._callbacks:
            if existing == callback:
                return
            # 绑定方法每次访问都会产生新对象，但底层 self/func 相同。
            if (getattr(existing, "__self__", None) is getattr(callback, "__self__", object())
                    and getattr(existing, "__func__", None) is getattr(callback, "__func__", None)):
                return
        self._callbacks.append(callback)

    def _on_settled(self) -> None:
        self._active = False
        pending, self._callbacks = self._callbacks, []
        for callback in pending:
            try:
                callback()
            except Exception:  # noqa: BLE001 - 重绘失败绝不能影响交互
                pass


_GLOBAL: ResizeActivity | None = None


def resize_activity() -> ResizeActivity:
    """Process-wide instance (created lazily on the GUI thread)."""
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = ResizeActivity()
    return _GLOBAL


def resizing() -> bool:
    return _GLOBAL is not None and _GLOBAL.active()


def mark_resize() -> None:
    resize_activity().mark()
