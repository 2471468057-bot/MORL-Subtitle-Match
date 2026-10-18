# -*- coding: utf-8 -*-
"""达芬奇实时跟随（达芬奇 → 2ByteASR）。

插件的 resolve-worker/main.js 会在协作目录里持续写 ``live.json``：

    { "playhead_ms": 12345, "timeline_rev": 7, "reload": true, "connected": true }

本模块只做两件事，都只在「当前工程来自达芬奇时间线」时生效：

1. 播放头跟随：达芬奇的播放头移动时，编辑器跟着跳（本地正在播放时不抢）。
2. 内容跟随：``timeline_rev`` 变化且 ``reload`` 为真时，从
   ``timeline.2byteproj`` 重新载入字幕，原地替换 cue 列表。

设计约束：

* 只用 QTimer 轮询一个小文件，不引入线程；读文件失败一律静默忽略，
  实时链路绝不能影响编辑器的稳定性。
* 原地替换 cue（同一个 project 对象）而不是重新打开工程，避免弹进度窗、
  重置撤销栈和播放头。
* 不调用 ``page._changed()``：跟随进来的内容不应该让自己变脏，否则会触发
  自动保存 → 又写回达芬奇，形成回环。
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer

# 只有达芬奇临时工程带这个 project_id，用它判断"是否处于协同模式"。
BRIDGE_PROJECT_ID = "davinci-timeline"
LIVE_FILENAME = "live.json"
PROJECT_FILENAME = "timeline.2byteproj"
DEFAULT_INTERVAL_MS = 250
# 播放头差异小于这个值就不动，免得每帧都触发一次寻址。
PLAYHEAD_EPSILON_MS = 60


class DavinciLiveLink:
    """轮询 ``live.json`` 并驱动编辑器跟随达芬奇时间线。"""

    def __init__(self, page, *, interval_ms: int = DEFAULT_INTERVAL_MS) -> None:
        self.page = page
        self._interval_ms = max(60, int(interval_ms))
        self._timer = QTimer(page)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._tick)
        self._last_rev = None
        self._last_acted_playhead_ms = None
        self._bridge_dir = self._resolve_bridge_dir()
        self._reloading = False

    # ------------------------------------------------------------------ 生命周期

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    # ------------------------------------------------------------------ 内部

    @staticmethod
    def _resolve_bridge_dir() -> Path | None:
        try:
            from .runtime_paths import user_data_root

            return Path(user_data_root()) / "bridge"
        except Exception:  # noqa: BLE001 - 路径不可用时整体降级为不跟随
            return None

    def _in_bridge_mode(self) -> bool:
        project = getattr(self.page, "project", None)
        if project is None:
            return False
        return str(getattr(project, "project_id", "") or "") == BRIDGE_PROJECT_ID

    def _read_live(self) -> dict | None:
        if self._bridge_dir is None:
            return None
        path = self._bridge_dir / LIVE_FILENAME
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def _tick(self) -> None:
        try:
            if not self._in_bridge_mode():
                return
            if self._reloading:
                return
            payload = self._read_live()
            if payload is None:
                return
            if not payload.get("connected", True):
                return
            self._handle_revision(payload)
            self._handle_playhead(payload)
        except Exception:  # noqa: BLE001 - 跟随失败绝不能影响编辑器
            pass

    # ------------------------------------------------------------------ 内容跟随

    def _handle_revision(self, payload: dict) -> None:
        rev = payload.get("timeline_rev")
        if rev is None:
            return
        if self._last_rev is None:
            self._last_rev = rev
            return
        if rev == self._last_rev:
            return
        self._last_rev = rev
        if not payload.get("reload"):
            return
        self._reload_cues()

    def _reload_cues(self) -> None:
        """原地替换 cue 列表：同一个 project 对象，撤销栈与播放头都不动。"""
        if self._bridge_dir is None:
            return
        path = self._bridge_dir / PROJECT_FILENAME
        if not path.exists():
            return
        page = self.page
        project = getattr(page, "project", None)
        if project is None:
            return
        self._reloading = True
        try:
            from .studio_project import load_project

            fresh = load_project(path)
            fresh_cues = list(getattr(fresh, "cues", []) or [])
            if not fresh_cues:
                return
            # 同一个对象：studio_timeline.set_project 只有在 project 变了时才
            # 会重置播放头/选区，传同一个对象可保留用户的当前定位。
            project.cues = fresh_cues
            playhead = int(getattr(page.timeline, "playhead_ms", 0) or 0)

            timeline = getattr(page, "timeline", None)
            if timeline is not None:
                if hasattr(timeline, "set_project"):
                    timeline.set_project(project)
                elif hasattr(timeline, "_rebuild_cue_index"):
                    timeline._rebuild_cue_index()
                if hasattr(timeline, "set_playhead"):
                    timeline.set_playhead(playhead)
                timeline.update()

            cue_model = getattr(page, "cue_model", None)
            if cue_model is not None:
                if hasattr(cue_model, "refresh"):
                    cue_model.refresh()
                elif hasattr(cue_model, "set_project"):
                    cue_model.set_project(project)

            summary = getattr(page, "_refresh_cue_list_summary", None)
            if callable(summary):
                summary()
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._reloading = False

    # ------------------------------------------------------------------ 播放头跟随

    def _handle_playhead(self, payload: dict) -> None:
        ms = payload.get("playhead_ms")
        if not isinstance(ms, (int, float)) or ms < 0:
            return
        ms = int(ms)
        # 比较"上次真正执行过的位置"，而不是相邻两次文件内容：插件只在播放头
        # 移动时才重写文件，只比较文件变化会漏掉第一帧与静止后的首次推送。
        if (
            self._last_acted_playhead_ms is not None
            and abs(ms - self._last_acted_playhead_ms) < PLAYHEAD_EPSILON_MS
        ):
            return

        page = self.page
        # 本地正在播放或正在编辑时不抢播放头：用户此刻在编辑器里操作。
        video = getattr(page, "video", None)
        if video is not None and not bool(getattr(video, "_paused", True)):
            return
        if self._editing_has_focus():
            return
        current = int(getattr(getattr(page, "timeline", None), "playhead_ms", 0) or 0)
        if abs(ms - current) < PLAYHEAD_EPSILON_MS:
            self._last_acted_playhead_ms = ms
            return
        seek = getattr(page, "_seek", None)
        if callable(seek):
            try:
                seek(ms / 1000.0)
                self._last_acted_playhead_ms = ms
            except Exception:  # noqa: BLE001
                pass

    def _editing_has_focus(self) -> bool:
        guard = getattr(self.page, "_editing_has_focus", None)
        if callable(guard):
            try:
                return bool(guard())
            except Exception:  # noqa: BLE001
                return False
        return False


def install_davinci_live_link(page) -> DavinciLiveLink:
    """挂到编辑器页面上（重复调用返回同一个实例）。"""
    existing = getattr(page, "_davinci_live_link", None)
    if isinstance(existing, DavinciLiveLink):
        existing.start()
        return existing
    link = DavinciLiveLink(page)
    page._davinci_live_link = link
    link.start()
    return link
