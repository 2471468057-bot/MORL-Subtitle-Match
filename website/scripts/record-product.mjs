// Genuine continuous browser recording. Inputs are only forward wheel events.
import fs from 'node:fs/promises';
import path from 'node:path';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const out=path.resolve(process.env.PRODUCT_EVIDENCE || 'tmp/product-continuity-recording');
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:process.env.HEADED!=='1'});
const ctx=await browser.newContext({viewport:{width:1440,height:900},recordVideo:{dir:out,size:{width:1440,height:900}}});
const page=await ctx.newPage(),events=[],errors=[];
page.on('pageerror',e=>errors.push(e.message));
await page.addInitScript(()=>{
  const frames=[];let previous=0,lastScroll=0;
  window.addEventListener('scroll',()=>{lastScroll=performance.now();},{passive:true});
  const sample=now=>{
    if(previous && now-lastScroll<120)frames.push(now-previous);
    previous=now;requestAnimationFrame(sample);
  };
  requestAnimationFrame(sample);window.__motionFrames=frames;
});
await page.goto(process.env.PRODUCT_URL||'http://127.0.0.1:4175/');
const started=Date.now();
const wheelTo=async y=>{
 y=Math.min(y,await page.evaluate(()=>document.documentElement.scrollHeight-innerHeight));
 let current=await page.evaluate(()=>scrollY), stagnant=0;
 while(y-current>2){
   await page.mouse.wheel(0,Math.min(34,y-current));await page.waitForTimeout(52);
   let next=await page.evaluate(()=>scrollY);
   if(next===current){await page.waitForTimeout(100);next=await page.evaluate(()=>scrollY);stagnant++;}else stagnant=0;
   if(stagnant>8)throw new Error(`Wheel stalled at ${current}, target ${y}`);
   current=next;
 }
};
const event=async(name,hold)=>{await page.waitForTimeout(hold);events.push({name,seconds:(Date.now()-started)/1000,scrollY:await page.evaluate(()=>scrollY),cuts:await page.locator('.razor-demo').getAttribute('data-cuts'),review:await page.locator('.review-strip').getAttribute('data-adopted')});console.log('REC',name);};
const shot=async(name,u,hold=700)=>{const y=await page.locator('.product-story').evaluate((e,u)=>e.getBoundingClientRect().top+scrollY-80+(e.offsetHeight-innerHeight+80)*u/6.85,u);await wheelTo(y);await event(name,hold);};
const section=async(name,sel,hold=800,offset=90)=>{const y=await page.locator(sel).evaluate((e,offset)=>e.getBoundingClientRect().top+scrollY-offset,offset);await wheelTo(y);await event(name,hold);};
await event('首屏空闲演示窗口',2900);
await wheelTo(160);await event('滚轮让旧自动窗口立即退场',800);
await shot('标题先行',.7,1000);
await shot('原三角色卡放大',1.28,2600);
await shot('主力标题接管，角色卡保持放大',1.80,850);
await shot('角色卡直接收拢为来源栏',2.30,600);
await shot('空轨道与说话人先就位',2.72,800);
await shot('A 字幕随后填入轨道',2.86,800);
await shot('B 文本落轨',3.0,800);
await shot('A 继续说话',3.15,850);
await shot('时间轴标题',3.4,850);
await shot('字词逐个定位',3.95,700);
await shot('第一刀，两段',4.12,650);
await shot('继续切成四段',4.34,1300);
await shot('更多合法切点，七段',4.71,2100);
await shot('文字复核来源',5.10,750);
await shot('MOSS 候选',5.44,500);
await shot('比较 Qwen 候选',5.59,600);
await shot('选择 FireRed 候选',5.74,600);
await shot('采用到同一条字幕',5.9,750);
await shot('从局部展开完整 Studio',6.72,1500);
await section('术语库标题先行','#glossary',750,140);
await section('切换游戏、筛选与确认','.glossary-app',4700,100);
await section('直播标题先行','#clips',850,110);
await section('三个直播候选，右侧详情与选区联动','.clip-app',4800,110);
await section('特效标题先行','#effects',700,110);
await section('木刻与 CRT 完整入退场','.effects-grid',4400,210);
await section('完整模型目录与运行条件','#models',1000,95);
await section('下载与运行条件','#download',1100,95);
const frames=await page.evaluate(()=>window.__motionFrames);
const sorted=[...frames].sort((a,b)=>a-b),frameIntervals={samples:frames.length,p95:sorted[Math.floor(sorted.length*.95)],max:sorted.at(-1),over50:frames.filter(t=>t>50).length,note:'rAF scheduling intervals during scrolling, not display FPS'};
await ctx.close();await page.video().saveAs(path.join(out,'scroll-path.webm'));await browser.close();
await fs.writeFile(path.join(out,'recording.json'),JSON.stringify({type:'continuous browser video',headless:process.env.HEADED!=='1',viewport:[1440,900],pointerMoves:0,clicks:0,events,errors,frameIntervals},null,2));if(errors.length)throw new Error(errors.join('\n'));
