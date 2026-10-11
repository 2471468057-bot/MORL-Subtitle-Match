"""Subset the desktop app's Source Han Sans SC to the characters this page uses.

Run with any Python that has fontTools + brotli (not part of the desktop env):
    python -X utf8 scripts/subset-fonts.py
Medium and Heavy come from assets/fonts (the desktop's own files). Paragraph
text uses Regular: the same Adobe design, instanced at wght 400 from Noto Sans
SC VF (OFL; path via NOTO_SC_VF). Without it the 400 face falls back to Medium.
Subsets are renamed "2B Sans" (OFL Reserved Font Name: "Source").
Writes product/fonts/2b-sans-{400,500,900}.woff2 and product/fonts/charset.txt.
Re-run after changing page text; tests/product-site.test.mjs checks coverage.
"""
import json
import os
import subprocess
from pathlib import Path

from fontTools import subset
from fontTools.varLib import instancer

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parent
OUT = WEB / "product" / "fonts"
NOTO_VF = Path(os.environ.get("NOTO_SC_VF", "C:/Windows/Fonts/NotoSansSC-VF.ttf"))
SOURCES = {
    "400": NOTO_VF if NOTO_VF.is_file() else ROOT / "assets" / "fonts" / "SourceHanSansSC-Medium.otf",
    "500": ROOT / "assets" / "fonts" / "SourceHanSansSC-Medium.otf",
    "900": ROOT / "assets" / "fonts" / "SourceHanSansSC-Heavy.otf",
}
# Page text lives in JSX/JS/JSON; generated artwork is excluded (own fonts).
# The Japanese page sets Japanese in system fonts, so Japanese copy and the
# Japanese column of the interface tables stay out of this Chinese subset;
# only their `Chinese sample` spans are added.
I18N = WEB / "product" / "i18n"
JA_ONLY = {I18N / "copy.ja.js", I18N / "sample.ja.js", I18N / "ui.js", I18N / "app-strings.json"}
TEXT_FILES = [
    p for p in [*(WEB / "product").rglob("*"), WEB / "public" / "data" / "catalog.json"]
    if p.suffix in {".jsx", ".js", ".json", ".css", ".html"} and p.is_file()
    and p.name != "generated-themes.js" and "fonts" not in p.parts and p not in JA_ONLY
]


def interface_text() -> str:
    """Keys and English values of the interface tables (no Japanese)."""
    app = json.loads((I18N / "app-strings.json").read_text("utf-8"))
    ui = json.loads(subprocess.run(
        ["node", "--input-type=module", "-e",
         "const m = await import(process.argv[1]); console.log(JSON.stringify(m.default))",
         (I18N / "ui.js").as_uri()],
        check=True, capture_output=True, encoding="utf-8").stdout)
    parts = [*app, *(v["en"] for v in app.values()), *ui, *(v[0] or "" for v in ui.values())]
    ja = (I18N / "copy.ja.js").read_text("utf-8").split("`")[1::2]
    ja += [p for v in ui.values() if v[1] for p in v[1].split("`")[1::2]]
    return "".join(parts + ja)


def charset() -> str:
    chars = {chr(c) for c in range(0x20, 0x7F)}
    chars |= set("·—–…“”‘’「」『』《》（）【】、，。：；！？％＋－×÷→←↑↓↗↘⌄›‹✓✕★☆●○◆◇▶■□▲△⏮⏭⏸")
    for text in [*(p.read_text("utf-8") for p in TEXT_FILES), interface_text()]:
        chars |= {ch for ch in text if ord(ch) >= 0x20 and not 0xD800 <= ord(ch) <= 0xDFFF}
    return "".join(sorted(chars))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = charset()
    (OUT / "charset.txt").write_text(text, "utf-8")
    for weight, source in SOURCES.items():
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = ["kern", "palt", "pwid", "vert", "locl"]  # pwid: English quotes
        options.name_IDs = [0, 1, 2, 3, 4, 5, 6]
        options.hinting = False
        options.desubroutinize = True
        font = subset.load_font(str(source), options)
        if "fvar" in font:
            font = instancer.instantiateVariableFont(font, {"wght": int(weight)})
        sub = subset.Subsetter(options)
        sub.populate(text=text)
        sub.subset(font)
        style = {"400": "Regular", "500": "Medium", "900": "Heavy"}[weight]
        names = font["name"]
        for record in list(names.names):
            if record.nameID in (1, 3, 4, 6, 16, 17):
                names.removeNames(nameID=record.nameID)
        for name_id, value in ((1, "2B Sans " + style), (3, "2B Sans " + style + " subset"),
                               (4, "2B Sans " + style), (6, "2BSans-" + style), (16, "2B Sans"), (17, style)):
            names.setName(value, name_id, 3, 1, 0x409)
        target = OUT / f"2b-sans-{weight}.woff2"
        subset.save_font(font, str(target), options)
        print(f"{target.name}: {target.stat().st_size // 1024} KB, {len(text)} chars")


if __name__ == "__main__":
    main()
