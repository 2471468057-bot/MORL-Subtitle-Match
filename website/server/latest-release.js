// SPDX-License-Identifier: GPL-3.0-only
// Finds the desktop app's newest published GitHub Release for the site's
// download buttons (Cloudflare Pages Functions in ../functions). GitHub's
// releases/latest only returns a published, non-prerelease release, so drafts
// are never served.
//
// env.GITHUB_REPO   owner/name, defaults to the app repository
// env.GITHUB_TOKEN  optional read-only token: raises the API rate limit and
//                   lets a published release of a private repository download

export const DEFAULT_REPO = "NOTBAD314/2ByteASR";

// Download name -> release attachment. The installers are named after the
// version (2ByteASR-Setup-0.7.1.exe, 2ByteASR-0.7.1-macos-arm64-Setup.dmg);
// `file` builds that name from a tag when only the tag is known. `optional`
// attachments are not in every release (the Mac build is experimental), so
// that fallback first asks whether the file is there.
export const ASSETS = {
  windows: {
    match: /^2ByteASR-Setup-[\w.+-]+\.exe$/i,
    file: (version) => `2ByteASR-Setup-${version}.exe`,
  },
  macos: {
    match: /^2ByteASR-[\w.+-]+-macos-arm64-Setup\.dmg$/i,
    file: (version) => `2ByteASR-${version}-macos-arm64-Setup.dmg`,
    optional: true,
  },
};

const UA = "2byteasr-site";
const versionOf = (tag) => String(tag).replace(/^v/i, "");

function apiHeaders(token, accept = "application/vnd.github+json") {
  const h = { accept, "user-agent": UA, "x-github-api-version": "2022-11-28" };
  if (token) h.authorization = `Bearer ${token}`;
  return h;
}

function pick(assets, name, version) {
  const found = assets.filter((a) => ASSETS[name].match.test(a.name));
  return found.find((a) => a.name === ASSETS[name].file(version)) || found[0];
}

function fromApi(repo, rel) {
  const version = versionOf(rel.tag_name);
  const assets = {};
  for (const name of Object.keys(ASSETS)) {
    const a = pick(rel.assets || [], name, version);
    if (a) assets[name] = { name: a.name, size: a.size, url: a.browser_download_url, api: a.url };
  }
  return {
    repo,
    tag: rel.tag_name,
    version,
    published: rel.published_at || null,
    notes: rel.html_url,
    assets,
  };
}

// The web page /releases/latest redirects to /releases/tag/<tag> without
// touching the API rate limit; attachment names then follow the convention.
async function fromWeb(repo, fetchImpl) {
  const res = await fetchImpl(`https://github.com/${repo}/releases/latest`, {
    redirect: "manual",
    headers: { "user-agent": UA },
  });
  const tag = (res.headers.get("location") || "").match(/\/releases\/tag\/([^/?#]+)$/)?.[1];
  if (res.status < 300 || res.status >= 400 || !tag) return null;
  const decoded = decodeURIComponent(tag);
  const version = versionOf(decoded);
  const base = `https://github.com/${repo}/releases/download/${tag}/`;
  const assets = {};
  for (const [name, spec] of Object.entries(ASSETS)) {
    const file = spec.file(version);
    const url = base + encodeURIComponent(file);
    if (spec.optional && !(await attached(url, fetchImpl))) continue;
    assets[name] = { name: file, size: null, url, api: null };
  }
  return { repo, tag: decoded, version, published: null, notes: `https://github.com/${repo}/releases/tag/${tag}`, assets };
}

// An attachment's download link redirects to the file; a missing one is 404.
async function attached(url, fetchImpl) {
  try {
    const res = await fetchImpl(url, { method: "HEAD", redirect: "manual", headers: { "user-agent": UA } });
    return res.status >= 300 && res.status < 400;
  } catch {
    return false;
  }
}

// Newest published release, or null when there is none (or the repository is
// private and no token is set). Throws only when GitHub cannot be reached.
export async function latestRelease(env = {}, fetchImpl = fetch) {
  const repo = env.GITHUB_REPO || DEFAULT_REPO;
  const token = env.GITHUB_TOKEN || "";
  const res = await fetchImpl(`https://api.github.com/repos/${repo}/releases/latest`, {
    headers: apiHeaders(token),
    cf: { cacheTtl: 300, cacheEverything: true },
  });
  if (res.ok) return fromApi(repo, await res.json());
  if (res.status === 404) return null;
  // Rate limited (403/429) or an API outage: the web redirect still names the tag.
  return fromWeb(repo, fetchImpl);
}

// Where to send the visitor for one attachment. With a token the API hands
// out a short-lived signed link, which also works for a private repository.
export async function downloadUrl(asset, env = {}, fetchImpl = fetch) {
  if (env.GITHUB_TOKEN && asset.api) {
    const res = await fetchImpl(asset.api, {
      redirect: "manual",
      headers: apiHeaders(env.GITHUB_TOKEN, "application/octet-stream"),
    });
    const signed = res.headers.get("location");
    if (res.status >= 300 && res.status < 400 && signed) return signed;
  }
  return asset.url;
}

// GitCode carries every release file under the same tag and name (the release
// script's `gitcode` step). Measured 2026-10-14 on a mainland line without a
// proxy: github.com downloads failed outright, GitCode gave ~14 MB/s.
export const GITCODE_REPO = "Notbad314/2ByteASR";

// Visitors in mainland China get GitCode; ?source=gitcode|github overrides.
export function preferredSource(request) {
  const asked = new URL(request.url).searchParams.get("source");
  if (asked === "gitcode" || asked === "github") return asked;
  return request.cf?.country === "CN" ? "gitcode" : "github";
}

// The GitCode copy of `rel`'s attachment `name`, or null while GitCode does not
// have that very tag and file (a mirror that lags never serves an old version).
export async function gitcodeAsset(rel, name, env = {}, fetchImpl = fetch) {
  const asset = rel?.assets?.[name];
  if (!asset) return null;
  const repo = env.GITCODE_REPO || GITCODE_REPO;
  try {
    const res = await fetchImpl(
      `https://api.gitcode.com/api/v5/repos/${repo}/releases/tags/${encodeURIComponent(rel.tag)}`,
      { headers: { accept: "application/json", "user-agent": UA }, cf: { cacheTtl: 300, cacheEverything: true } },
    );
    if (!res.ok) return null;
    const mirror = await res.json();
    if (mirror?.tag_name !== rel.tag || !(mirror.assets || []).some((a) => a.name === asset.name)) return null;
    return {
      name: asset.name,
      size: asset.size,
      url: `https://gitcode.com/${repo}/releases/download/${encodeURIComponent(rel.tag)}/${encodeURIComponent(asset.name)}`,
    };
  } catch {
    return null;
  }
}

// What the page needs to label its buttons. `available` follows the Windows
// installer; `macos` is null when this release has no Mac build.
export function summary(rel) {
  if (!rel) return { available: false };
  const label = (a) => (a ? { name: a.name, size: a.size } : null);
  return {
    available: Boolean(rel.assets.windows),
    version: rel.version,
    tag: rel.tag,
    published: rel.published,
    notes: rel.notes,
    windows: label(rel.assets.windows),
    macos: label(rel.assets.macos),
  };
}
