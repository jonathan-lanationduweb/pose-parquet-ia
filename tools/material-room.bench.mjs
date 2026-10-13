import fs from 'node:fs';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
const rows=[],errors=[];
try {
for(let run=0;run<5;run++) {
 const p=await browser.newPage({viewport:{width:1440,height:900}});
 p.on('pageerror',e=>errors.push(e.message));
 p.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await p.goto(`${process.env.PPAI_BASE||'http://127.0.0.1:8000'}/tools/product-concept.html?dev=1&prefetch=0&perf=1`);
 await p.waitForFunction(()=>window.__concept?.adapter.connecte&&window.__concept.DEMO_ROOMS.length,null,{timeout:90000});
 const result=await p.evaluate(async()=>{
  const c=window.__concept,engine=performance.now();
  async function ready(){const start=performance.now();while(c.etatApplication()!=='rendered'||c.state.applying||c.state.pendingApply||c.state.applied.key!==c.appliedKey()){if(performance.now()-start>60000)throw Error('render timeout');await new Promise(r=>setTimeout(r,5));}}
  async function room(id){const start=performance.now();c.openRoom(id);await ready();return performance.now()-start;}
  const firstRoom=await room('chambre'),firstFrame=performance.now();
  const coldRoom=await room('sejour'),warmRoom=await room('chambre');
  window.__perfRaz();const start=performance.now();c.setOrientation(17,false);await ready();const rotation=performance.now()-start;
  const stages=window.__perfRapport();
  const counts={};for(const prod of c.PREMIBEL_DEMO_PRODUCTS){const f=prod.materialFidelity;counts[f]=(counts[f]||0)+1;}
  return {engine,firstRoom,firstFrame,coldRoom,warmRoom,rotation,rotationStages:stages,counts};
 });rows.push({run:run+1,...result});console.log(JSON.stringify(rows.at(-1)));await p.close();
}
}finally{await browser.close();}
fs.writeFileSync('review/premibel-materials/room-performance.json',JSON.stringify({rows,errors},null,2));
if(errors.length||rows.some(r=>r.rotationStages.lignes.some(s=>/^G[0-4]|^G\.tuile|GPU\.material\.upload/.test(s.nom))))throw Error('rotation rebuilt/uploaded a texture or console error');
