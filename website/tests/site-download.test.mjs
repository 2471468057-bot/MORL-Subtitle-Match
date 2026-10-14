// Download routes (Pages Functions) against a stubbed GitHub, and the built
// pages' download links.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { ASSETS, downloadUrl, latestRelease, summary } from "../server/latest-release.js";
import { onRequestGet as download, onRequestHead } from "../functions/download/[name].js";
import { onRequestGet as releaseApi } from "../functions/api/release.js";
import zh from "../product/i18n/copy.zh.js";
import en from "../product/i18n/copy.en.js";
import ja from "../product/i18n/copy.ja.js";

const REPO = "NOTBAD314/2ByteASR";
const asset = (name, size = 1) => ({
  name,
  size,
  browser_download_url: `https://github.com/${REPO}/releases/download/v0.6.5/${name}`,
  url: `https://api.github.com/repos/${REPO}/releases/assets/${name.length}`,
});
const RELEASE = {
  tag_name: "v0.6.5",
  published_at: "2026-10-12T00:00:00Z",
  html_url: `https://github.com/${REPO}/releases/tag/v0.6.5`,
  assets: [
    asset("2ByteASR-Source-0.6.5.zip"),
    asset("2ByteASR-Setup-0.6.5-fix-20261013.exe", 2),
    asset("2ByteASR-Setup-0.6.5.exe", 1009166375),
    asset("2ByteASR-0.6.5-fix-1-macos-arm64-Setup.dmg", 3),
    asset("2ByteASR-0.6.5-macos-arm64-Setup.dmg", 546572457),
    asset("SHA256SUMS.txt"),
  ],
};
const WINDOWS_ONLY = { ...RELEASE, assets: RELEASE.assets.filter((a) => !a.name.endsWith(".dmg")) };
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

// Records requests; `routes` maps a URL prefix to a Response factory.
function github(routes) {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    for (const [prefix, respond] of Object.entries(routes))
      if (String(url).startsWith(prefix)) return respond();
    throw new TypeError("network down");
  };
  return { calls, fetchImpl };
}
const API = `https://api.github.com/repos/${REPO}/releases/latest`;
const WEB = `https://github.com/${REPO}/releases/latest`;

async function withFetch(fetchImpl, fn) {
  const saved = globalThis.fetch;
  globalThis.fetch = fetchImpl;
  try {
    return await fn();
  } finally {
    globalThis.fetch = saved;
  }
}
const request = (path, lang = "zh-CN,zh;q=0.9") =>
  new Request(`https://2byteasr.pages.dev${path}`, { headers: { "accept-language": lang } });

test("only the published latest release is asked for, and its own installers are picked", async () => {
  const gh = github({ [API]: () => json(RELEASE) });
  const rel = await latestRelease({}, gh.fetchImpl);
  assert.equal(gh.calls[0].url, API); // releases/latest never returns drafts or pre-releases
  assert.equal(gh.calls.length, 1);
  assert.equal(rel.version, "0.6.5");
  assert.equal(rel.assets.windows.name, "2ByteASR-Setup-0.6.5.exe");
  assert.equal(rel.assets.macos.name, "2ByteASR-0.6.5-macos-arm64-Setup.dmg");
  assert.deepEqual(summary(rel), {
    available: true,
    version: "0.6.5",
    tag: "v0.6.5",
    published: "2026-10-12T00:00:00Z",
    notes: RELEASE.html_url,
    windows: { name: "2ByteASR-Setup-0.6.5.exe", size: 1009166375 },
    macos: { name: "2ByteASR-0.6.5-macos-arm64-Setup.dmg", size: 546572457 },
  });
});

test("the Mac and Windows patterns never pick each other's installer", () => {
  const { windows, macos } = ASSETS;
  for (const v of ["0.7.1", "0.8.0-rc.1", "1.0.0+fix"]) {
    assert.ok(windows.match.test(windows.file(v)) && !macos.match.test(windows.file(v)), v);
    assert.ok(macos.match.test(macos.file(v)) && !windows.match.test(macos.file(v)), v);
  }
  assert.equal(macos.file("0.7.1"), "2ByteASR-0.7.1-macos-arm64-Setup.dmg");
  for (const other of ["2ByteASR-0.7.1-macos-x86_64-Setup.dmg", "2ByteASR-0.7.1-macos-arm64-Setup.dmg.sig", "2ByteASR-0.7.1-app-1cc2d3cbe544.zip"])
    assert.ok(!macos.match.test(other) && !windows.match.test(other), other);
});

