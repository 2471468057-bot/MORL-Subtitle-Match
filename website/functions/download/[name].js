// SPDX-License-Identifier: GPL-3.0-only
// /download/windows, /download/macos -> that installer of the newest published
// GitHub Release.
import { ASSETS, downloadUrl, latestRelease } from "../../server/latest-release.js";

const PENDING = {
  zh: ["安装包即将发布", "现在还没有公开的版本。请稍后再来，或先看看产品介绍。", "返回官网", "zh-CN", "/"],
  en: ["The installer is coming soon", "No version has been released yet. Please check back later.", "Back to the site", "en", "/en"],
  ja: ["インストーラーは近日公開", "まだ公開されたバージョンはありません。しばらくしてからもう一度お試しください。", "サイトに戻る", "ja", "/ja"],
};
// The Mac build is experimental and not attached to every release.
const NO_MAC = {
  zh: ["这个版本没有 Mac 安装包", "最新版本暂未提供 macOS 安装包。Mac 版是实验支持，不一定每个版本都有；Windows 版照常可以下载。", "返回官网", "zh-CN", "/"],
  en: ["No Mac installer in this version", "The latest version has no macOS installer. The Mac build is experimental and not part of every release; the Windows installer is available as usual.", "Back to the site", "en", "/en"],
  ja: ["このバージョンには Mac 版がありません", "最新バージョンには macOS 用インストーラーがありません。Mac 版は実験的サポートのため、すべてのバージョンに付くわけではありません。Windows 版はいつもどおりダウンロードできます。", "サイトに戻る", "ja", "/ja"],
};

function language(request) {
  const q = new URL(request.url).searchParams.get("lang");
  if (q in PENDING) return q;
  const accept = (request.headers.get("accept-language") || "").toLowerCase();
  if (accept.startsWith("ja")) return "ja";
  if (accept.startsWith("zh")) return "zh";
  return accept ? "en" : "zh";
}

function pending(request, status, pages = PENDING) {
  const [title, body, back, lang, home] = pages[language(request)];
  const html = `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><title>${title} · 2ByteASR</title><link rel="icon" href="/assets/brand-256.png"><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#121015;color:#f4eee9;font:17px/1.7 system-ui,sans-serif}main{max-width:34rem;padding:32px}h1{font-size:28px;margin:0 0 8px}p{color:#b9b0aa;margin:0 0 24px}a{color:#121015;background:#e58aa8;padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600}</style></head><body><main><h1>${title}</h1><p>${body}</p><a href="${home}#download">${back}</a></main></body></html>`;
  return new Response(html, {
    status,
    headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
  });
}

export async function onRequestGet({ params, env, request }) {
  const name = String(params.name || "");
  if (!Object.hasOwn(ASSETS, name)) return new Response("Not found", { status: 404 });
  let rel;
  try {
    rel = await latestRelease(env);
  } catch {
    return pending(request, 503);
  }
  const asset = rel?.assets[name];
  if (!asset) return pending(request, 404, name === "macos" && rel?.assets.windows ? NO_MAC : PENDING);
  return new Response(null, {
    status: 302,
    headers: { location: await downloadUrl(asset, env), "cache-control": "no-store" },
  });
}

// Download managers often ask with HEAD first; without this the request would
// fall through to the static site and get the home page.
export const onRequestHead = onRequestGet;
