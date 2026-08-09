"""Lexicon files must stay valid: unique names, no single CJK characters
(they would pollute the term candidates), and registered in game profiles."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

LEXICONS = Path(__file__).resolve().parents[1] / "lexicons"
PROFILES = Path(__file__).resolve().parents[1] / "game_profiles.json"


@pytest.mark.parametrize(
    "name",
    [
        "arknights_operators.json",
        "arknights_terms.json",
        "zenless_characters.json",
        "zenless_terms.json",
        "rocom_skills.json",
        "rocom_spirits.json",
    ],
)
def test_lexicon_schema_and_uniqueness(name):
    payload = json.loads((LEXICONS / name).read_text(encoding="utf-8"))
    assert payload["schema"] == 1
    assert payload["entry_count"] == len(payload["entries"])
    names = [entry["name"] for entry in payload["entries"]]
    assert len(names) == len(set(names)), "entry names must be unique"
    assert all(isinstance(n, str) and n for n in names)


def test_no_single_character_entries_in_new_lexicons():
    for name in ("arknights_operators.json", "arknights_terms.json",
                 "zenless_characters.json", "zenless_terms.json"):
        payload = json.loads((LEXICONS / name).read_text(encoding="utf-8"))
        for entry in payload["entries"]:
            assert not re.fullmatch(r"[\u4e00-\u9fff]", entry["name"]), (
                f"single CJK character must not be a lexicon entry: {entry['name']}"
            )


def test_new_lexicons_registered_in_game_profiles():
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    registered = {
        path
        for profile in profiles["profiles"].values()
        for path in (profile.get("lexicons") or [])
    }
    assert "lexicons/arknights_operators.json" in registered
    assert "lexicons/zenless_characters.json" in registered
    assert "明日方舟" in profiles["profiles"]
