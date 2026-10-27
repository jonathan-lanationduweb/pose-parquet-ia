/** Pixel-cell mask serialization, Python -> normalized polygons -> production Canvas. */
import assert from 'node:assert/strict';import fs from 'node:fs';import{execFileSync}from'node:child_process';import{createRequire}from'node:module';
const code=`
import json,numpy as np
from app.services.foreground import polygons
cases=[]
for name in ['rectangle','thin-leg','hole','diagonal','border','random']:
 m=np.zeros((40,60),bool)
 if name=='rectangle':m[15:30,20:40]=True
 if name=='thin-leg':m[10:35,30]=True
 if name=='hole':m[8:32,12:48]=True;m[16:25,22:37]=False
 if name=='diagonal':
  for y in range(10,30):m[y,10:y+10]=True
 if name=='random':m=np.random.default_rng(42).random((40,60))<.35
 if name=='border':m[20:,0:20]=True
 cases.append(dict(name=name,width=60,height=40,mask=m.astype(int).ravel().tolist(),occluders=[o.model_dump(by_alias=True,exclude_none=True) for o in polygons(m,kind='furniture',prefix=name)]))
print(json.dumps(cases))
`;
const cases=JSON.parse(execFileSync(process.env.PPAI_PYTHON||'.venv/Scripts/python.exe',['-c',code],{encoding:'utf8'}));
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE),browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const p=await browser.newPage();await p.goto((process.env.PPAI_BASE||'http://127.0.0.1:8000')+'/tools/product-concept.html?dev=1&prefetch=0');
 const rows=await p.evaluate(async cases=>{
  const{createSceneMasks}=await import('../web/scene/mask.js');
  return cases.map(c=>{
   const scene={floorZones:[{id:'floor',mask:{polygon:[{x:0,y:0},{x:1,y:0},{x:1,y:1},{x:0,y:1}],holes:[]}}],occluders:c.occluders},m=createSceneMasks(scene,c.width,c.height),a=m.occlusion;
   let wrong=0,max=0,missing=0;
   c.mask.forEach((v,i)=>{const delta=Math.abs((a?.[i]||0)-v*255);if(delta>1)wrong++;max=Math.max(max,delta);if(v&&(!a||a[i]<254))missing++;});
   return{name:c.name,wrong,max,missing};
  });
 },cases);
 fs.mkdirSync('review/visual-quality-s1-s8',{recursive:true});fs.writeFileSync('review/visual-quality-s1-s8/contour-roundtrip.json',JSON.stringify(rows,null,2));
 console.log(rows);for(const r of rows)assert.equal(r.wrong,0,r.name+' loses original pixel coverage');
}finally{await browser.close();}
