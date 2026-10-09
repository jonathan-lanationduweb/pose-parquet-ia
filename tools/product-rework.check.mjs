/** Visual regression: actual browser layouts and each calibrated scene / pattern / engine.
 * PPAI_BASE=http://127.0.0.1:8143 PPAI_PLAYWRIGHT_CORE=<module> node tools/product-rework.check.mjs
 * PPAI_REFERENCE_ROOT is optional and is served read-only for comparison captures.
 */
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const pw = require(process.env.PPAI_PLAYWRIGHT_CORE || 'playwright-core');
const base = process.env.PPAI_BASE || 'http://127.0.0.1:8143';
const out = path.resolve('review/product-rework');
fs.mkdirSync(out, { recursive: true });
const results = []; const errors = [];
const check = (name, value, detail) => { results.push({ name, pass: !!value, detail }); console.log(`${value?'OK':'FAIL'} ${name} ${detail?JSON.stringify(detail):''}`); };
const browser = await pw.chromium.launch({channel:'chrome',headless:true});
const shot = (p,name) => p.screenshot({path:path.join(out,name+'.jpg'),type:'jpeg',quality:88});
const waitReady = p => p.waitForFunction(()=>window.__concept.state.applied.source==='live',{timeout:90000});
async function page(width=1440,height=900,canvas=false,dev=false) {
  const p = await browser.newPage({viewport:{width,height}});
  p.on('pageerror',e=>errors.push(String(e)));
  p.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  if(canvas) await p.addInitScript(()=>{const orig=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(t,...a){return /webgl/.test(t)?null:orig.call(this,t,...a);};});
  await p.goto(base+'/tools/product-concept.html'+(dev?'?dev=1':''));
  await p.waitForFunction(()=>window.__concept);
  return p;
}
try {
  if(process.env.PPAI_REFERENCE_ROOT) {
    const root=path.resolve(process.env.PPAI_REFERENCE_ROOT);
    const server=http.createServer((req,res)=>{
      const file=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));
      if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}
      fs.readFile(file,(e,b)=>{if(e){res.writeHead(404);return res.end();}
        const ext=path.extname(file);res.setHeader('Content-Type',({'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.woff2':'font/woff2','.jpg':'image/jpeg','.webp':'image/webp'})[ext]||'application/octet-stream');res.end(b);});
    });
    await new Promise(r=>server.listen(8144,'127.0.0.1',r));
    try {
      const ref=await browser.newPage({viewport:{width:1440,height:900}});const logs=[];
      ref.on('pageerror',e=>logs.push(String(e)));ref.on('console',m=>{if(m.type()==='error')logs.push(m.text());});
      ref.on('response',r=>{if(r.status()>=400)logs.push(`${r.status()} ${r.url()}`);});
      await ref.goto('http://127.0.0.1:8144/outils/visualiseur-produit.html');await ref.waitForTimeout(6000);
      await shot(ref,'reference-1440-home');
      console.log('Reference body:',(await ref.locator('body').innerText()).slice(0,1200));
      fs.writeFileSync(path.join(out,'reference-diagnostics.json'),JSON.stringify(logs,null,2));
      await ref.close();
    } finally { server.close(); }
  }
  for(const width of [320,360,375,390,430,768,1024,1280,1440,1600,1920]) {
    const height=width<=430?(width===320?640:844):900; const p=await page(width,height);
    const prefix=width<1024?`mobile-${width}`:`desktop-${width}`;
    await shot(p,prefix+'-home');
    await p.evaluate(()=>window.__concept.openRoom('sejour'));await waitReady(p);
    await shot(p,prefix+'-room');
    for(const [fn,name] of [['openCus','customize'],['openCat','catalog'],['openRooms','rooms']]) {
      await p.evaluate(fn=>window.__concept[fn](),fn);await p.waitForTimeout(400);
      const layout=await p.evaluate(()=>{
        const c=window.__concept,stage=document.getElementById('stage').getBoundingClientRect(),panel=c.drawer.element.getBoundingClientRect();
        return {stage:{left:stage.left,right:stage.right,top:stage.top,bottom:stage.bottom,width:stage.width,height:stage.height},panel:{left:panel.left,right:panel.right,top:panel.top,bottom:panel.bottom},scrim:getComputedStyle(c.drawer.scrim).display,overflow:document.documentElement.scrollWidth>innerWidth,modal:c.drawer.element.getAttribute('aria-modal')};
      });
      const visible=width>=1024?layout.stage.right<=layout.panel.left+1:layout.stage.bottom<=layout.panel.top+1;
      check(`${width} ${name}: preview separate from panel`,visible&&!layout.overflow&&layout.scrim==='none',layout);
      await shot(p,prefix+'-'+name);
      await p.evaluate(()=>window.__concept.closeAll());
    }
    await p.close();
  }
  const geometry=[];
  for(const canvas of [false,true]) {
    const p=await page(1440,900,canvas,true);
    for(const scene of ['sejour','chambre','piece-claire','bureau-vide','piece-arcades']) {
      await p.evaluate(id=>window.__concept.openRoom(id),scene);await waitReady(p);
      await p.evaluate(()=>{window.__concept.state.ba=true;window.__concept.state.split=1;window.__concept.paintChrome();});
      await shot(p,`geometry-${canvas?'canvas':'webgl'}-${scene}-original`);
      await p.evaluate(()=>{window.__concept.state.ba=false;window.__concept.paintChrome();});
      for(const [id,pattern] of [['CHENF39031','lames'],['POINF36005','pdh'],['BTRPF39009','baton']]) {
        await p.evaluate(id=>window.__concept.select(id,true),id);await p.waitForFunction(id=>window.__concept.state.applied.source==='live'&&window.__concept.state.applied.key.includes(id),id,{timeout:90000});
        await shot(p,`geometry-${canvas?'canvas':'webgl'}-${scene}-${pattern}`);
        const d=await p.evaluate(()=>window.__geometryReview.show());
        check(`${canvas?'Canvas':'WebGL'} ${scene} ${pattern}: finite projection`,d&&d.zones.every(z=>z.valid&&z.samples.some(s=>s.valid&&Number.isFinite(s.plankWidthPx)&&s.plankWidthPx>0)));
        geometry.push({backend:canvas?'canvas':'webgl',pattern,...d});
        await shot(p,`geometry-${canvas?'canvas':'webgl'}-${scene}-${pattern}-axes`);
        if(!canvas&&pattern==='pdh'&&['sejour','chambre'].includes(scene))await shot(p,`geometry-demo-${scene}`);
        await p.evaluate(()=>window.__geometryReview.show(false));
      }
    }
    await p.close();
  }
  fs.writeFileSync(path.join(out,'geometry.json'),JSON.stringify(geometry,null,2));
  check('0 browser errors',errors.length===0,errors);
} finally {
  await browser.close();
  fs.writeFileSync(path.join(out,'visual-checks.json'),JSON.stringify({results,errors},null,2));
}
process.exitCode=results.some(r=>!r.pass)||errors.length?1:0;
