"""Dependency-light text distance helpers shared across pipeline stages."""

from __future__ import annotations


def levenshtein(left, right):
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, 1):
        current = [left_index]
        for right_index, right_value in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def phonetic_text(text):
    # Lazy import keeps this low-level module out of subtitle_core's import cycle.
    from pypinyin import Style, lazy_pinyin
    from twobyteasr.text_rules import content_only

    return "".join(
        lazy_pinyin(
            content_only(text),
            style=Style.NORMAL,
            errors=lambda value: list(value),
        )
    ).lower()


__all__ = ["levenshtein", "phonetic_text"]
