// Real-browser acceptance for the product pages (zh, en, ja), through Chrome
// DevTools Protocol (system Chrome or Edge; no npm packages). Start
// `npm run preview` first.
//   node scripts/verify-product.mjs
// PRODUCT_URL (default http://127.0.0.1:4175/), PRODUCT_EVIDENCE (output dir),
// CHROME (browser path). Writes screenshots and verify.json to the evidence dir.
import { spawn } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = process.env.PRODUCT_EVIDENCE || path.join(root, "../tmp/product-page-verify");
const base = process.env.PRODUCT_URL || "http://127.0.0.1:4175/";
const chrome =
  process.env.CHROME ||
  ["C:/Program Files/Google/Chrome/Application/chrome.exe", "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"].find(existsSync);
const charset = readFileSync(path.join(root, "product/fonts/charset.txt"), "utf8");
await fs.mkdir(out, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const profile = await fs.mkdtemp(path.join(os.tmpdir(), "2byte-verify-"));
const port = 9500 + Math.floor(Math.random() * 300);
const proc = spawn(chrome, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--hide-scrollbars", "--no-first-run", "--force-color-profile=srgb", "about:blank"], { stdio: "ignore" });
let targets = [];
for (let i = 0; i < 80 && !targets.length; i++) {
  try { targets = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).filter((t) => t.type === "page"); } catch {}
  await sleep(250);
}
const ws = new WebSocket(targets[0].webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let seq = 0;
const pending = new Map(), errors = [], external = [];
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id) pending.get(m.id)?.(m), pending.delete(m.id);
  if (m.method === "Runtime.exceptionThrown") errors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
  if (m.method === "Runtime.consoleAPICalled" && m.params.type === "error") errors.push(m.params.args.map((a) => a.value ?? a.description).join(" "));
  if (m.method === "Network.requestWillBeSent") {
    const u = m.params.request.url;
    if (/^https?:/.test(u) && !u.startsWith(new URL(base).origin)) external.push(u);
  }
});
const send = (method, params = {}) => new Promise((r) => { const id = ++seq; pending.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
const js = async (expr) => {
  const r = await send("Runtime.evaluate", { expression: `(async()=>{${expr}})()`, awaitPromise: true, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || expr);
  return r.result?.result?.value;
};
const viewport = (w, h, reduced = false) =>
  Promise.all([
    send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 700 }),
    send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: reduced ? "reduce" : "no-preference" }] }),
  ]);
const open = async (page) => { await send("Page.navigate", { url: new URL(page, base).href }); await sleep(1800); };
const snap = async (name) => {
  const s = await send("Page.captureScreenshot", { format: "png" });
  await fs.writeFile(path.join(out, name + ".png"), Buffer.from(s.result.data, "base64"));
};
const to = (sel, offset = 90) => js(`const e=document.querySelector(${JSON.stringify(sel)});scrollTo({top:e.getBoundingClientRect().top+scrollY-${offset},behavior:'instant'});`);
const checks = [];
const check = (name, data = true) => { checks.push({ name, data }); console.log("PASS", name, JSON.stringify(data)); };

// What each page shows at the checkpoints of its demonstrations.
const PAGES = {
  zh: {
    page: "index.html", html: "zh-CN", adopted: /已采用候选 2/, done: /已完成/, written: /已写回 3 处/, rendered: /压制完成/,
    third: /战术/, clips: ["再一起去山顶", "看看有没有新的任务，"],
    applied: /已写回/, speed: "速度优先", quality: "质量优先", off: "已关闭", removed: "AI 字幕设计",
  },
  en: {
    page: "en.html", html: "en", adopted: /Candidate 2 accepted/, done: /Completed/, written: /3 changes applied/, rendered: /Export complete/,
    third: /positions/, clips: ["Then we'll all go to the hilltop", "and check for any new missions,"],
    applied: /applied/, speed: "Speed first", quality: "Quality first", off: "Off", removed: "AI Subtitle Design",
  },
  ja: {
    page: "ja.html", html: "ja", adopted: /候補 2 を採用/, done: /完了/, written: /3 件を反映済み/, rendered: /書き出し完了/,
    third: /戦術/, clips: ["それからみんなで山頂へ行こう、", "何かないかな、新しい任務。"],
    applied: /反映済み/, speed: "速度優先", quality: "品質優先", off: "オフ", removed: "AI字幕デザイン",
  },
};

