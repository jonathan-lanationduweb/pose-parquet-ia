/** Full product review. Photos and captures are local, under ignored review/. */
import fs from 'node:fs';import path from 'node:path';import http from 'node:http';import {createRequire} from 'node:module';
const req=createRequire(import.meta.url),pw=req(process.env.PPAI_PLAYWRIGHT_CORE||'playwright-core');
const BASE=process.env.PPAI_BASE||'http://127.0.0.1:8143',OUT=path.resolve('review/roomvo-level');fs.mkdirSync(OUT,{recursive:true});
const browser=await pw.chromium.launch({channel:'chrome',headless:true});const results=[],errors=[],photos=[];
const ok=(name,pass,detail)=>{results.push({name,pass:!!pass,detail});console.log(`${pass?'PASS':'FAIL'} ${name} ${detail?JSON.stringify(detail):''}`);};
const shot=(p,name)=>p.screenshot({path:path.join(OUT,name+'.jpg'),type:'jpeg',quality:90});
const ready=p=>p.waitForFunction(()=>{const c=window.__concept;return c.state.applied.source==='live'&&c.state.applied.key===c.appliedKey()&&!c.state.applying;},null,{timeout:90000});
async function page(width=1440,height=900,canvas=false){const p=await browser.newPage({viewport:{width,height}});p.on('pageerror',e=>errors.push(String(e)));if(canvas)await p.addInitScript(()=>{const orig=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(t,...args){return /webgl/.test(t)?null:orig.call(this,t,...args);};});await p.goto(BASE+'/tools/product-concept.html');await p.waitForFunction(()=>window.__sessionRooms);return p;}
try{
  for(const width of [320,360,375,390,430,768,820,1024,1280,1440,1600,1920]){
    const p=await page(width,width<700?844:900);if(width===1440)await shot(p,'01-home');if(width===390)await shot(p,'10-home-mobile');
    await p.click('#quickRooms [data-room="sejour"]');await ready(p);
    const m=await p.evaluate(()=>{const b=id=>{const r=document.getElementById(id).getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom};};return {overflow:document.documentElement.scrollWidth>innerWidth,card:b('card'),stage:b('stage'),sidebar:b('catalogSidebar'),products:document.querySelectorAll('#prods [data-id]').length};});
    ok(`layout ${width}`,!m.overflow&&m.card.bottom<= (width<700?844:900)+1&&m.products===39&&(width<1024||m.stage.x>=335),m);
    if(width===1440){await shot(p,'03-visualizer');await shot(p,'04-catalog');await p.evaluate(()=>window.__concept.openRooms());await shot(p,'02-room-select');await p.click('#roomClose');}
    if(width===390)await shot(p,'11-room-mobile');
    await p.evaluate(()=>window.__concept.openCus());await p.waitForTimeout(250);
    const visible=await p.evaluate(()=>{const r=document.getElementById('stage').getBoundingClientRect();return {stageHeight:r.height,windowHeight:innerHeight,side:document.getElementById('catalogSidebar').getBoundingClientRect().width};});
    ok(`customize ${width}`,width>=1024||visible.stageHeight>=(width<700?844:900)*.35,visible);
    if(width===1440)await shot(p,'05-customize');if(width===390)await shot(p,'13-customize-mobile');
    await p.evaluate(()=>window.__concept.closeAll());await p.evaluate(()=>window.__concept.openCat());if(width===390)await shot(p,'12-catalog-mobile');
    await p.close();
  }
  const p=await page();let posts=0;p.on('request',r=>{if(r.url().endsWith('/v1/analyze-room'))posts++;});
  for(const name of ['sejour','chambre','couloir','petite-piece','salon','appartement-ancien','entree-cadree']){
    const file=path.resolve(`datasets/private-real/${name}.jpg`);if(!fs.existsSync(file)){ok('photo '+name,false,'missing source');continue;}
    console.log('PHOTO START '+name);const before=posts;await p.setInputFiles('#file',file);await p.waitForFunction(()=>window.__concept.state.source==='uploaded');
    if(name==='sejour')await shot(p,'06-upload-analyzing');
    await p.waitForFunction(()=>{const c=window.__concept;return !['ANALYSIS_WAITING','ANALYZING','PHOTO_SELECTED'].includes(c.etatProduit());},null,{timeout:240000});
    const decision=await p.evaluate(()=>window.__concept.etatProduit());let manual=false;
    if(decision!=='RENDER_READY'){
      manual=true;await p.evaluate(()=>window.__concept.floorEditStart());await p.waitForFunction(()=>window.__concept.floorEdit.actif,{timeout:90000});
      const rect=await p.locator('#floorEdit').boundingBox();await p.mouse.move(rect.x+rect.width*.40,rect.y+rect.height*.90);await p.mouse.down();await p.mouse.move(rect.x+rect.width*.58,rect.y+rect.height*.90,{steps:8});await p.mouse.up();
      if(name==='couloir')await shot(p,'08-manual-adjustment');await p.click('#floorDone');
    }
    await ready(p);if(name==='sejour')await shot(p,'07-upload-result');const after=posts;
    for(const id of ['POINF36005','BTRPF39009','CHENF39031','CHENF36014','CHENF36015']){await p.evaluate(id=>window.__concept.select(id),id);await ready(p);}
    for(const deg of [0,37,90,315]){await p.evaluate(d=>window.__concept.setOrientation(d,false),deg);await ready(p);}
    const final=await p.evaluate(()=>window.__concept.etatProduit());photos.push({photo:name,decision,manual,render:'live',catalog:posts===after,final,posts:posts-before});ok('photo '+name,final==='RENDER_READY'&&posts===after,photos.at(-1));
  }
  await p.evaluate(()=>window.__concept.startCompare());await p.evaluate(()=>window.__concept.select('CHENF39031'));await p.waitForFunction(()=>window.__concept.state.appliedB.source==='live');await shot(p,'09-compare');
  await p.evaluate(()=>window.__concept.startCompare());await p.click('#baBtn');ok('before after convention',await p.evaluate(()=>window.__concept.state.ba&&document.getElementById('clipA').style.clipPath.match(/[0-9.]+/g).map(Number).join(',')==='0,0,0,50'));
  ok('session photos in memory',(await p.evaluate(()=>window.__sessionRooms.count))===7);
  await p.click('#homeReturn');await p.waitForSelector('#entry:not(.hidden)');ok('session room gallery',(await p.locator('.session-room').count())===7);
  await p.locator('.session-remove').first().click();ok('delete session room',(await p.locator('.session-room').count())===6);await p.close();
  const mobile=await page(390,844);await mobile.setInputFiles('#file',path.resolve('datasets/private-real/couloir.jpg'));await mobile.waitForFunction(()=>window.__concept.state.source==='uploaded');await shot(mobile,'14-upload-mobile');await mobile.waitForFunction(()=>!['ANALYSIS_WAITING','ANALYZING'].includes(window.__concept.etatProduit()),{timeout:240000});await mobile.evaluate(()=>window.__concept.floorEditStart());await mobile.waitForFunction(()=>window.__concept.floorEdit.actif);await shot(mobile,'15-manual-mobile');await mobile.click('#floorDone');await ready(mobile);await mobile.close();
  const cpu=await page(1280,900,true);await cpu.click('#quickRooms [data-room="chambre"]');await ready(cpu);ok('Canvas fallback',await cpu.evaluate(()=>window.__concept.adapter.mode==='live'));await shot(cpu,'canvas-fallback');await cpu.close();
  ok('0 console exceptions',errors.length===0,errors);
}finally{fs.writeFileSync(path.join(OUT,'checks.json'),JSON.stringify({results,photos,errors},null,2));await browser.close();}
process.exitCode=results.some(r=>!r.pass)||errors.length?1:0;
