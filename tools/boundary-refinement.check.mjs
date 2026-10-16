/** Private photo replay, using the production renderer and its geometry diagnostics. */
import fs from 'node:fs';import path from 'node:path';import assert from 'node:assert/strict';import{createRequire}from'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const OUT='review/room-understanding-v2-1',base=process.env.PPAI_BASE||'http://127.0.0.1:8000';
const browser=await chromium.launch({channel:'chrome',headless:true}),results=[];
try{const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.route('**/rd-boundary/*',r=>{const id=decodeURIComponent(new URL(r.request().url()).pathname.split('/').pop());assert.ok(/^[a-z-]+$/.test(id));return r.fulfill({contentType:'image/jpeg',body:fs.readFileSync(`${OUT}/${id}/original.jpg`)});});
await page.goto(base+'/tools/product-concept.html?dev=1&prefetch=0');await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
for(const dir of fs.readdirSync(OUT).filter(x=>fs.existsSync(`${OUT}/${x}/scene-before.json`)&&(!process.env.PPAI_REVIEW_CASE||x===process.env.PPAI_REVIEW_CASE))){
 const runs=[];
 for(const variant of ['before','after']){
  const raw=JSON.parse(fs.readFileSync(`${OUT}/${dir}/scene-${variant}.json`,'utf8'));
  const measurement=JSON.parse(fs.readFileSync(`${OUT}/${dir}/measurement.json`,'utf8'));
  const result=await page.evaluate(async({raw,dir,measurement,variant})=>{
   const c=window.__concept;if(!await c.adapter.openPhotoScene(raw,`${location.origin}/rd-boundary/${dir}`))throw Error(c.adapter.refusScene);
   const reference=measurement.referenceProductId?(variant==='before'?measurement.beforeProductId:measurement.referenceProductId):'CHENF39031';
   const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id===reference).renderProfile;
   const start=performance.now(),frame=await c.adapter.applyProfile(profile,0);if(!frame)throw Error('No frame');
   if(c.adapter.lastHit)throw Error('stale frame');
   const render=frame.toDataURL('image/jpeg',.95),overlay=document.createElement('canvas');overlay.width=frame.width;overlay.height=frame.height;
   const ctx=overlay.getContext('2d');ctx.drawImage(frame,0,0);
   function line(a,b,color){if(![a.x,a.y,b.x,b.y].every(Number.isFinite))return;ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}
   if(Number.isFinite(raw.camera.horizon))line({x:0,y:raw.camera.horizon*frame.height},{x:frame.width,y:raw.camera.horizon*frame.height},'#ffd400');
   const diagnostics=[];
   for(const mm of [92,150,190]){const d=c.adapter.geometryDiagnostics({...profile,widthM:mm/1000},0);diagnostics.push(d);for(const z of d.zones)if(z.valid){for(const sample of z.samples)if(sample.valid)line(sample.a,sample.b,mm===92?'#72ff7a':mm===150?'#ffd400':'#ff96ff');if(mm===150){for(let k=0;k<z.contour.length;k++)line(z.contour[k],z.contour[(k+1)%z.contour.length],'#ff7777');for(const axis of z.axes)line(axis.a,axis.b,axis.color);}}}
   ctx.fillStyle='#111d';ctx.fillRect(8,8,Math.min(frame.width-16,950),190);ctx.fillStyle='#fff';ctx.font='15px sans-serif';
   const text=['92 / 150 / 190 mm: near, mid, far (scale estimated)',...diagnostics.map(d=>`${Math.round(d.plankM*1000)}mm: `+d.zones.filter(z=>z.valid).flatMap(z=>z.samples.map(s=>`${s.position} ${s.valid?s.plankWidthPx.toFixed(1):'--'}px`)).join(' | ')),...(measurement.perspective?.plausibility?.geometryCandidates||[]).map(x=>`${x.chosen?'WINNER ':''}${x.id}: ${Number(x.score).toFixed(2)} ${x.reason}`)];text.slice(0,9).forEach((t,i)=>ctx.fillText(t,20,32+i*19));
   return{render,overlay:overlay.toDataURL('image/jpeg',.94),renderMs:performance.now()-start,diagnostics};
  },{raw,dir,measurement,variant});
  fs.writeFileSync(`${OUT}/${dir}/render-${variant}.jpg`,Buffer.from(result.render.split(',')[1],'base64'));
  if(variant==='after')fs.writeFileSync(`${OUT}/${dir}/geometry-overlay.jpg`,Buffer.from(result.overlay.split(',')[1],'base64'));
  runs.push({variant,renderMs:result.renderMs,diagnostics:result.diagnostics});
 }
 results.push({id:dir,runs});console.log('PASS',dir);
}
assert.deepEqual(errors,[]);const old=process.env.PPAI_REVIEW_CASE&&fs.existsSync(`${OUT}/render-matrix.json`)?JSON.parse(fs.readFileSync(`${OUT}/render-matrix.json`,'utf8')).results:[];fs.writeFileSync(`${OUT}/render-matrix.json`,JSON.stringify({results:[...old.filter(x=>!results.some(y=>y.id===x.id)),...results],errors},null,2));
}finally{await browser.close();}
