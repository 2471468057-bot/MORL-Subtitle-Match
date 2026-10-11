// Record the final product page, using its real controls and existing example data.
// Output raw frames only to tmp. No model inference, desktop claim or publication.
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const modulePath=process.env.PLAYWRIGHT_MODULE;
const {chromium}=await import(modulePath?.startsWith('file:')?modulePath:modulePath?pathToFileURL(modulePath).href:'playwright');
const root=path.resolve('tmp/brand-readme-20260930/media');
await fs.mkdir(root,{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const base=process.env.PRODUCT_URL||'http://127.0.0.1:4175/';
const pause=ms=>page.waitForTimeout(ms);
const shot=async u=>page.evaluate(u=>{const e=document.querySelector('.product-story');scrollTo({top:e.offsetTop-80+(e.offsetHeight-innerHeight+80)*u/6.85,behavior:'instant'});},u);
const slide=async(a,b,ms)=>{const start=Date.now();while(Date.now()-start<ms){const t=Math.min(1,(Date.now()-start)/ms);await shot(a+(b-a)*(t*t*(3-2*t)));await pause(30);}await shot(b);};
async function fresh(){await page.goto(base);await page.mouse.move(3,100);await page.evaluate(()=>scrollTo(0,0));await pause(400);}
async function bounds(selector){const b=await page.locator(selector).boundingBox();return{x:Math.floor(b.x),y:Math.floor(b.y),width:Math.ceil(b.width),height:Math.ceil(b.height)};}
async function pointer(){await page.evaluate(()=>{const p=document.createElement('div');p.id='recording-pointer';p.style.cssText='position:fixed;top:0;left:0;width:24px;height:30px;z-index:99999;pointer-events:none;transform:translate(-50px,-50px)';p.innerHTML='<svg viewBox="0 0 26 34"><path d="M3 2v24l6-6 5 11 5-2-6-11h10z" fill="#fff2ff" stroke="#68445e" stroke-width="2"/></svg>';document.body.append(p);addEventListener('pointermove',e=>{p.style.transform=`translate(${e.clientX}px,${e.clientY}px)`});});}
async function capture(name,clip,actions){
  const dir=path.join(root,name);await fs.mkdir(dir,{recursive:true});
  const frames=[],start=Date.now();let done=false,problem;
  const action=actions().catch(e=>{problem=e;}).finally(()=>done=true);
  while(!done){
    const t=(Date.now()-start)/1000, file=`frame-${String(frames.length).padStart(5,'0')}.png`;
    await page.screenshot({path:path.join(dir,file),clip,animations:'allow'});
    frames.push({file,time:t});
    await pause(Math.max(1,(frames.length*50)-(Date.now()-start)));
  }
  await action;if(problem)throw problem;
  const duration=(Date.now()-start)/1000;
  await fs.writeFile(path.join(dir,'capture.json'),JSON.stringify({name,type:'product-page interaction example',url:base,viewport:[1440,900],clip,duration,frames},null,2));
  console.log(JSON.stringify({name,frames:frames.length,duration,fps:frames.length/duration}));
}
async function save(name,selector){await page.screenshot({path:path.join(root,name+'.png'),clip:await bounds(selector)});}
try {
 await fresh();await shot(.9);await pause(500);
 const overview=await bounds('.product-window');
 await save('overview','.product-window');
 await capture('overview',overview,async()=>{
   await pause(1300);await slide(.9,1.3,550);await pause(1100);
   await slide(1.3,2.74,650);await pause(150);await slide(2.74,3.19,2100);await pause(450);
   await slide(3.19,3.92,450);await pause(550);await slide(3.92,4.14,600);await pause(650);
   await slide(4.14,4.35,450);await pause(650);await slide(4.35,5.45,550);await pause(700);
   await slide(5.45,5.72,500);await pause(650);await slide(5.72,5.9,400);await pause(700);
   await slide(5.9,6.72,550);await pause(2400);
 });
 await save('studio-result','.product-window');
 await fresh();await shot(3.95);await pause(500);
 await page.locator('.razor-demo').getByRole('button',{name:'重置',exact:true}).click();
 await pointer();await page.mouse.move(3,100);await pause(300);
 const razor=await bounds('.studio-editor');
 await capture('word-split',razor,async()=>{
   await pause(850);
   for(const i of [4,16]){const b=await bounds(`[data-word="${i}"]`);await page.mouse.move(b.x+b.width-2,b.y+b.height/2,{steps:18});await pause(650);await page.mouse.click(b.x+b.width-2,b.y+b.height/2);await pause(1100);}
   if(await page.locator('.razor-demo').getAttribute('data-cuts')!=='5,17')throw Error('Expected actual two cuts');
   await save('word-split','.studio-editor');
   await page.locator('.razor-demo').getByRole('button',{name:'撤销',exact:true}).click();await pause(1200);
   if(await page.locator('.razor-demo').getAttribute('data-cuts')!=='5')throw Error('Undo did not change timeline');
   await page.locator('.razor-demo').getByRole('button',{name:'撤销',exact:true}).click();await page.mouse.move(3,100);await pause(900);
 });
 await fresh();await shot(5.45);await pause(400);await pointer();
 await page.locator('.review-candidates > button').first().click();await page.mouse.move(3,100);
 await capture('candidate-review',await bounds('.studio-review'),async()=>{
   await pause(1250);
   await page.locator('.review-candidates > button').nth(2).hover();await pause(350);await page.locator('.review-candidates > button').nth(2).click();await pause(1100);
   await page.locator('.review-candidates > button').nth(1).hover();await pause(350);await page.locator('.review-candidates > button').nth(1).click();await pause(1100);
   await page.locator('.adopt-candidate').hover();await pause(600);await page.locator('.adopt-candidate').click();await page.mouse.move(3,100);await pause(1800);
   if(await page.locator('.review-strip').getAttribute('data-adopted')!=='1')throw Error('Candidate was not adopted');
   if(!(await page.locator('.current-cue').innerText()).includes('任务'))throw Error('Current text did not update');
   await save('candidate-review','.studio-review');
 });
 await fresh();await shot(1.3);await pause(500);await save('model-roles','.product-window');
 await shot(3.19);await pause(500);await save('speaker-tracks','.product-window');
 await page.locator('.glossary-app').scrollIntoViewIfNeeded();await pause(600);await save('glossary','.glossary-app');
 await page.locator('.clip-app').scrollIntoViewIfNeeded();await pause(600);await save('live-clips','.clip-app');
 await page.locator('.effects-grid').scrollIntoViewIfNeeded();await pause(4300);
 await save('caption-effects','.effects-grid');
 await capture('caption-effects',await bounds('.effects-grid'),async()=>{
   await pause(850);
   await page.getByRole('button',{name:'重播木刻压印',exact:true}).click();
   await page.getByRole('button',{name:'重播CRT 计分屏',exact:true}).click();
   await pause(3400);await pause(1300);
 });
 await fs.writeFile(path.join(root,'validation.json'),JSON.stringify({errors,claims:'Website interaction examples only; no model speed or accuracy claim. Native desktop evidence is separate.'},null,2));
 if(errors.length)throw Error(errors.join('\n'));
} finally {await browser.close();}