async function verify(lang) {
  const P = PAGES[lang];
  const tag = (s) => `[${lang}] ${s}`;
  await viewport(1440, 900);
  await open(P.page);
  await snap(`${lang}-hero-1440`);
  // language: the page, its title and the three language links
  const meta = await js(`return {lang:document.documentElement.lang,title:document.title,links:[...document.querySelectorAll('.site-nav .lang-switch a')].map(a=>[a.getAttribute('href'),a.getAttribute('aria-current')]),alternates:document.querySelectorAll('link[rel=alternate][hreflang]').length}`);
  assert.equal(meta.lang, P.html);
  assert.deepEqual(meta.links.map((l) => l[0]), ["./index.html", "./en.html", "./ja.html"]);
  assert.equal(meta.links.find((l) => l[1] === "page")[0], "./" + P.page);
  assert.equal(meta.alternates, 3);
  check(tag("page language, title, hreflang and language links"), meta);

  // hero: two real screens of the app in one 3D group that leans toward the pointer
  const hero = await js(`return {studio:!!document.querySelector('.stage .studio-app'),home:!!document.querySelector('.stage .home-win'),width:Math.round(document.querySelector('.stage').getBoundingClientRect().width),h1:document.querySelector('h1').getClientRects().length,h1h:Math.round(document.querySelector('h1').getBoundingClientRect().height)}`);
  assert.equal(hero.studio && hero.home, true);
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1400, y: 120 });
  await sleep(900);
  const right = await js(`return getComputedStyle(document.querySelector('.stage-3d')).getPropertyValue('--ry')`);
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 30, y: 860 });
  await sleep(900);
  const left = await js(`return getComputedStyle(document.querySelector('.stage-3d')).getPropertyValue('--ry')`);
  assert.ok(parseFloat(right) > 2 && parseFloat(left) < -2, JSON.stringify({ right, left }));
  check(tag("hero stage shows Studio + home windows and tilts with the mouse"), { ...hero, right, left });

  // nothing in the interface replicas sticks out of its window
  const outside = await js(`const bad=[];for(const app of document.querySelectorAll('.app:not(.studio-app)')){const ar=app.getBoundingClientRect();if(!ar.width)continue;for(const el of app.querySelectorAll('*')){if(el.closest('svg')||el.children.length||!el.textContent.trim())continue;const r=el.getBoundingClientRect();if(r.width&&(r.right>ar.right+1||r.left<ar.left-1))bad.push(el.textContent.trim().slice(0,30))}}return bad`);
  assert.deepEqual(outside, []);
  check(tag("no interface text runs outside its window"), outside.length);

  // the difference, before / after
  await to("#compare", 20); await sleep(600);
  const cmp = await js(`return {bad:document.querySelectorAll('.cmp-raw u').length,rows:document.querySelectorAll('.cmp-rows li').length,first:document.querySelector('.cmp-rows .cmp-text').textContent,keys:[...document.querySelectorAll('.cmp-keys b')].map(b=>b.textContent)}`);
  assert.equal(cmp.rows, 5); assert.equal(cmp.keys.length, 4); assert.equal(cmp.bad, 3);
  await snap(`${lang}-compare`);
  check(tag("before/after comparison, subtitles in the page language"), cmp);

  // 候选 / 优先审核: plays to "candidate 2 adopted"; the visitor can adopt candidate 3
  await to("#review", 20); await sleep(5200);
  assert.match(await js(`return document.querySelector('.rv-saved').textContent`), P.adopted);
  await snap(`${lang}-review`);
  await js(`document.querySelectorAll('.rv-card')[2].click()`); await sleep(300);
  const cap = await js(`return document.querySelector('.rv-cap').textContent`);
  const row = await js(`return document.querySelector('.rv-row').textContent`);
  assert.match(cap, P.third); assert.match(row, P.done);
  check(tag("candidate review: adopting candidate 3 updates the caption and marks the cue done"), cap);

  // AI 词库校对: only checked suggestions are written back
  await to("#proofread", 20); await sleep(4600);
  const pf = await js(`return {btn:document.querySelector('.pf-foot .app-btn').textContent,done:document.querySelectorAll('.pf-item.is-done').length,off:document.querySelectorAll('.pf-item.is-off').length}`);
  assert.match(pf.btn, P.written); assert.equal(pf.done, 3); assert.equal(pf.off, 1);
  assert.equal(await js(`return document.querySelector('#review .pf')`), null);
  await snap(`${lang}-proofread`);
  check(tag("AI proofread writes back the 3 checked terms, leaves the unchecked one"), pf);

  // 术语库: confirming a reference term moves the counts
  await to("#glossary", 20); await sleep(500);
  await js(`document.querySelector('#glossary .demo').dispatchEvent(new PointerEvent('pointerenter',{pointerType:'mouse'}))`);
  const g0 = await js(`return document.querySelector('.gl-head').textContent`);
  await js(`document.querySelector('.gl-confirm').click()`); await sleep(300);
  const g1 = await js(`return document.querySelector('.gl-head').textContent`);
  assert.notEqual(g0, g1);
  await snap(`${lang}-glossary`);
  check(tag("glossary: confirming a reference term updates the counts"), { g0, g1 });

  // 字级时间轴 / 分轨: two speaker lanes, a word row, and a razor at a word edge
  await to("#timing .demo", 120); await sleep(800);
  const tm = await js(`return {lanes:document.querySelectorAll('.tm-row .dot').length,words:document.querySelectorAll('.tm-word').length}`);
  assert.deepEqual(tm, { lanes: 2, words: 8 });
  await js(`document.querySelectorAll('.tm-bar .sd-tools button')[0].click()`); await sleep(400);
  const clips = await js(`return [...document.querySelectorAll('.tm-clip.s0')].map(e=>e.textContent)`);
  assert.ok(P.clips.every((c) => clips.includes(c)), JSON.stringify(clips));
  await snap(`${lang}-timing`);
  check(tag("timing: 2 speaker lanes, 8 word blocks, the razor cut gives two joined cues"), { tm, clips });

  // 导出与压制
  await to("#export", 20); await sleep(7200);
  const ex = await js(`return {head:document.querySelector('.ex-rhead').textContent,toast:document.querySelector('.ex-toast')?.textContent||''}`);
  assert.match(ex.head, P.rendered);
  await snap(`${lang}-export`);
  check(tag("export: subtitle files exported, video render completes"), ex);

  // every demo uses the same frame size
  const sizes = await js(`return [...document.querySelectorAll('.demo .app-frame')].map(f=>{const r=f.getBoundingClientRect();return Math.round(r.width)+'x'+Math.round(r.height)})`);
  assert.equal(new Set(sizes).size, 1, JSON.stringify(sizes));
  check(tag("all five demos render at the same size"), sizes);

  // removed content stays removed
  const gone = await js(`return {ai:document.body.textContent.includes(${JSON.stringify(P.removed)}),iframe:document.querySelectorAll('iframe').length,scene:document.querySelectorAll('.scene,.hud').length,eyebrow:document.querySelectorAll('.eyebrow').length,emdash:document.body.textContent.includes('—')}`);
  assert.deepEqual(gone, { ai: false, iframe: 0, scene: 0, eyebrow: 0, emdash: false });
  check(tag("AI subtitle design and the cartoon frame are gone; no eyebrows or em dashes"), gone);

  // 免费本地 · 模型
  await to("#models", 20); await sleep(500);
  const roles = () => js(`return [...document.querySelectorAll('.plan-roles .role-model')].map(e=>e.textContent)`);
  await js(`[...document.querySelectorAll('.goal')].find(b=>b.textContent.includes(${JSON.stringify(P.speed)})).click()`); await sleep(400);
  assert.deepEqual(await roles(), ["SenseVoice", P.off, P.off]);
  await js(`[...document.querySelectorAll('.goal')].find(b=>b.textContent.includes(${JSON.stringify(P.quality)})).click()`); await sleep(400);
  assert.deepEqual(await roles(), ["MOSS", "FireRed", "Qwen3-ASR"]);
  await js(`document.querySelector('.models-all').click()`); await sleep(400);
  const all = await js(`return document.querySelectorAll('.mcard').length`);
  assert.equal(all, 18);
  await js(`document.querySelectorAll('.mcard-more').forEach(b=>b.click())`); await sleep(300);

  // language hygiene, with every model card opened: English text carries no
  // Chinese (the brand name aside); anything marked Chinese is inside the font subset
  const text = await js(`const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);const loose=[],zh=[];while(w.nextNode()){const n=w.currentNode,t=n.textContent;if(!t.trim()||!n.parentElement.offsetParent&&n.parentElement.tagName!=='NOSCRIPT')continue;const owner=n.parentElement.closest('[lang]').lang;if(owner.startsWith('zh'))zh.push(t);else if(owner===document.documentElement.lang&&(/[\\u3400-\\u9fff]/.test(t)))loose.push(t.trim().slice(0,40))}const attrs=[...document.querySelectorAll('[placeholder]')].map(e=>e.placeholder);return {loose:[...new Set(loose)],zh:zh.join(''),kana:/[\\u3040-\\u30ff]/.test(document.body.textContent),attrs}`);
  const missing = [...new Set(text.zh)].filter((c) => c.charCodeAt(0) > 0x2e7f && !charset.includes(c));
  assert.deepEqual(missing, [], "Chinese sample characters outside the font subset");
  if (lang === "en") {
    assert.deepEqual(text.loose, [], "untranslated Chinese on the English page");
    assert.ok(!text.attrs.some((a) => /[\u3400-\u9fff]/.test(a)));
  }
  if (lang === "ja") assert.ok(text.kana);
  check(tag("plans map to role cards; 18 models; no stray Chinese on the English page"), { all, loose: text.loose.length, markedChinese: text.zh.length });

  // phone width and reduced motion
  await viewport(390, 844);
  await open(P.page);
  const width = await js(`return document.documentElement.scrollWidth`);
  assert.equal(width, 390);
  await snap(`${lang}-hero-390`);
  check(tag("no horizontal scroll at 390 px"), width);
  await viewport(1440, 900, true);
  await open(P.page);
  await to("#proofread", 20); await sleep(800);
  const still = await js(`return {reduced:document.querySelector('#root>div').classList.contains('reduced'),proofread:document.querySelector('.pf-foot .app-btn').textContent}`);
  assert.equal(still.reduced, true);
  assert.match(still.proofread, P.applied);
  check(tag("reduced motion shows finished states"), still);
}

