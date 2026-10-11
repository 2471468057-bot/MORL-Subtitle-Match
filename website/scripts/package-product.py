"""Package the product page: a review zip (built page + evidence) and a source zip.

Earlier packages in deliverables/ stay untouched as the before-state.
Run after `npm run build`, `node scripts/build-readme-scenes.mjs` and `npm test`.
"""
from pathlib import Path
import hashlib
import json
import zipfile

site = Path(__file__).resolve().parents[1]
build = site / "product-build"
evidence = site / "review-20261009"
dest = site / "deliverables"
dest.mkdir(exist_ok=True)
TAG = "v3-20261009"  # v3: Chinese, English and Japanese pages
for name in ["打开产品介绍.html", "portable.html", "portable-en.html", "portable-ja.html", "index.html", "en.html", "ja.html",
             "product.js", "product-en.js", "product-ja.js", "product.css"]:
    assert (build / name).is_file(), f"Missing build output: {name}"
for name in ["VALIDATION.md", "verify.json"]:
    assert (evidence / name).is_file(), f"Missing evidence: {name}"


def pack(name, files, extra):
    target = dest / name
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for file, arc in sorted(files, key=lambda x: x[1]):
            z.write(file, arc)
        for arc, text in extra.items():
            z.writestr(arc, text)
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
    return {"file": name, "bytes": target.stat().st_size, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


review = [(p, p.relative_to(build).as_posix()) for p in build.rglob("*") if p.is_file()]
review += [(p, "review/" + p.relative_to(evidence).as_posix()) for p in evidence.rglob("*") if p.is_file()]
results = [pack(f"2ByteASR-product-page-{TAG}-review.zip", review, {
    "请先阅读.md": "# 兔白字幕产品介绍页（2026-10-09 改版，中文 / English / 日本語）\n\n解压后打开“打开产品介绍.html”（中文）、“portable-en.html”（English）或“portable-ja.html”（日本語）。脚本、样式、字体与图片都已内嵌，可离线查看；三个文件放在同一文件夹时，页面右上角可以切换语言。日文页的日文使用电脑自带的日文字体。\nreview/ 里是三种语言的截图（zh- / en- / ja-）、浏览器检查结果 verify.json 和检查范围 VALIDATION.md。\n仅本地审阅，没有部署或发布。\n",
})]

allow = [
    "product", "public", "scripts", "tests/product-control.test.mjs", "tests/product-editing.test.mjs",
    "tests/product-bundle.test.mjs", "tests/product-site.test.mjs", "tests/product-i18n.test.mjs", "review-20261009",
    "package.json", "index.html", "preview.cmd", "README.md", "DESIGN.md", "ASSETS.md", ".gitignore",
]
skip = {"generated-themes.js"}
files = []
for item in allow:
    p = site / item
    assert p.exists(), item
    for f in p.rglob("*") if p.is_dir() else [p]:
        if f.is_file() and f.name not in skip and "__pycache__" not in f.parts:
            files.append((f, "website/" + f.relative_to(site).as_posix()))
results.append(pack(f"2ByteASR-product-page-{TAG}-source.zip", files, {
    "SOURCE-START.md": "# 兔白字幕产品介绍页源码（2026-10-09 改版）\n\n进入 website：npm install、npm run build、npm test；预览用 npm run preview，再运行 node scripts/verify-product.mjs 做浏览器检查。\n改动页面文字后，用装有 fontTools + brotli 的 Python 运行 scripts/subset-fonts.py 重新生成字体子集。\n三种语言：页面文案在 product/i18n/copy.*.js；界面文字写 t(\"中文\")，英日译文来自桌面词表（scripts/extract_i18n.py 生成 app-strings.json，需要完整仓库）和 product/i18n/ui.js。\n目录数据由 scripts/extract_catalog.py 从桌面源码抽取，需要在完整仓库里运行。\n本包不含桌面程序源码、配置、用户工程、模型或密钥。\n",
}))
(dest / f"product-{TAG}-SHA256SUMS.txt").write_text("".join(f"{r['sha256']}  {r['file']}\n" for r in results), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False, indent=2))
