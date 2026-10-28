/** Real pointer/UI save tests on an explicitly synthetic, isolated annotation store. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const root='review/foreground-v6',fixture=root+'/synthetic-ui-fixture-'+Date.now();
fs.mkdirSync(root,{recursive:true});
const code=`from pathlib import Path
from PIL import Image,ImageDraw
from scripts.foreground_annotation_v6 import AnnotationServer
p=Path('${fixture}/sources/sofa/01-original.png');p.parent.mkdir(parents=True,exist_ok=True)
im=Image.new('RGB',(640,480),(190,180,160));ImageDraw.Draw(im).rectangle((160,120,200,360),fill=(40,40,40));im.save(p)
s=AnnotationServer(('127.0.0.1',0),Path('${fixture}/sources'),Path('${fixture}/synthetic-records'))
print(s.server_port,flush=True)
s.serve_forever()`;
const child=spawn('.venv/Scripts/python.exe',['-u','-c',code],{stdio:['ignore','pipe','pipe']});
let stderr='';child.stderr.on('data',d=>stderr+=d);
const port=await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Fixture did not start: '+stderr)),20000);child.stdout.once('data',d=>{clearTimeout(timer);resolve(Number(d.toString().trim()));});child.once('exit',c=>reject(Error('Fixture exited '+c+stderr)));});
const browser=await chromium.launch({channel:'chrome',headless:true});
const results=[];
try{
 const page=await browser.newPage({viewport:{width:1440,height:960},deviceScaleFactor:2});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:'+port);await page.locator('#photo').waitFor();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Masques vierges'));
 assert.equal(await page.locator('#objects option').count(),0);
 await page.locator('#author').fill('SYNTHETIC UI TEST — NOT HUMAN GT');await page.locator('#category').selectOption('thin-leg');await page.locator('#add').click();
 const pos=async(x,y)=>{const r=await page.locator('#board').boundingBox();return {x:r.x+x/640*r.width,y:r.y+y/480*r.height};};
 const a=await pos(100,80),b=await pos(250,400);await page.mouse.move(a.x,a.y);await page.mouse.down();await page.mouse.move(b.x,b.y,{steps:5});await page.mouse.up();
 await page.locator('[data-mode=foreground]').click();
 for(const [x,y] of [[160,120],[200,120],[200,360],[160,360]]){const p=await pos(x,y);await page.mouse.click(p.x,p.y);}
 await page.keyboard.press('Enter');
 await page.locator('#draft').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Brouillon enregistré'));
 let saved=await (await page.request.get('http://127.0.0.1:'+port+'/api/annotation/sofa')).json();assert.equal(saved.maskRevision,null);assert.equal(saved.objects.length,1);assert.equal(saved.objects[0].drawings.length,1);
 for(const [p,q] of saved.objects[0].drawings[0].points.entries())for(let k=0;k<2;k++)assert.ok(Math.abs(q[k]-[[160,120],[200,120],[200,360],[160,360]][p][k])<1);
 // Validation must fail before explicit human attestation / object review.
 await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('confirmation'));
 await page.locator('#reviewed').check();await page.locator('#human').check();await page.locator('#save').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('masques PNG enregistrés'));
 saved=await (await page.request.get('http://127.0.0.1:'+port+'/api/annotation/sofa')).json();assert.equal(saved.status,'reviewed-regions');assert.ok(saved.maskRevision);assert.equal(saved.scope,'reviewed-regions-only');
 await page.reload();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Relevé local chargé'));assert.equal(await page.locator('#objects option').count(),1);
 await page.locator('#plus').click();await page.locator('#plus').click();assert.equal(await page.locator('#zoom').textContent(),'225 %');await page.locator('#fit').click();assert.equal(await page.locator('#zoom').textContent(),'100 %');
 assert.deepEqual(errors,[]);results.push({synthetic:true,sourceCoordinates:true,draftNotGT:true,explicitReview:true,persistence:true,zoom:true});await page.close();
 // Real private photos are read-only in this test: no gestures or saves.
 for(const width of [1440,390]){
  const real=await browser.newPage({viewport:{width,height:width===390?844:960},deviceScaleFactor:2,isMobile:width===390,hasTouch:width===390});const faults=[];real.on('pageerror',e=>faults.push(e.message));let posts=0;real.on('request',r=>{if(r.method()==='POST')posts++;});
  await real.goto('http://127.0.0.1:8766');await real.waitForFunction(()=>document.querySelector('#photo').naturalWidth>1000&&document.querySelector('#status').textContent.includes('Masques vierges'));
  assert.equal(await real.locator('#objects option').count(),0);assert.equal(await real.locator('#scene option').count(),9);
  if(width===390)await real.locator('.workspace').scrollIntoViewIfNeeded();
  assert.equal(await real.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await real.screenshot({path:root+'/annotation-'+width+'.png',fullPage:width===390});assert.equal(posts,0);assert.deepEqual(faults,[]);results.push({width,dpr:2,realPhotoReadOnly:true,blankMasks:true,posts,horizontalOverflow:false});await real.close();
 }
}finally{await browser.close();child.kill();}
fs.writeFileSync(root+'/ui-check.json',JSON.stringify(results,null,2));console.log('PASS synthetic trace / draft / approval / persistence / zoom; real photos read-only 1440 and 390 DPR2');
