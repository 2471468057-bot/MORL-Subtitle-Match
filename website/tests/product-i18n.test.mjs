import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import zh from "../product/i18n/copy.zh.js";
import en from "../product/i18n/copy.en.js";
import ja from "../product/i18n/copy.ja.js";
import ui from "../product/i18n/ui.js";
import sampleZh from "../product/i18n/sample.zh.js";
import sampleEn from "../product/i18n/sample.en.js";
import sampleJa from "../product/i18n/sample.ja.js";
import { words as zhWords } from "../product/edit-model.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (p) => fs.readFileSync(path.join(root, p), "utf8");
// esbuild writes non-ASCII text as \uXXXX escapes; decode before looking at characters.
const decode = (s) => s.replace(/\\u\{([0-9a-f]+)\}|\\u([0-9a-f]{4})/gi, (_, a, b) => String.fromCodePoint(parseInt(a || b, 16)));
const app = JSON.parse(read("product/i18n/app-strings.json"));
const catalog = JSON.parse(read("public/data/catalog.json"));
const HAN = /[㐀-鿿]/;
const KANA = /[぀-ヿ]/;

// Same shape: every key, every array length; strings only where zh has strings.
function shape(a, b, at = "copy") {
  if (a === null) return assert.ok(b === null || Array.isArray(b), at);
  assert.equal(typeof b, typeof a, at);
  if (Array.isArray(a)) {
    assert.ok(Array.isArray(b), at);
    assert.equal(b.length, a.length, at);
    a.forEach((v, i) => shape(v, b[i], `${at}[${i}]`));
  } else if (typeof a === "object") {
    assert.deepEqual(Object.keys(b).sort(), Object.keys(a).sort(), at);
    for (const k of Object.keys(a)) shape(a[k], b[k], `${at}.${k}`);
  }
}
const strings = (o) => (typeof o === "string" ? [o] : o && typeof o === "object" ? Object.values(o).flatMap(strings) : []);

test("the three copy files have the same structure", () => {
  shape(zh, en, "en");
  shape(zh, ja, "ja");
});

test("sample subtitles exist in every language with the Chinese segmentation", () => {
  const glossary = JSON.parse(read("product/glossary-data.json"));
  const ids = glossary.flatMap((g) => g.rows.map((r) => r.id));
  for (const [lang, s] of Object.entries({ en: sampleEn, ja: sampleJa })) {
    // same 26 words; every subtitle line still ends with punctuation
    assert.equal(s.words.length, zhWords.length, lang);
    for (const i of [4, 8, 16, 22, 25]) assert.match(s.words[i], /[,.、。]$/, `${lang} word ${i}`);
    assert.equal(s.readings.length, 3);
    assert.equal(s.rows.length, 5);
    assert.equal(s.proofread.length, 4);
    assert.equal(s.proofAdd.length, 2);
    assert.deepEqual(Object.keys(s.glossary).sort(), ids.sort(), lang);
    const text = JSON.stringify(s);
    if (lang === "en") assert.doesNotMatch(text, HAN, "Chinese in the English sample");
    if (lang === "ja") assert.match(text, KANA);
  }
  assert.equal(sampleZh.words, null);
  assert.equal(sampleZh.readings[1], zhWords[16].text, "the Chinese right reading is the sample word");
  // each language's second reading is its sample word 16
  assert.equal(sampleEn.readings[1], sampleEn.words[16]);
  assert.equal(sampleJa.readings[1], sampleJa.words[16]);
});

