import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const read = (p) => fs.readFileSync(new URL(p, import.meta.url), "utf8");
// esbuild writes non-ASCII text as \uXXXX escapes; decode before looking at characters.
const decode = (s) => s.replace(/\\u\{([0-9a-f]+)\}|\\u([0-9a-f]{4})/gi, (_, a, b) => String.fromCodePoint(parseInt(a || b, 16)));
const catalog = JSON.parse(read("../public/data/catalog.json"));

test("catalog, plans and themes come from the current desktop source", () => {
  assert.equal(catalog.schema, 2);
  assert.equal(catalog.models.length, 18);
  for (const gone of ["nemotron", "qwen_api", "qwen31_flash", "qwen_audio_asr_flash", "mai_transcribe_2_word", "qwen_audio_filetrans"])
    assert.ok(!catalog.models.some((m) => m.key === gone), gone);
  assert.deepEqual(catalog.plans.map((p) => p.key), ["quality", "speed", "low_memory", "transcribe_only", "api", "custom"]);
  const keys = new Set(catalog.models.map((m) => m.key));
  for (const p of catalog.plans) if (!["api", "custom"].includes(p.key)) assert.ok(keys.has(p.primary), p.primary);
  assert.deepEqual(Object.keys(catalog.themes), ["grape", "warm", "plum", "lavender", "slate"]);
  assert.equal(catalog.themes.grape.accent, "#b34470");
  for (const t of Object.values(catalog.themes)) assert.ok(t.roles.primary && t.zones.studio);
});

test("reference indices are relative scores with the not-accuracy note", () => {
  assert.match(catalog.reference_note, /不是识别正确率/);
  for (const m of catalog.models)
    for (const kind of ["accuracy", "speed"]) {
      const e = m.reference[kind];
      if (e) assert.ok(e.score >= 1 && e.score <= 100 && typeof e.approx === "boolean", m.key + kind);
    }
});

// The Chinese and English pages set all text in the subset; the Japanese page
// uses system Japanese fonts and only its marked Chinese samples (checked in
// scripts/verify-product.mjs) come from the subset.
test("every character the page renders is inside the embedded font subset", () => {
  const charset = new Set(read("../product/fonts/charset.txt"));
  const shipped = decode(read("../product-build/product.js") + read("../product-build/product-en.js") + read("../product-build/product.css"));
  assert.ok(shipped.includes("录播拖进来"), "decoded bundle text");
  // CJK punctuation, ideographs and full-width forms; React's own regex ranges
  // (U+2FEF, U+D7FF, U+F900, U+FDCF, U+FDF0, U+FFFD) are not page text.
  const cjk = (c) => (c >= 0x3000 && c <= 0x303f) || (c >= 0x3400 && c <= 0x9fff) || (c >= 0xff00 && c <= 0xffef);
  const missing = [...new Set(shipped)].filter((ch) => cjk(ch.codePointAt(0)) && !charset.has(ch));
  assert.deepEqual(missing, [], "run scripts/subset-fonts.py again");
});

test("no decorative gradients, gradient text or glows in the page styles", () => {
  const css = read("../product-build/product.css");
  assert.doesNotMatch(css, /(linear|radial|conic)-gradient\(/);
  assert.doesNotMatch(css, /background-clip:\s*text/);
});

test("the standalone pages carry their fonts and stay offline", () => {
  for (const name of ["portable.html", "portable-en.html", "portable-ja.html"]) {
    const html = read("../product-build/" + name);
    assert.match(html, /data:font\/woff2;base64,/, name);
    assert.doesNotMatch(html, /<link[^>]+href="https?:/i, name);
    assert.doesNotMatch(html, /<script[^>]+src=/i, name);
    assert.match(html, /window\.__LANG_PAGES=/, name);
  }
});