await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable");
try {
  for (const lang of Object.keys(PAGES)) await verify(lang);
  // the offline single files link to each other
  await viewport(1440, 900);
  for (const [lang, file] of [["zh", "portable.html"], ["en", "portable-en.html"], ["ja", "portable-ja.html"]]) {
    await open(file);
    const p = await js(`return {lang:document.documentElement.lang,links:[...document.querySelectorAll('.site-nav .lang-switch a')].map(a=>a.getAttribute('href')),stage:!!document.querySelector('.stage .studio-app'),css:document.querySelectorAll('link[rel=stylesheet]').length}`);
    assert.equal(p.lang, PAGES[lang].html);
    assert.deepEqual(p.links, ["./portable.html", "./portable-en.html", "./portable-ja.html"]);
    assert.equal(p.stage, true); assert.equal(p.css, 0);
    check(`[${lang}] ${file} renders offline and links to the other offline files`, p);
  }
  assert.deepEqual(errors, [], "page errors");
  assert.deepEqual(external, [], "external requests");
  check("no page errors and no external requests");
} finally {
  await fs.writeFile(path.join(out, "verify.json"), JSON.stringify({ date: new Date().toISOString(), base, checks, errors, external }, null, 2));
  ws.close();
  proc.kill();
  await sleep(300);
  await fs.rm(profile, { recursive: true, force: true }).catch(() => {});
}
console.log(`${checks.length} checks passed · evidence in ${out}`);
