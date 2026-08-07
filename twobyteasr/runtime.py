"""Per-queue mutable runtime state shared by pipeline stages.

The application currently runs one media queue at a time.  A queue owns one
``RuntimeContext`` instance; worker threads read the same object, so changing a
runtime option never relies on values copied by ``from subtitle_core import *``.
Legacy module attributes are mirrored while old entry points are still kept.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class RuntimeContext:
    game_name: str = ""
    enable_domain_terms: bool = False
    discovered_terms: set[str] = field(default_factory=set)
    output_review_track: bool = False
    force_refresh_api_cache: bool = False
    force_refresh_polish_cache: bool = False
    force_refresh_group_cache: bool = False
    expected_speakers: int = 0
    cancellation_token: Any | None = None
    event_log_path: str = ""
    review_items: list[dict[str, Any]] = field(default_factory=list)

    def reset_for_media(self) -> None:
        """Clear output/report state while retaining queue-wide discovered terms."""
        self.review_items.clear()


_CONTEXT_LOCK = threading.RLock()
_ACTIVE_CONTEXT = RuntimeContext()


def get_runtime_context() -> RuntimeContext:
    """Return the context active for the current queue and its worker threads."""
    with _CONTEXT_LOCK:
        return _ACTIVE_CONTEXT


def runtime_context_from_legacy(legacy: Any) -> RuntimeContext:
    """Build a context from compatibility attributes without retaining them."""
    return RuntimeContext(
        game_name=str(getattr(legacy, "RUNTIME_GAME_NAME", "") or ""),
        enable_domain_terms=bool(getattr(legacy, "RUNTIME_ENABLE_DOMAIN_TERMS", False)),
        discovered_terms=set(getattr(legacy, "RUNTIME_DISCOVERED_TERMS", set()) or ()),
        output_review_track=bool(getattr(legacy, "RUNTIME_OUTPUT_REVIEW_TRACK", False)),
        force_refresh_api_cache=bool(
            getattr(legacy, "RUNTIME_FORCE_REFRESH_API_CACHE", False)
        ),
        force_refresh_polish_cache=bool(
            getattr(legacy, "RUNTIME_FORCE_REFRESH_POLISH_CACHE", False)
        ),
        force_refresh_group_cache=bool(
            getattr(legacy, "RUNTIME_FORCE_REFRESH_GROUP_CACHE", False)
        ),
        expected_speakers=int(getattr(legacy, "RUNTIME_EXPECTED_SPEAKERS", 0) or 0),
        cancellation_token=getattr(legacy, "RUNTIME_CANCELLATION_TOKEN", None),
        event_log_path=str(getattr(legacy, "RUN_EVENT_LOG_PATH", "") or ""),
        review_items=list(getattr(legacy, "RUN_REVIEW_ITEMS", ()) or ()),
    )


def sync_legacy_runtime(legacy: Any, context: RuntimeContext) -> None:
    """Mirror the active context for callers that still use the old attributes."""
    legacy.RUNTIME_GAME_NAME = context.game_name
    legacy.RUNTIME_ENABLE_DOMAIN_TERMS = context.enable_domain_terms
    legacy.RUNTIME_DISCOVERED_TERMS = context.discovered_terms
    legacy.RUNTIME_OUTPUT_REVIEW_TRACK = context.output_review_track
    legacy.RUNTIME_FORCE_REFRESH_API_CACHE = context.force_refresh_api_cache
    legacy.RUNTIME_FORCE_REFRESH_POLISH_CACHE = context.force_refresh_polish_cache
    legacy.RUNTIME_FORCE_REFRESH_GROUP_CACHE = context.force_refresh_group_cache
    legacy.RUNTIME_EXPECTED_SPEAKERS = context.expected_speakers
    legacy.RUNTIME_CANCELLATION_TOKEN = context.cancellation_token
    legacy.RUN_EVENT_LOG_PATH = context.event_log_path
    legacy.RUN_REVIEW_ITEMS = context.review_items


@contextmanager
def activate_runtime_context(
    context: RuntimeContext,
    *,
    legacy: Any | None = None,
) -> Iterator[RuntimeContext]:
    """Activate a queue context and restore the previous one on every exit path."""
    global _ACTIVE_CONTEXT
    with _CONTEXT_LOCK:
        previous = _ACTIVE_CONTEXT
        _ACTIVE_CONTEXT = context
        if legacy is not None:
            sync_legacy_runtime(legacy, context)
    try:
        yield context
    finally:
        with _CONTEXT_LOCK:
            _ACTIVE_CONTEXT = previous
            if legacy is not None:
                sync_legacy_runtime(legacy, previous)


__all__ = [
    "RuntimeContext",
    "activate_runtime_context",
    "get_runtime_context",
    "runtime_context_from_legacy",
    "sync_legacy_runtime",
]
