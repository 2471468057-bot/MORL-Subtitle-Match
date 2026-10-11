// Sample the unchanged, already approved HTML artworks at 25 fps.
// Rendering is deterministic; this is an artwork replay, not a desktop recording.
import fs from 'node:fs/promises';
import path from 'node:path';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const out=path.resolve(process.env.README_RAW||'tmp/readme-motion-daily-20260930/media','caption-effects');
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:900}});
try {
 await page.goto(process.env.PRODUCT_URL||'http://127.0.0.1:4175/');
 await page.locator('.effects-grid').scrollIntoViewIfNeeded();await page.waitForTimeout(4500);
 const b=await page.locator('.effects-grid').boundingBox(),clip={x:Math.floor(b.x),y:Math.floor(b.y),width:Math.ceil(b.width),height:Math.ceil(b.height)};
 const fps=25,frames=[],duration=3.8;
 for(let i=0;i<duration*fps;i++){
   const seconds=i/fps,t=Math.min(3,(seconds+.9)%duration);
   await page.evaluate(t=>document.querySelectorAll('.effects-grid iframe').forEach((f,i)=>f.contentWindow.postMessage({type:'2byte-demo-caption',text:i?'这个 BGM 刚刚好':'这段，留作精彩瞬间。',time:t,duration:3,visible:true,reduced:false},'*')),t);
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   const file=`render-${String(i).padStart(5,'0')}.png`;
   await page.screenshot({path:path.join(out,file),clip});frames.push({file,time:seconds});
 }
 await fs.writeFile(path.join(out,'capture.json'),JSON.stringify({name:'caption-effects',type:'existing HTML artwork replay at exact clock times',clip,duration,frames},null,2));
 console.log('Rendered 95 artwork frames at exact 25 fps, continuous artwork clock across loop');
} finally {await browser.close();}
