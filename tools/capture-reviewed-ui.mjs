import fs from 'node:fs';import{createRequire}from'node:module';
const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE),browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const p=await browser.newPage({viewport:{width:1440,height:900}});
 await p.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');
 await p.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 await p.evaluate(()=>window.__concept.openRoom('salle-a-manger-meublee'));
 await p.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY'&&!window.__concept.state.applying,null,{timeout:90000});
 await p.screenshot({path:'review/common-foreground-review/dining-ui.png'});
 console.log('Normal UI ready; dining screenshot saved.');
}finally{await browser.close();}
