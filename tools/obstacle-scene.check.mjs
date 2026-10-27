/** Recovered supports in reviewed real scenes, checked against pre-task masks. */
import assert from 'node:assert/strict';import{execFileSync}from'node:child_process';import fs from'node:fs';import{createRequire}from'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE),browser=await chromium.launch({channel:'chrome',headless:true});
const cases=[['premibel-salon',[580,325,620,358]],['salle-a-manger-meublee',[330,450,370,575]],['salle-a-manger-meublee',[580,450,610,600]]],rows=[];
try{
 const p=await browser.newPage({viewport:{width:1440,height:900}});
 await p.goto((process.env.PPAI_BASE||'http://127.0.0.1:8000')+'/tools/product-concept.html?dev=1&prefetch=0');
 await p.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 for(const[id,box]of cases){
  const before=JSON.parse(execFileSync('git',['show','64fefbb:web/data/scenes/'+id+'.json'],{encoding:'utf8'}));
  const after=JSON.parse(fs.readFileSync('web/data/scenes/'+id+'.json','utf8'));
  for(const k of ['camera','planes','light'])assert.deepEqual(after[k],before[k],id+' changed '+k);
  const result=await p.evaluate(async({id,before,box})=>{
   const {normalizeScene}=await import('../web/scene/schema.js'),{createSceneMasks}=await import('../web/scene/mask.js');
   const c=window.__concept;await c.adapter.openRoom(id);
   const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='BTRPF39009').renderProfile,frame=await c.adapter.applyProfile(profile,0),s=c.adapter.diagnosticSnapshot(profile,0),w=s.size.width,h=s.size.height;
   const old=createSceneMasks(normalizeScene(before),w,h),data=frame.getContext('2d').getImageData(0,0,w,h).data,src=s.photo.getContext('2d').getImageData(0,0,w,h).data;
   let recovered=0,maxError=0;const coarse=old.occlusion,newMask=s.masks.occlusion;
   for(let y=box[1];y<box[3];y++)for(let x=box[0];x<box[2];x++){
    const i=y*w+x,p=i*4;if(newMask[i]<250||(coarse&&coarse[i]>5))continue;
    if(Math.max(src[p],src[p+1],src[p+2])>115)continue;
    for(let k=0;k<3;k++)maxError=Math.max(maxError,Math.abs(src[p+k]-data[p+k]));recovered++;
   }
   return{scene:id,box,recoveredOpaqueSupportPixels:recovered,maxSourcePixelError:maxError};
  },{id,before,box});
  assert.ok(result.recoveredOpaqueSupportPixels>=5,JSON.stringify(result));assert.ok(result.maxSourcePixelError<=2,JSON.stringify(result));rows.push(result);
 }
 fs.writeFileSync('review/occlusion-obstacles/recovered-supports.json',JSON.stringify(rows,null,2));console.log('PASS recovered real supports; source pixels preserved, camera/planes/light unchanged',rows);
}finally{await browser.close();}
