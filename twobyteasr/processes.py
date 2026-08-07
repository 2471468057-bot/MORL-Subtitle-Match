"""Cross-platform subprocess launch options used by the desktop workflow."""

from __future__ import annotations

import os
import subprocess


def hidden_subprocess_kwargs() -> dict:
    """Prevent console executables from opening a stray window on Windows."""
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0),
        "startupinfo": startupinfo,
    }
