/** Targeted visual and mobile regression for every demo room. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const base=process.env.PPAI_BASE||'http://127.0.0.1:8000';
const out='review/current-fixes';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
const rows=[];
async function ready(page,id){await page.waitForFunction(id=>{const c=window.__concept;return c.state.roomId===id&&c.etatApplication()==='rendered'&&c.state.applied.source==='live';},id,{timeout:90000});}
async function open(page){const manifest=await(await page.request.get(`${base}/web/data/rooms.json`)).json();const count=manifest.scenes.filter(s=>s.availableForGallery&&s.renderReady&&s.calibration?.status==='validated').length;await page.goto(`${base}/tools/product-concept.html?prefetch=0`);await page.waitForFunction(count=>window.__concept?.adapter.connecte&&window.__concept.DEMO_ROOMS.length===count,count,{timeout:90000});}
const inspectView = ()=>{const c=window.__concept;const b=document.getElementById('stage').getBoundingClientRect(),card=document.getElementById('card').getBoundingClientRect();const snap=c.adapter.visitSnapshot(),m=snap.masks;const sc=c.cssScale(),vp=c.state.vp;let floor=0,samples=0;
    for(let y=20;y<b.height-20;y+=12)for(let x=10;x<b.width-10;x+=12){const sx=Math.floor((x-vp.x)/sc),sy=Math.floor((y-vp.y)/sc);samples++;if(sx>=0&&sy>=0&&sx<m.width&&sy<m.height){const i=sy*m.width+sx;if(m.coverage[i]>127&&(!m.occlusion||m.occlusion[i]<127))floor++;}}
    return{floorFraction:floor/samples,overflow:document.documentElement.scrollWidth>innerWidth,cardBottom:card.bottom,height:innerHeight,vp:{...vp},focus:snap.floorFocus};};
try {
 for(const before of [true,false]){
  const p=await browser.newPage({viewport:{width:1440,height:900}});
  if(before)await p.route('**/data/scenes/piece-claire.json',r=>r.fulfill({contentType:'application/json',body:fs.readFileSync(`${out}/piece-before.json`,'utf8')}));
  await open(p);await p.evaluate(()=>{const c=window.__concept;c.select('BTRPF39009',true);c.openRoom('piece-claire');});await ready(p,'piece-claire');
  const frame=await p.evaluate(()=>document.getElementById('after').toDataURL('image/jpeg',.95));fs.writeFileSync(`${out}/piece-${before?'before':'after'}.jpg`,Buffer.from(frame.split(',')[1],'base64'));await p.close();
 }
 for(const width of [320,390,430]){
  const ctx=await browser.newContext({viewport:{width,height:740},isMobile:true,hasTouch:true});const p=await ctx.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));await open(p);
  const ids=await p.evaluate(()=>window.__concept.DEMO_ROOMS.map(r=>r.id));
  for(const id of ids){
   await p.evaluate(id=>window.__concept.openRoom(id),id);await ready(p,id);
   const view=await p.evaluate(inspectView);
   assert.ok(!view.overflow,`${width} ${id}: overflow`);assert.ok(view.cardBottom<=view.height+1,`${id}: bottom controls clipped`);assert.ok(view.floorFraction>=.10,`${width} ${id}: floor hidden (${view.floorFraction})`);
   await p.evaluate(()=>window.__concept.openCus());await p.waitForTimeout(150);const custom=await p.evaluate(inspectView);assert.ok(custom.floorFraction>=.10,`${width} ${id}: floor hidden while customizing (${custom.floorFraction})`);assert.ok(!custom.overflow);await p.screenshot({path:`${out}/${width}-${id}-custom.jpg`,type:'jpeg',quality:85});await p.locator('#cusClose').tap();await p.waitForTimeout(100);await p.screenshot({path:`${out}/${width}-${id}.jpg`,type:'jpeg',quality:85});rows.push({width,id,customFloorFraction:custom.floorFraction,...view});fs.writeFileSync(`${out}/mobile-rooms.json`,JSON.stringify(rows,null,2));
  }
  await p.locator('#photoMore').tap();const options=p.locator('#photoActions');for(const name of ['Plein écran','Télécharger le rendu','Voir toute la pièce'])assert.ok(await options.getByRole('button',{name,exact:true}).isVisible(),`Missing option ${name}`);
  assert.equal(await options.getByRole('button',{name:'Ajuster le sol',exact:true,includeHidden:true}).isVisible(),false,'Demo exposes an unavailable correction');const rect=await options.boundingBox();assert.ok(rect.x>=0&&rect.x+rect.width<=width+1,'Options outside phone');await p.screenshot({path:`${out}/${width}-options.jpg`,type:'jpeg',quality:90});await options.getByRole('button',{name:'Voir toute la pièce',exact:true}).tap();assert.ok(await p.evaluate(()=>window.__concept.state.vp.z<=1),'Full photo command failed');assert.deepEqual(errors,[]);console.log(`PASS ${width}px: ${ids.length} rooms, floor visible, controls and options`);await ctx.close();
 }
}finally{await browser.close();}
