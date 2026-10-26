import fs from 'node:fs';import assert from 'node:assert/strict';import{createRequire}from'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
const root='review/defects';fs.mkdirSync(root,{recursive:true});
try{
 const normal=await browser.newPage({viewport:{width:1440,height:900}}),urls=[],errors=[];
 normal.on('request',r=>urls.push(r.url()));normal.on('pageerror',e=>errors.push(e.message));
 await normal.addInitScript(()=>{window.__shaderSources=[];const p=WebGL2RenderingContext.prototype,fn=p.shaderSource;p.shaderSource=function(s,source){window.__shaderSources.push(source);return fn.call(this,s,source);};});
 await normal.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');
 await normal.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 await normal.evaluate(()=>window.__concept.openRoom('piece-claire'));
 await normal.waitForFunction(()=>window.__concept.etatApplication()==='rendered'&&!window.__concept.state.applying,null,{timeout:90000});
 assert.equal(await normal.locator('#visualDebugPanel,#visualDebugOverlay').count(),0);
 assert.equal(await normal.evaluate(()=>typeof window.__visualDiagnostics),'undefined');
 assert.equal(await normal.evaluate(()=>window.__concept.adapter.diagnosticSnapshot()),null);
 assert.equal(await normal.evaluate(()=>window.__concept.adapter.diagnosticUnlitFrame()),null);
 assert.ok(!urls.some(url=>/\/web\/product\/(geometry-review|diagnostic-layers|defect-report)\.js/.test(url)));
 assert.ok(await normal.evaluate(()=>window.__shaderSources.every(s=>!s.includes('uniform bool uDiagnosticUnlit'))));
 const normalProbes=await normal.evaluate(()=>{const c=window.__concept.adapter.visitSnapshot().canvas,d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;return Array.from({length:80},(_,i)=>Array.from(d.slice(((i*19387)%(c.width*c.height))*4,((i*19387)%(c.width*c.height))*4+3)));});
 await normal.close();
 const page=await browser.newPage({viewport:{width:1440,height:900}});page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8000/tools/product-concept.html?dev=1&prefetch=0');await page.waitForFunction(()=>window.__concept?.adapter.connecte&&window.__visualDiagnostics,null,{timeout:90000});
 await page.evaluate(()=>window.__concept.openRoom('piece-claire'));await page.waitForFunction(()=>window.__concept.etatApplication()==='rendered'&&!window.__concept.state.applying,null,{timeout:90000});
 const probes=await page.evaluate(()=>{const c=window.__concept.adapter.visitSnapshot().canvas,d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;return Array.from({length:80},(_,i)=>Array.from(d.slice(((i*19387)%(c.width*c.height))*4,((i*19387)%(c.width*c.height))*4+3)));});
 probes.forEach((p,i)=>p.forEach((v,k)=>assert.ok(Math.abs(v-normalProbes[i][k])<=1,'DEV-off changed normal render')));
 const inspected=await page.evaluate(async()=>{
  const c=window.__concept,s=c.adapter.diagnosticSnapshot(),{buildDiagnosticLayers,patternAt,scaleData}=await import('../web/product/diagnostic-layers.js'),{projectionRuntime}=await import('../web/scene/metric-runtime.js');
  const before=JSON.stringify(s.scene),beforeMask=s.masks.effectiveCoverage.slice(),all=buildDiagnosticLayers(s),w=s.size.width,h=s.size.height;
  let protectedProbes=0,visibleProbes=0,gridProbes=0;
  const grid=all.layers.debugGrid.getContext('2d').getImageData(0,0,w,h).data,pattern=all.layers.debugPattern.getContext('2d').getImageData(0,0,w,h).data,mask=all.layers.debugMasks.getContext('2d').getImageData(0,0,w,h).data;
  const render=s.canvas.getContext('2d').getImageData(0,0,w,h).data,source=s.photo.getContext('2d').getImageData(0,0,w,h).data;
  for(let i=0;i<w*h;i+=131){
   if(s.masks.effectiveCoverage[i]===0){if(grid[i*4+3]!==0||pattern[i*4+3]!==0)throw Error('Overlay escaped effective mask');}
   if((s.masks.occlusion?.[i]||0)>250){
    if(mask[i*4]===0)throw Error('Protected object missing red overlay');
    for(let k=0;k<3;k++)if(Math.abs(render[i*4+k]-source[i*4+k])>2)throw Error('Protected source pixel changed');
    protectedProbes++;
   }
   if(s.masks.effectiveCoverage[i]>250)visibleProbes++;
  }
    const zone=s.scene.floorZones[0],rt=projectionRuntime(zone.plane,w,h);
  if(!all.floorSpacePattern||all.metadata.floorPatternPreview.cameraApplied!==false)throw Error('Missing pre-projection pattern view');
  const {floorSpacePattern}=await import('../web/product/diagnostic-layers.js');
  const altered={...s,scene:structuredClone(s.scene)};
  altered.scene.floorZones[0].plane.projection.cameraModel.focalLength*=1.7;
  const flatA=all.floorSpacePattern.getContext('2d').getImageData(0,0,640,640).data,flatB=floorSpacePattern(altered).getContext('2d').getImageData(0,0,640,640).data;
  for(let i=0;i<640*640;i+=6991)for(let k=0;k<4;k++)if(flatA[i*4+k]!==flatB[i*4+k])throw Error('Flat pattern depends on camera');
  const center=rt.floor.pixelToFloorLocal({x:w*.5,y:h*.85},rt.camera);
  // Actual half-metre grid intersections projected by the renderer CameraModel.
  for(let u=Math.floor(center.u)-1;u<=Math.floor(center.u)+1;u+=.5)for(let v=Math.floor(center.v)-1;v<=Math.floor(center.v)+1;v+=.5){
   const p=rt.camera.project(rt.floor.floorLocalToWorld(u,v));if(!p)continue;const x=Math.round(p.x),y=Math.round(p.y);if(x<3||y<3||x>=w-3||y>=h-3||s.masks.effectiveCoverage[y*w+x]<250)continue;
   let hit=false;for(let dy=-2;dy<=2;dy++)for(let dx=-2;dx<=2;dx++)if(grid[((y+dy)*w+x+dx)*4+3]>100)hit=true;
   if(!hit)throw Error('Grid not registered with actual CameraModel');gridProbes++;
  }
  const sig=JSON.stringify(s.scene.floorZones.map(z=>z.plane.projection)),unlit=await c.adapter.diagnosticUnlitFrame();
  if(!unlit)throw Error('No unlit frame');
  const unlitPixels=unlit.getContext('2d').getImageData(0,0,w,h).data;let changed=0;
  for(let i=0;i<w*h;i+=131)if(s.masks.effectiveCoverage[i]>250&&Math.abs(unlitPixels[i*4]-render[i*4])>3)changed++;
  if(!changed)throw Error('Unlit comparison did not disable lighting');
  if(JSON.stringify(c.adapter.diagnosticSnapshot().scene.floorZones.map(z=>z.plane.projection))!==sig)throw Error('Unlit changed camera');
  if(JSON.stringify(s.scene)!==before||!s.masks.effectiveCoverage.every((v,i)=>v===beforeMask[i]))throw Error('Diagnostic mutated scene or masks');
  window.__diagnosticCase={signature:sig,board:patternAt(s,zone,{x:w*.5,y:h*.85}).boardId};
  return {protectedProbes,visibleProbes,gridProbes,unlitChangedProbes:changed,scale:scaleData(s),metadata:all.metadata};
 });
 assert.ok(inspected.protectedProbes>20&&inspected.visibleProbes>100&&inspected.gridProbes>3);
 assert.ok(inspected.scale.boardWidthMeters>0&&inspected.scale.boardLengthMeters>0);
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});await page.waitForTimeout(250);
  for(const flag of ['debugGrid','debugMasks','debugCamera','debugFloorPlane','debugScale','debugPattern']){
   const result=await page.evaluate(flag=>{const d=window.__visualDiagnostics;d.setFlags(Object.fromEntries(Object.keys(d.flags).map(k=>[k,k===flag])));const snap=window.__concept.adapter.diagnosticSnapshot();return{active:Object.entries(d.flags).filter(([,v])=>v).map(([k])=>k),signature:JSON.stringify(snap.scene.floorZones.map(z=>z.plane.projection)),source:document.getElementById('vpPhoto').getBoundingClientRect().toJSON(),overlay:document.getElementById('visualDebugOverlay').getBoundingClientRect().toJSON(),boardId:d.sample({x:snap.size.width*.5,y:snap.size.height*.85}).board.boardId,originalBoardId:window.__diagnosticCase.board,originalSignature:window.__diagnosticCase.signature};},flag);
   assert.deepEqual(result.active,[flag]);assert.equal(result.signature,result.originalSignature);assert.deepEqual(result.boardId,result.originalBoardId);
   for(const k of ['x','y','width','height'])assert.ok(Math.abs(result.source[k]-result.overlay[k])<.01,'Viewport layer mismatch');
  }
  await page.evaluate(()=>window.__visualDiagnostics.setFlags({debugPattern:false,debugMasks:true}));
  await page.locator('#visualDebugPanel').evaluate(e=>e.open=true);
  const vpBefore=await page.evaluate(()=>JSON.stringify(window.__concept.state.vp));await page.locator('[data-debug-flag=debugGrid]').check();assert.equal(await page.evaluate(()=>JSON.stringify(window.__concept.state.vp)),vpBefore);
  await page.screenshot({path:root+'/debug-ui-'+width+'.png'});
 }
 await page.close();
 const fallback=await browser.newPage({viewport:{width:390,height:844}});
 fallback.on('pageerror',e=>errors.push(e.message));
 await fallback.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return /webgl/.test(kind)?null:get.call(this,kind,...args);};});
 await fallback.goto('http://127.0.0.1:8000/tools/product-concept.html?dev=1&prefetch=0');
 await fallback.waitForFunction(()=>window.__concept?.adapter.connecte&&window.__visualDiagnostics,null,{timeout:90000});
 const canvasResult=await fallback.evaluate(async()=>{
  const c=window.__concept;await c.adapter.openRoom('chambre');
  const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='CHENF39031').renderProfile;
  const normal=await c.adapter.applyProfile(profile,0);if(!normal)throw Error('Canvas frame missing');
  const snapshot=c.adapter.diagnosticSnapshot(),w=normal.width,h=normal.height,lit=normal.getContext('2d').getImageData(0,0,w,h).data;
  const unlit=await c.adapter.diagnosticUnlitFrame();if(!unlit)throw Error('Canvas unlit missing');
  const flat=unlit.getContext('2d').getImageData(0,0,w,h).data,photo=snapshot.photo.getContext('2d').getImageData(0,0,w,h).data;
  let changed=0,protectedPixels=0;
  for(let i=0;i<w*h;i+=137){if(snapshot.masks.effectiveCoverage[i]===0){for(let k=0;k<3;k++)if(flat[i*4+k]!==photo[i*4+k])throw Error('Canvas diagnostic repainted object');protectedPixels++;}
   if(snapshot.masks.effectiveCoverage[i]>250&&Math.abs(lit[i*4]-flat[i*4])>3)changed++;}
  return {backend:c.adapter.moteur.backend,changed,protectedPixels};
 });
 assert.equal(canvasResult.backend,'canvas');assert.ok(canvasResult.changed>10&&canvasResult.protectedPixels>100);
 inspected.canvasFallback=canvasResult;await fallback.close();
 assert.deepEqual(errors,[]);fs.writeFileSync(root+'/diagnostic-tests.json',JSON.stringify(inspected,null,2));
 console.log('PASS DEV lazy loading/zero normal overlay allocation, normal output probes preserved, exact grid/masks/occlusions, independent flags and mappings at 1440/390, real unlit comparison, immutable camera/masks');
}finally{await browser.close();}
