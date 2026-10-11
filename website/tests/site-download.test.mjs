// Download routes (Pages Functions) against a stubbed GitHub.
import test from "node:test";
import assert from "node:assert/strict";
import { downloadUrl, latestRelease, summary } from "../server/latest-release.js";
import { onRequestGet as download } from "../functions/download/[name].js";
import { onRequestGet as releaseApi } from "../functions/api/release.js";

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
    asset("SHA256SUMS.txt"),
  ],
};
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

test("only the published latest release is asked for, and its own installer is picked", async () => {
  const gh = github({ [API]: () => json(RELEASE) });
  const rel = await latestRelease({}, gh.fetchImpl);
  assert.equal(gh.calls[0].url, API); // releases/latest never returns drafts or pre-releases
  assert.equal(rel.version, "0.6.5");
  assert.equal(rel.assets.windows.name, "2ByteASR-Setup-0.6.5.exe");
  assert.deepEqual(summary(rel), {
    available: true,
    version: "0.6.5",
    tag: "v0.6.5",
    published: "2026-10-12T00:00:00Z",
    notes: RELEASE.html_url,
    windows: { name: "2ByteASR-Setup-0.6.5.exe", size: 1009166375 },
  });
});

test("a release without an installer is not offered", async () => {
  const gh = github({ [API]: () => json({ ...RELEASE, assets: [asset("SHA256SUMS.txt")] }) });
  const rel = await latestRelease({}, gh.fetchImpl);
  assert.equal(rel.assets.windows, undefined);
  assert.equal(summary(rel).available, false);
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
});

test("/api/release labels the button, and says when GitHub could not be asked", async () => {
  const ok = await withFetch(github({ [API]: () => json(RELEASE) }).fetchImpl, () => releaseApi({ env: {} }));
  assert.equal((await ok.json()).windows.size, 1009166375);
  assert.match(ok.headers.get("cache-control"), /max-age=300/);
  const none = await withFetch(github({ [API]: () => json({}, 404) }).fetchImpl, () => releaseApi({ env: {} }));
  assert.deepEqual(await none.json(), { available: false });
  const down = await withFetch(github({}).fetchImpl, () => releaseApi({ env: {} }));
  assert.deepEqual(await down.json(), { available: null });
  assert.equal(down.headers.get("cache-control"), "no-store");
});
