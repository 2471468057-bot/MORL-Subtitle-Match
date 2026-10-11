// The page language is fixed at build time: scripts/build-product.mjs bundles
// the page once per language and resolves "@lang/*" to that language's files.
//   t("中文原文")   interface text, keyed by its Chinese source like the desktop
//                   app's own i18n (twobyteasr/i18n.py); zh returns the key.
//   COPY.x.y        page copy (headlines, ledes, points), one file per language.
//   rich("…")      renders copy markup: *em*  **strong**  `中文示例`  \n = <br>.
// Chinese sample content (subtitles, glossary terms) stays Chinese in every
// language and carries lang={ZH}, so it is set in the Chinese font.
import React, { Fragment } from "react";
import DICT from "@lang/dict";
import COPY from "@lang/copy";

export const LANG = __LANG__;
export const ZH = "zh-CN";
export { COPY };
// [code, name in that language, html lang, short label for narrow screens]
export const LANGS = [
  ["zh", "中文", "zh-CN", "中"],
  ["en", "English", "en", "EN"],
  ["ja", "日本語", "ja", "日"],
];
const PAGES = { zh: "./index.html", en: "./en.html", ja: "./ja.html" };
export const pageFor = (lang) => globalThis.window?.__LANG_PAGES?.[lang] || PAGES[lang];

// A key may carry a context after "|" ("关闭|off") when one Chinese word needs
// two translations; the Chinese page shows the part before "|".
export function t(src, params) {
  const s = DICT[src] ?? src.replace(/\|[^|]*$/, "");
  if (!params) return s;
  const parts = s.split(/\{(\w+)\}/);
  if (Object.values(params).every((v) => v == null || typeof v !== "object"))
    return parts.map((p, i) => (i % 2 ? params[p] ?? "" : p)).join("");
  return parts.map((p, i) => <Fragment key={i}>{i % 2 ? params[p] : p}</Fragment>);
}

// *em*  **strong**  `zh sample`  and line breaks.
const TOKEN = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\n)/;
export function rich(text) {
  if (text == null) return null;
  return text.split(TOKEN).map((p, i) => {
    if (!p) return null;
    if (p === "\n") return <br key={i} />;
    if (p.startsWith("**")) return <strong key={i}>{rich(p.slice(2, -2))}</strong>;
    if (p.startsWith("*")) return <em key={i}>{rich(p.slice(1, -1))}</em>;
    if (p.startsWith("`")) return <span key={i} lang={ZH}>{p.slice(1, -1)}</span>;
    return <Fragment key={i}>{p}</Fragment>;
  });
}
