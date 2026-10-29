/** All approval writes use isolated synthetic fixtures. Real photos remain read-only. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const root='review/foreground-assisted-v6',fixture=root+'/synthetic-'+Date.now();
fs.mkdirSync(root,{recursive:true});
const code=`from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scripts.foreground_annotation_v6 import AnnotationServer
root=Path('${fixture}')
p=root/'sources/sofa/01-original.png';p.parent.mkdir(parents=True,exist_ok=True)
im=Image.new('RGB',(640,480),(190,180,160));draw=ImageDraw.Draw(im)
labels=np.full((480,640),3,np.int32);fg=np.zeros((480,640),bool)
for box,label,color in [((100,100,220,280),23,(80,90,100)),((340,120,390,320),19,(50,60,70)),((200,380,440,440),28,(150,150,140))]:
 x0,y0,x1,y1=box;draw.rectangle((x0,y0,x1-1,y1-1),fill=color);labels[y0:y1,x0:x1]=label;fg[y0:y1,x0:x1]=True
im.save(p);np.save(p.parent/'labels.npy',labels);np.save(p.parent/'support.npy',np.ones_like(fg))
b=root/'foreground-mask-v5-1/sofa';b.mkdir(parents=True);np.save(b/'v51.npy',fg);np.save(b/'prior.npy',fg)
s=AnnotationServer(('127.0.0.1',0),root/'sources',root/'synthetic-records')
print(s.server_port,flush=True);s.serve_forever()`;
const child=spawn('.venv/Scripts/python.exe',['-u','-c',code],{stdio:['ignore','pipe','pipe']});let stderr='';child.stderr.on('data',d=>stderr+=d);
const port=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture startup: '+stderr)),25000);child.stdout.once('data',d=>{clearTimeout(timer);resolve(Number(d.toString().trim()));});child.once('exit',c=>reject(Error('Fixture exited '+c+stderr)));});
const url='http://127.0.0.1:'+port,browser=await chromium.launch({channel:'chrome',headless:true}),rows=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:960},deviceScaleFactor:2}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(url);await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Propositions prêtes'));
 assert.equal(await page.locator('#workflow').inputValue(),'assisted-review');assert.equal(await page.locator('#objects option').count(),0);assert.equal((await (await page.request.get(url+'/api/annotation/sofa')).json()),null);
 assert.equal(await page.locator('#proposalLabel').textContent(),'PROPOSITION AUTOMATIQUE — NON VALIDÉE');
 await page.locator('#author').fill('SYNTHETIC AUTOMATION — NOT REAL HUMAN GT');
 const pos=async(x,y)=>{const r=await page.locator('#board').boundingBox();return {x:r.x+x/640*r.width,y:r.y+y/480*r.height};};
 const tap=async(x,y)=>{const p=await pos(x,y);await page.mouse.click(p.x,p.y);};
 await tap(160,180);assert.equal(await page.locator('#objects option').count(),1);assert.equal(await page.locator('#objectCategory').inputValue(),'sofa');
 await page.locator('#draft').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Brouillon enregistré'));
 let record=await (await page.request.get(url+'/api/annotation/sofa')).json();assert.equal(record.maskRevision,null);assert.equal(record.objects[0].annotationMode,'assisted-review');assert.equal(record.objects[0].useProposal,true);assert.equal(record.objects[0].humanConfirmed,false);
 await page.locator('[data-mode=erase]').click();await tap(150,150);await page.locator('#undo').click();await page.locator('#redo').click();
 await page.locator('#draft').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Brouillon enregistré'));
 record=await (await page.request.get(url+'/api/annotation/sofa')).json();assert.equal(record.objects[0].drawings.length,1);assert.equal(record.maskRevision,null);
 await page.locator('#validateObject').click();assert.ok((await page.locator('#status').textContent()).includes('confirmez'));
 await page.locator('#reviewed').check();await page.locator('#human').check();await page.locator('#validateObject').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Validation humaine enregistrée'));
 record=await (await page.request.get(url+'/api/annotation/sofa')).json();assert.ok(record.maskRevision);assert.equal(record.objects[0].humanDrawnFromScratch,false);assert.equal(record.objects[0].humanReviewed,true);assert.equal(record.objects[0].proposalSource,'foreground-v5-1');
 await page.locator('#next').click();assert.equal(await page.locator('#objects option').count(),2);assert.ok((await page.locator('#origin').textContent()).includes('NON VALIDÉ'));
 await page.locator('#negative').click();assert.equal(await page.locator('#objectCategory').inputValue(),'negative-region');
 const a=await pos(460,110),b=await pos(610,310);await page.mouse.move(a.x,a.y);await page.mouse.down();await page.mouse.move(b.x,b.y,{steps:5});await page.mouse.up();
 await page.locator('#reviewed').check();await page.locator('#human').check();await page.locator('#validateObject').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Validation humaine enregistrée'));
 record=await (await page.request.get(url+'/api/annotation/sofa')).json();assert.equal(record.status,'partial-reviewed');assert.equal(record.validatedObjectIds.length,2);assert.equal(record.objects.filter(o=>o.humanConfirmed).length,2);
 await page.waitForFunction(()=>document.querySelector('#evaluation').textContent.includes('1/5 objets relus')&&document.querySelector('#evaluation').textContent.includes('1/1 zone négative'));
 const progress=await (await page.request.get(url+'/api/evaluation')).json();assert.equal(progress.objects,1);assert.equal(progress.negativeRegions,1);assert.equal(progress.ready,false);
 await page.reload();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Relevé local chargé'));assert.equal(await page.locator('#objects option').count(),3);
 await page.locator('#workflow').selectOption('manual');assert.equal(await page.locator('#proposalLabel').isVisible(),false);await page.locator('#kind').selectOption('polygon');
 assert.deepEqual(errors,[]);rows.push({synthetic:true,proposalNotGT:true,correction:true,undoRedo:true,explicitValidation:true,partialValidation:true,negative:true,automaticReadiness:true,manualRetained:true});await page.close();
 const realURL=process.env.PPAI_ANNOTATION_URL||'http://127.0.0.1:8767';
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:width===390?844:960},deviceScaleFactor:2,isMobile:width===390,hasTouch:width===390}),faults=[];let posts=0;page.on('pageerror',e=>faults.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts++;});
  await page.goto(realURL);await page.waitForFunction(()=>document.querySelector('#photo').naturalWidth===1536&&document.querySelector('#status').textContent.includes('Propositions prêtes'));
  assert.equal(await page.locator('#proposalLabel').isVisible(),true);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  const count=await page.locator('#overlay image').count();assert.ok(count>0);
  if(width===390)await page.locator('.workspace').scrollIntoViewIfNeeded();
  await page.screenshot({path:root+'/assisted-'+width+'.png',fullPage:width===390});
  await page.locator('#workflow').selectOption('manual');assert.equal(await page.locator('#proposalLabel').isVisible(),false);assert.equal(await page.locator('#objects option').count(),0);
  assert.equal(posts,0);assert.deepEqual(faults,[]);rows.push({width,dpr:2,proposalImages:count,realPhotoReadOnly:true,posts,horizontalOverflow:false});await page.close();
 }
}finally{await browser.close();child.kill();}
fs.writeFileSync(root+'/browser.json',JSON.stringify(rows,null,2));console.log('PASS assisted proposal / correction / undo-redo / partial human approval / negative / readiness / manual / desktop-mobile read-only');
