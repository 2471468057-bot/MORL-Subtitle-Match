"""Which page the window opens on, and how it treats files given at launch.

The recognition home page has been retired: its settings now open as a modal
from the editor's toolbar. Every launch therefore lands in the Studio — either
on the project library (no project yet) or straight in the editor.
"""

from __future__ import annotations

import os
from pathlib import Path

from .media_intake import SUPPORTED_MEDIA_SUFFIXES

PROJECT_SUFFIXES = frozenset({".2byteproj", ".2byteasrproj"})
SUBTITLE_SUFFIXES = frozenset({".srt", ".ass", ".ssa", ".vtt"})

# Pages the main window can open on.
DEST_RECOGNITION = "recognition"
DEST_LIBRARY = "project_library"
DEST_STUDIO = "studio"

# Kept for compatibility with launchers that still set it.
STUDIO_START_ENV = "TWOBYTEASR_START_IN_STUDIO"


def path_identity(path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def classify_open_paths(paths):
    """Return ordered typed requests, coalescing duplicate path identities."""
    result, seen = [], set()
    for raw in paths or ():
        path = str(Path(str(raw)).expanduser())
        identity = path_identity(path)
        if identity in seen:
            continue
        seen.add(identity)
        suffix = Path(path).suffix.lower()
        kind = ("project" if suffix in PROJECT_SUFFIXES else
                "subtitle" if suffix in SUBTITLE_SUFFIXES else
                "media" if suffix in SUPPORTED_MEDIA_SUFFIXES else "unsupported")
        result.append((kind, path))
    return result


def studio_start_requested() -> bool:
    """Retained for callers that still ask; the Studio is always the start page."""
    return True


def startup_destination(paths, preferences, *, explicit_operation=False):
    """Every launch opens the Studio.

    Media or project arguments are handed to the intake queue afterwards, which
    loads them into the editor; there is no separate recognition page to route
    to anymore.
    """
    requests = classify_open_paths(paths)
    if any(kind in {"project", "subtitle"} for kind, _ in requests):
        # 2026-10-18（用户："这个页面怎么还在"）：工程库/识别首页已删除，传入工程
        # 文件也应直接进编辑器，不再路由到那个页面。
        return DEST_STUDIO
    if requests or explicit_operation:
        # Media arguments: open the editor and let the intake queue add them.
        return DEST_STUDIO
    # 旧设置里可能仍存着 "project_library"（该页面已删除）：一律落到 Studio，
    # 否则会打开那个本该消失的识别首页。
    return DEST_STUDIO
