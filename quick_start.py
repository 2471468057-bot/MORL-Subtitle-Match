"""Fast 2ByteASR launcher: open the workbench first, then drop media into it."""

from __future__ import annotations

import os
import sys


PIPELINE_BUILD_ID = "2026.08.05-v7.14-strict-length-number-style"


def _show_error(title: str, message: str) -> None:
    """Show a native message box; never fail silently (pythonw has no console)."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    except Exception:
        pass


def _write_setup_marker() -> None:
    """Self-heal: once the app starts, record that configuration finished.

    Legacy installs configured before the marker feature existed would
    otherwise keep showing the first-run dialog. The marker is written next
    to this script; the path is normalized and confined to the script dir.
    """
    try:
        import datetime
        import pathlib
        root = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))
        marker = os.path.join(root, "2byteasr.setup-complete")
        if not os.path.abspath(marker).startswith(os.path.abspath(root) + os.sep):
            return
        pathlib.Path(marker).write_text(
            datetime.datetime.now().isoformat(), encoding="ascii")
    except Exception:
        pass


def main() -> int:
    try:
        import moss_firered_pipeline
        import subtitle_core
        from twobyteasr.ui import run_desktop_app

        moss_firered_pipeline.verify_pipeline_contract(
            subtitle_core,
            os.path.realpath(__file__),
            PIPELINE_BUILD_ID,
        )
        _write_setup_marker()
        return run_desktop_app(
            subtitle_core,
            moss_firered_pipeline,
            None,
            select_media=False,
            initial_paths=sys.argv[1:],
        )
    except Exception as exc:
        _show_error(
            "2ByteASR 启动失败",
            "运行环境不完整（可能上次配置中断），无法启动工作台。\n\n"
            "请双击 setup_2byteasr.bat 重新完成配置，"
            "已下载的内容会自动续传、不会重复下载。\n\n"
            f"详细信息：\n{exc}",
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
