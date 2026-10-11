// Render the repository product README for local review, never website/README.
import fs from 'node:fs/promises';
import path from 'node:path';
const {marked}=await import(process.env.MARKED_MODULE||'marked');
const root=path.resolve('.'),out=path.resolve(process.env.README_PREVIEW||'releases/daily-20260930');
const source=process.env.README_SOURCE||'README.md',lang=process.env.README_LANG||'zh-CN';
const prefix=process.env.README_PREVIEW_PREFIX||'readme';
const title=lang==='en'?'2ByteASR · Product overview':lang==='ja'?'2ByteASR · 製品紹介':'兔白字幕 · 中文产品介绍';
const base=path.relative(out,root).replaceAll('\\','/')+'/';
await fs.mkdir(out,{recursive:true});
let html=marked.parse(await fs.readFile(path.join(root,source),'utf8'));
html=html.replace(/<h([1-6])>(.*?)<\/h\1>/g,(all,n,title)=>`<h${n} id="${title.replace(/<[^>]*>/g,'').toLowerCase().replace(/[^\p{L}\p{N}\s_-]/gu,'').replace(/\s/g,'-')}">${title}</h${n}>`);
const css=`*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif}main{max-width:896px;margin:24px auto;padding:32px;border:1px solid var(--border);border-radius:6px}h1,h2,h3{line-height:1.3;margin:24px 0 16px}h1{font-size:2em}h2{font-size:1.5em}h1,h2{padding-bottom:.3em;border-bottom:1px solid var(--border)}a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}p{margin:0 0 16px}img{max-width:100%;height:auto;vertical-align:middle}em{color:var(--muted)}table{display:block;max-width:100%;overflow:auto;border-collapse:collapse;margin-bottom:16px}td,th{padding:6px 13px;border:1px solid var(--border)}code{font-size:85%;background:var(--code);border-radius:4px;padding:.2em .4em}li+li{margin-top:.3em}.notice{max-width:896px;margin:16px auto;padding:0 20px;color:var(--muted);font-size:13px}@media(max-width:600px){main{padding:16px;margin:0;border:0}h1{font-size:1.65em}}`;
for(const dark of [false,true]){
 const vars=dark?'--bg:#0d1117;--fg:#e6edf3;--muted:#9198a1;--border:#3d444d;--link:#4493f8;--code:#656c7633':'--bg:#ffffff;--fg:#1f2328;--muted:#59636e;--border:#d1d9e0;--link:#0969da;--code:#818b981f';
 await fs.writeFile(path.join(out,`${prefix}-${dark?'dark':'light'}.html`),`<!doctype html><html lang="${lang}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><base href="${base}"><title>${title}</title><style>:root{${vars}}${css}</style><main class="markdown-body">${html}</main></html>`);
}
console.log(`${source}: light and dark previews generated.`);
