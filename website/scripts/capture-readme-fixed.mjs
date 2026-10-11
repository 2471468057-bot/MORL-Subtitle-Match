// Exactly 25 fps, no scroll, resize, autonomous timer or screenshot-time pacing.
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const out=path.resolve(process.env.README_RAW||'tmp/readme-motion-daily-20260930/media');
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1080,height:960},deviceScaleFactor:1});
const names=['speaker-tracks','word-split','candidate-review','live-clips'];
const checks=[];
try {
 for(const name of names){
  const dir=path.join(out,name);await fs.mkdir(dir,{recursive:true});
  await page.goto((process.env.PRODUCT_URL||'http://127.0.0.1:4175/')+'readme.html?scene='+name);
  await page.waitForFunction(()=>!!window.readmeFrame);await page.evaluate(()=>document.fonts.ready);
  const stage=page.locator('.readme-stage');
  const b=await stage.boundingBox(),clip={x:0,y:0,width:1080,height:Math.ceil(b.height)};
  if(process.env.README_STILLS){await page.evaluate(()=>window.readmeFrame(5));await stage.screenshot({path:path.join(out,name+'-layout.png')});continue;}
  const duration=name==='speaker-tracks'?8:name==='word-split'?10:name==='candidate-review'?9:11;
  const center=async selector=>{const r=await page.locator(selector).boundingBox();return {x:r.x+r.width/2,y:r.y+r.height/2};};
  const endWord=async i=>{const r=await page.locator(`[data-word="${i}"]`).boundingBox();return {x:r.x+r.width-1,y:r.y+r.height/2};};
  let actions=[];
  if(name==='word-split') actions=[{at:1.5,to:()=>endWord(4)}, {at:3.5,to:()=>endWord(16)}, {at:6,to:()=>center('.studio-toolbar button:first-child')}, {at:7.5,to:()=>center('.studio-toolbar button:first-child')}];
  if(name==='candidate-review') actions=[{at:1.3,to:()=>center('.review-candidates button:nth-child(3)')},{at:3,to:()=>center('.review-candidates button:nth-child(2)')},{at:4.5,to:()=>center('.adopt-candidate')},{at:7.3,to:()=>center('#reset-review')}];
  if(name==='live-clips') actions=[{at:1.5,to:()=>center('.clip-candidate:nth-of-type(3)')},{at:3.5,to:()=>center('.clip-candidate:nth-of-type(1)')},{at:5.5,to:()=>center('.clip-detail .wine-button')},{at:8,to:()=>center('.software-title button')}];
  let cursor={x:1020,y:clip.height-28},from=cursor,current=-1;
  const frames=[];
  for(let i=0;i<duration*25;i++){
   const t=i/25;await page.evaluate(t=>window.readmeFrame(t),t);
   const index=actions.findIndex(a=>t>=a.at-.6 && !a.done);
   if(index>=0){
    if(index!==current){current=index;from={...cursor};actions[index].point=await actions[index].to();}
    const a=actions[index],u=Math.min(1,Math.max(0,(t-(a.at-.6))/.6)),ease=u*u*(3-2*u);
    cursor={x:from.x+(a.point.x-from.x)*ease,y:from.y+(a.point.y-from.y)*ease};
    await page.mouse.move(cursor.x,cursor.y);
    if(t>=a.at){await page.mouse.click(cursor.x,cursor.y);a.done=true;}
   }
   if(t>duration-1){
    if(t<duration-.96)from={...cursor};
    const u=Math.min(1,(t-duration+1)/.6),e=u*u*(3-2*u);
    cursor={x:from.x+(1020-from.x)*e,y:from.y+(clip.height-28-from.y)*e};
    await page.mouse.move(cursor.x,cursor.y);
   }
   await page.evaluate(p=>{const el=document.querySelector('#readme-pointer');el.style.visibility=p.show?'visible':'hidden';el.style.transform=`translate(${p.x}px,${p.y}px)`;},{...cursor,show:name!=='speaker-tracks'});
   // React state is painted before each screenshot; fps depends only on i/25.
   const file=`frame-${String(i).padStart(5,'0')}.png`;
   await page.screenshot({path:path.join(dir,file),clip});frames.push({file,time:t});
   if(i===Math.round(5.8*25)){
    await page.screenshot({path:path.join(out,name+'.png'),clip});
    const detail=await page.evaluate(()=>({cuts:document.querySelector('.razor-demo')?.dataset.cuts,review:document.querySelector('.review-strip')?.dataset.review,clip:document.querySelector('.clip-detail')?.dataset.candidate,accepted:document.querySelectorAll('.accepted-clips>span').length,body:document.body.innerText}));
    if(name==='word-split')assert.equal(detail.cuts,'5,17');
    if(name==='candidate-review')assert.match(detail.body,/已采用 FireRed/);
    if(name==='live-clips')assert.equal(detail.accepted,1);
    checks.push({name,detail});
   }
   if(i%100===0)console.log(name,i+'/'+duration*25);
  }
  const end=await stage.boundingBox();assert.equal(end.height,b.height);assert.equal(await page.evaluate(()=>scrollY),0);
  await fs.writeFile(path.join(dir,'capture.json'),JSON.stringify({name,type:'fixed camera; original React components; real pointer clicks',clip,duration,fps:25,frames},null,2));
 }
 await fs.writeFile(path.join(out,'checks.json'),JSON.stringify(checks,null,2));
} finally {await browser.close();}
