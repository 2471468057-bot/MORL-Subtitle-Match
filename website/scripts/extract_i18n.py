"""Collect the desktop app's own English / Japanese text for the page.

The interface replicas on the English and Japanese pages should read like the
real app in that language, so every t("中文") key the page uses, and every
catalog string it shows, is looked up in twobyteasr/i18n.py (the app's merged
zh -> en / ja tables). Hits go to product/i18n/app-strings.json; misses are
listed so they can be written by hand in product/i18n/ui.js (which also holds
deliberate context overrides and wins over the app text).

Run from the full repository (needs the desktop source, not its runtime deps):
    python -X utf8 scripts/extract_i18n.py
"""
import json
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
sys.path.insert(0, str(ROOT))
from twobyteasr import i18n  # noqa: E402

KEY = re.compile(r'\bt\(\s*"((?:[^"\\]|\\.)*)"')
HAN = re.compile(r"[㐀-鿿]")


def page_keys() -> set[str]:
    keys = set()
    for path in (WEB / "product").rglob("*"):
        if path.suffix in {".js", ".jsx"} and "i18n" not in path.parts:
            keys |= {json.loads('"' + k + '"') for k in KEY.findall(path.read_text("utf-8"))}
    return keys


def catalog_strings() -> set[str]:
    """Every catalog string the page renders (models.jsx, plans.jsx)."""
    c = json.loads((WEB / "public" / "data" / "catalog.json").read_text("utf-8"))
    out = {c["reference_note"]}
    for m in c["models"]:
        tech, copy, ref = m.get("technical") or {}, m.get("copy") or {}, m.get("reference") or {}
        out |= {m["name"], m["mode"], m["summary"], copy.get("summary"), copy.get("limitations"), m.get("verification"),
                tech.get("purpose"), tech.get("limits"), ref.get("caption")}
        for kind in ("accuracy", "speed"):
            if ref.get(kind):
                out |= {ref[kind].get("label"), ref[kind].get("reason")}
    for p in c["plans"]:
        out |= {p["label"], p["description"]}
    return {s for s in out if s and HAN.search(s)}


def main() -> None:
    table = i18n._TRANSLATIONS
    keys = page_keys() | catalog_strings()
    hits = {k: {"en": table["en"][k], "ja": table["ja"][k]}
            for k in sorted(keys) if "|" not in k and k in table["en"] and k in table["ja"]}
    target = WEB / "product" / "i18n" / "app-strings.json"
    target.write_text(json.dumps(hits, ensure_ascii=False, indent=1, sort_keys=True) + "\n", "utf-8")
    missing = sorted(k for k in keys if k not in hits)
    print(f"{len(keys)} keys; {len(hits)} from the app -> {target.relative_to(WEB)}; {len(missing)} need ui.js")
    for k in missing:
        print("  " + k)


if __name__ == "__main__":
    main()
