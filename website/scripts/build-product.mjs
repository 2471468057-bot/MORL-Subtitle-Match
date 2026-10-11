import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import fs from "node:fs/promises";
import path from "node:path";
import { LANGS, copyFor, langPlugin } from "./lang-plugin.mjs";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
let req = createRequire(path.join(root, "package.json"));
try {
  req.resolve("esbuild");
} catch {
  req = createRequire(path.join(root, "../renderer/package.json"));
}
const { build } = req("esbuild");
const out = path.join(root, "product-build");
// Start clean so no output from an earlier round survives in the review package.
await fs.rm(out, { recursive: true, force: true });
await fs.mkdir(out, { recursive: true });

// One bundle per language; the Chinese page keeps its original file names.
const suffix = (lang) => (lang === "zh" ? "" : "-" + lang);
const HTML_LANG = { zh: "zh-CN", en: "en", ja: "ja" };
const PAGE = { zh: "index.html", en: "en.html", ja: "ja.html" };
const PORTABLE = { zh: "portable.html", en: "portable-en.html", ja: "portable-ja.html" };
for (const lang of LANGS) {
  await build({
    entryPoints: [path.join(root, "product/page.jsx")],
    outfile: path.join(out, `product${suffix(lang)}.js`),
    bundle: true,
    minify: true,
    format: "iife",
    nodePaths: [path.dirname(req.resolve("react/package.json")) + "/.."],
    jsx: "automatic",
    define: { "process.env.NODE_ENV": '"production"', __LANG__: JSON.stringify(lang) },
    plugins: [langPlugin(lang)],
    target: ["es2022"],
    loader: { ".woff2": "file" },
    assetNames: "fonts/[name]-[hash]",
  });
}
// Styles do not depend on the language: keep one product.css.
const css0 = await fs.readFile(path.join(out, "product.css"), "utf8");
for (const lang of LANGS.filter((l) => l !== "zh")) {
  const p = path.join(out, `product-${lang}.css`);
  if ((await fs.readFile(p, "utf8")) !== css0) throw new Error(`product-${lang}.css differs from product.css`);
  await fs.rm(p);
}

const template = await fs.readFile(path.join(root, "product/index.html"), "utf8");
const esc = (s) => s.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;");
function page(lang, copy, links) {
  const alternates = LANGS.map((l) => `<link rel="alternate" hreflang="${HTML_LANG[l]}" href="./${links[l]}">`).join("");
  const html = template
    .replace('<html lang="zh-CN">', `<html lang="${HTML_LANG[lang]}">`)
    .replace(/<meta name="description" content="[^"]*">/, () => `<meta name="description" content="${esc(copy.meta.description)}">`)
    .replace(/<title>[^<]*<\/title>/, () => `<title>${esc(copy.meta.title)}</title>${alternates}`)
    .replace(/<noscript>[^<]*<\/noscript>/, () => `<noscript>${esc(copy.meta.noscript)}</noscript>`)
    .replace('<script src="./product.js" defer></script>', `<script src="./product${suffix(lang)}.js" defer></script>`);
  if (html === template) throw new Error("index.html template changed shape");
  return html;
}
const copies = Object.fromEntries(await Promise.all(LANGS.map(async (l) => [l, await copyFor(l)])));
for (const lang of LANGS) await fs.writeFile(path.join(out, PAGE[lang]), page(lang, copies[lang], PAGE));

for (const name of ["assets/product", "assets/model-logos", "licenses", "data"])
  await fs.cp(path.join(root, "public", name), path.join(out, name), {
    recursive: true,
  });
await fs.copyFile(
  path.join(root, "public/assets/brand-256.png"),
  path.join(out, "assets/brand-256.png"),
);
await fs.copyFile(
  path.join(root, "public/THIRD_PARTY.md"),
  path.join(out, "THIRD_PARTY.md"),
);
// A separate portable HTML per language has every image, script, style and
// font embedded; its language links point at the other portable files.
const assets = {};
async function images(dir) {
  for (const e of await fs.readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) await images(p);
    else if (/\.(png|webp)$/.test(e.name)) {
      const key = "./" + path.relative(out, p).replaceAll("\\", "/");
      assets[key] =
        "data:image/" +
        (e.name.endsWith(".webp") ? "webp" : "png") +
        ";base64," +
        (await fs.readFile(p)).toString("base64");
    }
  }
}
await images(path.join(out, "assets"));
let css = css0;
// Fonts travel inside the standalone page as data URIs.
for (const m of new Set(css.match(/\.\/fonts\/[\w.-]+\.woff2/g) || []))
  css = css.replaceAll(
    m,
    "data:font/woff2;base64," +
      (await fs.readFile(path.join(out, m))).toString("base64"),
  );
const portablePages = Object.fromEntries(LANGS.map((l) => [l, PORTABLE[l]]));
for (const lang of LANGS) {
  const js = await fs.readFile(path.join(out, `product${suffix(lang)}.js`), "utf8");
  const html = page(lang, copies[lang], portablePages)
    .replace(
      '<link rel="stylesheet" href="./product.css">',
      () => `<style>${css}</style>`,
    )
    .replace(
      '<link rel="icon" href="./assets/brand-256.png">',
      () => `<link rel="icon" href="${assets["./assets/brand-256.png"]}">`,
    )
    .replace(
      `<script src="./product${suffix(lang)}.js" defer></script>`,
      () =>
        `<script>window.__PRODUCT_ASSETS=${JSON.stringify(assets)};window.__LANG_PAGES=${JSON.stringify(Object.fromEntries(LANGS.map((l) => [l, "./" + PORTABLE[l]])))};${js.replaceAll("</script", "<\\/script")}</script>`,
    );
  await fs.writeFile(path.join(out, PORTABLE[lang]), html);
  if (lang === "zh") await fs.writeFile(path.join(out, "打开产品介绍.html"), html);
}
console.log("Product pages (zh, en, ja) + standalone HTML: website/product-build. No deployment.");