test("a release without an installer is not offered", async () => {
  const gh = github({ [API]: () => json({ ...RELEASE, assets: [asset("SHA256SUMS.txt")] }) });
  const rel = await latestRelease({}, gh.fetchImpl);
  assert.equal(rel.assets.windows, undefined);
  assert.equal(summary(rel).available, false);
  assert.equal(summary(rel).macos, null);
});

test("a release without the Mac build still offers Windows", async () => {
  const rel = await latestRelease({}, github({ [API]: () => json(WINDOWS_ONLY) }).fetchImpl);
  assert.equal(rel.assets.macos, undefined);
  assert.equal(summary(rel).available, true);
  assert.equal(summary(rel).macos, null);
});

test("when the API is rate limited the web redirect still finds the newest tag", async () => {
  const gh = github({
    [API]: () => json({ message: "API rate limit exceeded" }, 403),
    [WEB]: () => new Response(null, { status: 302, headers: { location: `https://github.com/${REPO}/releases/tag/v0.7.0` } }),
  });
  const rel = await latestRelease({}, gh.fetchImpl);
  assert.equal(rel.version, "0.7.0");
  assert.equal(rel.assets.windows.url, `https://github.com/${REPO}/releases/download/v0.7.0/2ByteASR-Setup-0.7.0.exe`);
  assert.equal(gh.calls[1].init.redirect, "manual");
  // GitHub could not be asked whether the Mac build is attached: no Mac button
  assert.equal(rel.assets.macos, undefined);
});

test("the web fallback offers the Mac build only when its download link exists", async () => {
  const DMG = `https://github.com/${REPO}/releases/download/v0.7.1/2ByteASR-0.7.1-macos-arm64-Setup.dmg`;
  const routes = (dmgStatus) => ({
    [API]: () => json({ message: "API rate limit exceeded" }, 429),
    [WEB]: () => new Response(null, { status: 302, headers: { location: `https://github.com/${REPO}/releases/tag/v0.7.1` } }),
    [DMG]: () => new Response(null, { status: dmgStatus, headers: dmgStatus === 302 ? { location: "https://release-assets.githubusercontent.com/x" } : {} }),
  });
  const gh = github(routes(302));
  const rel = await latestRelease({}, gh.fetchImpl);
  assert.equal(rel.assets.macos.url, DMG);
  const head = gh.calls.find((c) => c.url === DMG);
  assert.equal(head.init.method, "HEAD");
  assert.equal(head.init.redirect, "manual");
  assert.deepEqual(summary(rel).macos, { name: "2ByteASR-0.7.1-macos-arm64-Setup.dmg", size: null });
  const missing = await latestRelease({}, github(routes(404)).fetchImpl);
  assert.equal(missing.assets.macos, undefined);
  assert.ok(missing.assets.windows);
});

test("no published release (or a private repository without a token) means nothing to download", async () => {
  const gh = github({ [API]: () => json({ message: "Not Found" }, 404) });
  assert.equal(await latestRelease({}, gh.fetchImpl), null);
  assert.deepEqual(summary(null), { available: false });
});

test("with a token the visitor gets GitHub's signed link and never the token", async () => {
  const gh = github({
    "https://api.github.com/repos/": () =>
      new Response(null, { status: 302, headers: { location: "https://objects.githubusercontent.com/signed?x=1" } }),
  });
  const rel = { assets: { windows: { url: "https://github.com/x", api: "https://api.github.com/repos/x/assets/1" } } };
  const url = await downloadUrl(rel.assets.windows, { GITHUB_TOKEN: "t0k" }, gh.fetchImpl);
  assert.equal(url, "https://objects.githubusercontent.com/signed?x=1");
  assert.equal(gh.calls[0].init.headers.authorization, "Bearer t0k");
  assert.equal(gh.calls[0].init.headers.accept, "application/octet-stream");
  assert.equal(await downloadUrl(rel.assets.windows, {}, gh.fetchImpl), "https://github.com/x");
});

test("/download/windows redirects to the newest installer", async () => {
  const res = await withFetch(github({ [API]: () => json(RELEASE) }).fetchImpl, () =>
    download({ params: { name: "windows" }, env: {}, request: request("/download/windows") }),
  );
  assert.equal(res.status, 302);
  assert.equal(res.headers.get("location"), `https://github.com/${REPO}/releases/download/v0.6.5/2ByteASR-Setup-0.6.5.exe`);
  assert.equal(res.headers.get("cache-control"), "no-store");
  assert.equal(onRequestHead, download); // HEAD is answered the same way
});

