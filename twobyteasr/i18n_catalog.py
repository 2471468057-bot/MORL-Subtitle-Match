"""Reviewed additions to the shared UI catalog (Chinese source, English, Japanese).

Loaded dynamically from locales/catalog.json to prevent Python AST bloat.
"""
from __future__ import annotations

import json
from pathlib import Path

_catalog_path = Path(__file__).resolve().parent / "locales" / "catalog.json"

with open(_catalog_path, "r", encoding="utf-8") as _f:
    STRINGS: dict[str, tuple[str, str]] = {
        _k: (_v[0], _v[1]) for _k, _v in json.load(_f).items()
    }
