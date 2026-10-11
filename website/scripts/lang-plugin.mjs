// esbuild plugin: bundles one page language. "@lang/copy" and "@lang/sample"
// become product/i18n/{copy,sample}.<lang>.js and "@lang/dict" the zh -> <lang> interface
// table (app-strings.json from the desktop app, then ui.js on top).
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dir = path.join(root, "product/i18n");
export const LANGS = ["zh", "en", "ja"];

export async function dictFor(lang) {
  if (lang === "zh") return {};
  const column = { en: 0, ja: 1 }[lang];
  const app = JSON.parse(await fs.readFile(path.join(dir, "app-strings.json"), "utf8"));
  const ui = (await import(pathToFileURL(path.join(dir, "ui.js")) + "?t=" + Date.now())).default;
  const out = {};
  for (const [k, v] of Object.entries(app)) out[k] = v[lang];
  for (const [k, v] of Object.entries(ui)) if (v[column] != null) out[k] = v[column];
  return out;
}

export async function copyFor(lang) {
  return (await import(pathToFileURL(path.join(dir, `copy.${lang}.js`)) + "?t=" + Date.now())).default;
}

export const langPlugin = (lang) => ({
  name: "page-language",
  setup(b) {
    b.onResolve({ filter: /^@lang\/(dict|copy|sample)$/ }, (a) => ({ path: a.path.slice(6), namespace: "lang" }));
    b.onLoad({ filter: /^dict$/, namespace: "lang" }, async () => ({
      contents: JSON.stringify(await dictFor(lang)),
      loader: "json",
      watchFiles: [path.join(dir, "app-strings.json"), path.join(dir, "ui.js")],
    }));
    b.onLoad({ filter: /^(copy|sample)$/, namespace: "lang" }, (a) => ({
      contents: `export { default } from "./${a.path}.${lang}.js";`,
      resolveDir: dir,
      loader: "js",
    }));
  },
});