test("/download/windows explains itself in the visitor's language before the first release", async () => {
  const gh = github({ [API]: () => json({ message: "Not Found" }, 404) });
  const zh = await withFetch(gh.fetchImpl, () =>
    download({ params: { name: "windows" }, env: {}, request: request("/download/windows") }),
  );
  assert.equal(zh.status, 404);
  assert.match(await zh.text(), /安装包即将发布/);
  const ja = await withFetch(gh.fetchImpl, () =>
    download({ params: { name: "windows" }, env: {}, request: request("/download/windows?lang=ja", "en") }),
  );
  assert.match(await ja.text(), /<html lang="ja">[\s\S]*href="\/ja#download"/);
  const down = await withFetch(github({}).fetchImpl, () =>
    download({ params: { name: "windows" }, env: {}, request: request("/download/windows", "en-US") }),
  );
  assert.equal(down.status, 503);
  assert.match(await down.text(), /coming soon/);
  const other = await download({ params: { name: "linux" }, env: {}, request: request("/download/linux") });
  assert.equal(other.status, 404);
  const mac = await withFetch(gh.fetchImpl, () =>
    download({ params: { name: "macos" }, env: {}, request: request("/download/macos", "en-US") }),
  );
  assert.equal(mac.status, 404);
  assert.match(await mac.text(), /coming soon/);
});

test("/download/macos redirects to the newest Mac installer", async () => {
  const res = await withFetch(github({ [API]: () => json(RELEASE) }).fetchImpl, () =>
    download({ params: { name: "macos" }, env: {}, request: request("/download/macos") }),
  );
  assert.equal(res.status, 302);
  assert.equal(res.headers.get("location"), `https://github.com/${REPO}/releases/download/v0.6.5/2ByteASR-0.6.5-macos-arm64-Setup.dmg`);
  assert.equal(res.headers.get("cache-control"), "no-store");
});

test("/download/macos says when the newest release has no Mac build", async () => {
  const gh = github({ [API]: () => json(WINDOWS_ONLY) });
  const zh = await withFetch(gh.fetchImpl, () =>
    download({ params: { name: "macos" }, env: {}, request: request("/download/macos") }),
  );
  assert.equal(zh.status, 404);
  const text = await zh.text();
  assert.match(text, /<html lang="zh-CN">[\s\S]*这个版本没有 Mac 安装包[\s\S]*href="\/#download"/);
  assert.doesNotMatch(text, /即将发布/);
  const en = await withFetch(gh.fetchImpl, () =>
    download({ params: { name: "macos" }, env: {}, request: request("/download/macos?lang=en") }),
  );
  assert.match(await en.text(), /No Mac installer in this version/);
  // Windows is untouched by a missing Mac build
  const win = await withFetch(gh.fetchImpl, () =>
    download({ params: { name: "windows" }, env: {}, request: request("/download/windows") }),
  );
  assert.equal(win.status, 302);
});

test("/api/release labels the button, and says when GitHub could not be asked", async () => {
  const ok = await withFetch(github({ [API]: () => json(RELEASE) }).fetchImpl, () => releaseApi({ env: {} }));
  const body = await ok.json();
  assert.equal(body.windows.size, 1009166375);
  assert.equal(body.macos.size, 546572457);
  assert.match(ok.headers.get("cache-control"), /max-age=300/);
  const none = await withFetch(github({ [API]: () => json({}, 404) }).fetchImpl, () => releaseApi({ env: {} }));
  assert.deepEqual(await none.json(), { available: false });
  const down = await withFetch(github({}).fetchImpl, () => releaseApi({ env: {} }));
  assert.deepEqual(await down.json(), { available: null });
  assert.equal(down.headers.get("cache-control"), "no-store");
});

test("each language page links the Mac installer with its own note", () => {
  const read = (p) => fs.readFileSync(new URL(p, import.meta.url), "utf8");
  // esbuild writes non-ASCII text as \uXXXX escapes; decode before looking at characters.
  const decode = (s) => s.replace(/\\u\{([0-9a-f]+)\}|\\u([0-9a-f]{4})/gi, (_, a, b) => String.fromCodePoint(parseInt(a || b, 16)));
  for (const [file, copy] of [["product.js", zh], ["product-en.js", en], ["product-ja.js", ja]]) {
    const js = decode(read(`../product-build/${file}`));
    assert.ok(js.includes("/download/macos"), file);
    assert.ok(js.includes(copy.download.mac) && js.includes(copy.download.macNote), file);
    assert.match(copy.download.macNote, /macOS 15[\s\S]*Control/, file);
  }
});

