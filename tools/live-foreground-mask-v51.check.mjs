/** Actual local FastAPI/model + UI import, with V5 foreground validation; V4 preserved. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const baseline=process.argv.includes('--baseline');
const root='review/foreground-mask-v5-1/'+(baseline?'baseline-live':'live'),browser=await chromium.launch({channel:'chrome',headless:true}),rows=[];
fs.mkdirSync(root,{recursive:true});
try{
 for(const [run,width] of [1440,390,1440,390,390].entries()){
  const page=await browser.newPage({viewport:{width,height:width===390?844:900},deviceScaleFactor:2,isMobile:width===390,hasTouch:width===390});
  if(baseline){
    const {execFileSync}=await import('node:child_process');
    const source=execFileSync('git',['show','d87781f:web/scene/occlusion-refiner.js'],{encoding:'utf8'});
    await page.route('**/web/scene/occlusion-refiner.js',r=>r.fulfill({contentType:'text/javascript',body:source}));
  }
  const errors=[];let posts=0,api;
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/v1/analyze-room'))posts++;});
  page.on('response',async r=>{if(r.request().method()==='POST'&&r.url().endsWith('/v1/analyze-room'))api=await r.json();});
  await page.goto('http://127.0.0.1:8000/tools/product-concept.html?dev=1&prefetch=0');
  await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
  const start=Date.now();await page.setInputFiles('#file','review/foreground-mask-v5/sofa/01-original.png');
  await page.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY'&&!window.__concept.state.applying,null,{timeout:180000});
  const firstMs=Date.now()-start;
  const initialGeometry=await page.evaluate(()=>JSON.stringify([window.__concept.state.photoScene.raw.camera,window.__concept.state.photoScene.raw.planes]));
  await page.waitForFunction(()=>window.__concept.state.photoScene?.qualityUpdateMs!=null,null,{timeout:180000});
  const finalMs=Date.now()-start;
  assert.equal(await page.evaluate(()=>JSON.stringify([window.__concept.state.photoScene.raw.camera,window.__concept.state.photoScene.raw.planes])),initialGeometry);
  const result=await page.evaluate(async()=>{
    const c=window.__concept,raw=c.state.photoScene.raw;
    const foreground=c.state.photoScene.provenance.foregroundUnderstanding;if(!foreground?.timingsMs)throw Error('V5 foreground missing');
    if(c.state.photoScene.provenance.sceneQuality.foregroundQuality>=.8)throw Error('Uncalibrated foreground promoted');
    const wire=raw.light.lightLayer;if(!wire?.data?.startsWith('data:image/png;base64,'))throw Error('Backend lightLayer missing');
    const {decodeLightLayer}=await import('/web/scene/contact-compositor.js');const layer=await decodeLightLayer(wire);
    if(!layer.rgba.every(Number.isFinite))throw Error('Non-finite texture');
    const geometry=JSON.stringify([raw.camera,raw.planes]);
    for(const id of ['CHENF39031','BTRPF39009']){await c.select(id);}
    if(JSON.stringify([c.state.photoScene.raw.camera,c.state.photoScene.raw.planes])!==geometry)throw Error('Geometry changed');
    return {foreground,qualityProvenance:c.state.photoScene.provenance,pass:c.state.photoScene.provenance.pass,encoding:wire.encoding,layerSize:[wire.width,wire.height],renderedSize:c.adapter.visitSnapshot().size,horizontalOverflow:document.documentElement.scrollWidth>innerWidth};
  });
  await page.waitForFunction(()=>!window.__concept.state.applying);
  await page.screenshot({path:root+'/live-ui-'+run+'-'+width+'.png'});
  assert.equal(posts,1);assert.deepEqual(errors,[]);assert.equal(result.horizontalOverflow,false);
  fs.writeFileSync(root+'/live-api-'+run+'-'+width+'.json',JSON.stringify(api));
  rows.push({run,width,firstMs,finalMs,posts,...result});console.log(JSON.stringify({run,width,firstMs,finalMs,posts,foregroundQuality:result.foreground.foregroundQuality}));await page.close();
 }
}finally{await browser.close();}
fs.writeFileSync(root+'/live-ui.json',JSON.stringify(rows,null,2));