test("copy markup is balanced and follows the page's writing rules", () => {
  for (const [lang, copy] of Object.entries({ zh, en, ja }))
    for (const s of strings(copy)) {
      const plain = s.replace(/\*\*[^*]+\*\*/g, "").replace(/\*[^*]+\*/g, "");
      assert.doesNotMatch(plain, /\*/, `${lang}: unbalanced * in ${s}`);
      assert.equal((s.match(/`/g) || []).length % 2, 0, `${lang}: unbalanced \` in ${s}`);
      assert.doesNotMatch(s, /—/, `${lang}: em dash in ${s}`);
    }
  // English copy has no Chinese except the brand in the meta description
  for (const s of strings(en)) assert.doesNotMatch(s.replace(/2ByteASR \(兔白字幕\)/, ""), HAN, s);
});

// Every interface key the page asks for, and every catalog string it shows.
function pageKeys() {
  const keys = new Set();
  const walk = (dir) => {
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) { if (e.name !== "i18n" && e.name !== "fonts") walk(p); }
      else if (/\.(jsx?|mjs)$/.test(e.name))
        for (const m of fs.readFileSync(p, "utf8").matchAll(/\bt\(\s*"((?:[^"\\]|\\.)*)"/g)) keys.add(JSON.parse(`"${m[1]}"`));
    }
  };
  walk(path.join(root, "product"));
  for (const m of catalog.models) {
    const tech = m.technical || {}, copy = m.copy || {}, ref = m.reference || {};
    [m.name, m.mode, m.summary, copy.summary, copy.limitations, m.verification, tech.purpose, tech.limits, ref.caption,
      ...["accuracy", "speed"].flatMap((k) => (ref[k] ? [ref[k].label, ref[k].reason] : []))].forEach((s) => s && keys.add(s));
  }
  for (const p of catalog.plans) keys.add(p.label), keys.add(p.description);
  keys.add(catalog.reference_note);
  return [...keys].filter((k) => HAN.test(k));
}
const lookup = (k, lang) => ui[k]?.[lang === "en" ? 0 : 1] ?? app[k]?.[lang];

test("every interface and catalog string has an English and a Japanese text", () => {
  const keys = pageKeys();
  assert.ok(keys.length > 350, keys.length);
  const missing = keys.flatMap((k) => ["en", "ja"].filter((l) => !lookup(k, l)).map((l) => `${l}: ${k}`));
  assert.deepEqual(missing, []);
  // placeholders survive translation
  for (const k of keys)
    for (const l of ["en", "ja"]) {
      const want = (k.match(/\{\w+\}/g) || []).sort();
      assert.deepEqual((lookup(k, l).match(/\{\w+\}/g) || []).sort(), want, `${l}: ${k}`);
    }
});

test("hand-written translations are real: English has no Chinese, Japanese is not English", () => {
  for (const [k, [e, j]] of Object.entries(ui)) {
    assert.ok(e != null || j != null, k);
    if (e) assert.doesNotMatch(e, HAN, `en: ${k}`);
    if (j && e) assert.notEqual(j, e, `ja copies en: ${k}`);
    if (j && /[a-z]{3}/i.test(j.replace(/\{\w+\}/g, ""))) assert.ok(KANA.test(j) || HAN.test(j), `ja without Japanese: ${k}`);
  }
});

test("each language bundle carries only its own language", () => {
  const [zhJs, enJs, jaJs] = ["product.js", "product-en.js", "product-ja.js"].map((f) => decode(read("product-build/" + f)));
  assert.doesNotMatch(enJs, KANA, "Japanese text in the English bundle");
  assert.doesNotMatch(zhJs, KANA, "Japanese text in the Chinese bundle");
  assert.ok(!jaJs.includes(en.hero.download) && !zhJs.includes(en.hero.download));
  assert.ok(jaJs.includes(ja.hero.download) && enJs.includes(en.hero.download));
  for (const [file, lang, title] of [["index.html", "zh-CN", zh.meta.title], ["en.html", "en", en.meta.title], ["ja.html", "ja", ja.meta.title]]) {
    const html = read("product-build/" + file);
    assert.match(html, new RegExp(`<html lang="${lang}">`));
    assert.ok(html.includes(`<title>${title}</title>`), file);
    assert.equal((html.match(/rel="alternate" hreflang=/g) || []).length, 3, file);
  }
});