// GitCode mirror (mainland China). 2026-10-14: github.com downloads failed on a
// mainland line while GitCode served the same files at ~14 MB/s.
const GITCODE_TAG = "https://api.gitcode.com/api/v5/repos/Notbad314/2ByteASR/releases/tags/v0.6.5";
const GITCODE_FILE = "https://gitcode.com/Notbad314/2ByteASR/releases/download/v0.6.5/";
const mirrored = (names, tag = "v0.6.5") => () =>
  json({ tag_name: tag, assets: names.map((name) => ({ name, browser_download_url: GITCODE_FILE + name })) });
const visitor = (path, country) => {
  const req = request(path);
  if (country) Object.defineProperty(req, "cf", { value: { country } });
  return req;
};
const go = (routes, name, req) =>
  withFetch(github(routes).fetchImpl, () => download({ params: { name }, env: {}, request: req }));

test("visitors in mainland China get the identical installer from GitCode", async () => {
  const routes = { [API]: () => json(RELEASE), [GITCODE_TAG]: mirrored(["2ByteASR-Setup-0.6.5.exe", "2ByteASR-0.6.5-macos-arm64-Setup.dmg"]) };
  const win = await go(routes, "windows", visitor("/download/windows", "CN"));
  assert.equal(win.status, 302);
  assert.equal(win.headers.get("location"), GITCODE_FILE + "2ByteASR-Setup-0.6.5.exe");
  const mac = await go(routes, "macos", visitor("/download/macos", "CN"));
  assert.equal(mac.headers.get("location"), GITCODE_FILE + "2ByteASR-0.6.5-macos-arm64-Setup.dmg");
  const elsewhere = await go(routes, "windows", visitor("/download/windows", "JP"));
  assert.equal(elsewhere.headers.get("location"), `https://github.com/${REPO}/releases/download/v0.6.5/2ByteASR-Setup-0.6.5.exe`);
});

test("?source= picks the mirror explicitly in either direction", async () => {
  const routes = { [API]: () => json(RELEASE), [GITCODE_TAG]: mirrored(["2ByteASR-Setup-0.6.5.exe"]) };
  const chosen = await go(routes, "windows", visitor("/download/windows?source=gitcode", "US"));
  assert.equal(chosen.headers.get("location"), GITCODE_FILE + "2ByteASR-Setup-0.6.5.exe");
  const github_ = await go(routes, "windows", visitor("/download/windows?source=github", "CN"));
  assert.match(github_.headers.get("location"), /^https:\/\/github\.com\//);
});

test("a GitCode mirror that lags or fails never serves an old or missing file", async () => {
  const gh = `https://github.com/${REPO}/releases/download/v0.6.5/2ByteASR-Setup-0.6.5.exe`;
  const older = await go({ [API]: () => json(RELEASE), [GITCODE_TAG]: mirrored(["2ByteASR-Setup-0.6.4.exe"], "v0.6.4") },
    "windows", visitor("/download/windows", "CN"));
  assert.equal(older.headers.get("location"), gh);
  const missing = await go({ [API]: () => json(RELEASE), [GITCODE_TAG]: mirrored(["SHA256SUMS.txt"]) },
    "windows", visitor("/download/windows", "CN"));
  assert.equal(missing.headers.get("location"), gh);
  const down = await go({ [API]: () => json(RELEASE) }, "windows", visitor("/download/windows", "CN"));
  assert.equal(down.headers.get("location"), gh);
  const head = await withFetch(github({ [API]: () => json(RELEASE), [GITCODE_TAG]: mirrored(["2ByteASR-Setup-0.6.5.exe"]) }).fetchImpl,
    () => onRequestHead({ params: { name: "windows" }, env: {}, request: visitor("/download/windows", "CN") }));
  assert.equal(head.headers.get("location"), GITCODE_FILE + "2ByteASR-Setup-0.6.5.exe");
});

test("each language page offers the GitCode links", () => {
  const read = (p) => fs.readFileSync(new URL(p, import.meta.url), "utf8");
  const decode = (s) => s.replace(/\\u\{([0-9a-f]+)\}|\\u([0-9a-f]{4})/gi, (_, a, b) => String.fromCodePoint(parseInt(a || b, 16)));
  for (const [file, copy] of [["product.js", zh], ["product-en.js", en], ["product-ja.js", ja]]) {
    const js = decode(read(`../product-build/${file}`));
    assert.ok(js.includes("?source=gitcode"), file);
    for (const key of ["mirror", "mirrorWindows", "mirrorMac"]) assert.ok(js.includes(copy.download[key]), `${file} ${key}`);
  }
});
