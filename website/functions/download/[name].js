// SPDX-License-Identifier: GPL-3.0-only
// /download/windows -> the installer of the newest published GitHub Release.
import { ASSETS, downloadUrl, latestRelease } from "../../server/latest-release.js";

const PENDING = {
  zh: ["安装包即将发布", "现在还没有公开的版本。请稍后再来，或先看看产品介绍。", "返回官网", "zh-CN", "/"],
  en: ["The installer is coming soon", "No version has been released yet. Please check back later.", "Back to the site", "en", "/en"],
  ja: ["インストーラーは近日公開", "まだ公開されたバージョンはありません。しばらくしてからもう一度お試しください。", "サイトに戻る", "ja", "/ja"],
};

function language(request) {
  const q = new URL(request.url).searchParams.get("lang");
  if (q in PENDING) return q;
  const accept = (request.headers.get("accept-language") || "").toLowerCase();
  if (accept.startsWith("ja")) return "ja";
  if (accept.startsWith("zh")) return "zh";
  return accept ? "en" : "zh";
}

function pending(request, status) {
  const [title, body, back, lang, home] = PENDING[language(request)];
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
  if (!asset) return pending(request, 404);
  return new Response(null, {
    status: 302,
    headers: { location: await downloadUrl(asset, env), "cache-control": "no-store" },
  });
}
