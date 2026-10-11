// SPDX-License-Identifier: GPL-3.0-only
// Finds the desktop app's newest published GitHub Release for the site's
// download button (Cloudflare Pages Functions in ../functions). GitHub's
// releases/latest only returns a published, non-prerelease release, so drafts
// are never served.
//
// env.GITHUB_REPO   owner/name, defaults to the app repository
// env.GITHUB_TOKEN  optional read-only token: raises the API rate limit and
//                   lets a published release of a private repository download

export const DEFAULT_REPO = "NOTBAD314/2ByteASR";

// Download name -> release attachment. The installer is named after the
// version (2ByteASR-Setup-0.6.5.exe); `file` builds that name from a tag when
// only the tag is known.
export const ASSETS = {
  windows: {
    match: /^2ByteASR-Setup-[\w.+-]+\.exe$/i,
    file: (version) => `2ByteASR-Setup-${version}.exe`,
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
    assets[name] = { name: file, size: null, url: base + encodeURIComponent(file), api: null };
  }
  return { repo, tag: decoded, version, published: null, notes: `https://github.com/${repo}/releases/tag/${tag}`, assets };
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

// What the page needs to label its button.
export function summary(rel) {
  if (!rel) return { available: false };
  const setup = rel.assets.windows;
  return {
    available: Boolean(setup),
    version: rel.version,
    tag: rel.tag,
    published: rel.published,
    notes: rel.notes,
    windows: setup ? { name: setup.name, size: setup.size } : null,
  };
}
