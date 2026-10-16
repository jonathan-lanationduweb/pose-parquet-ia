import fs from 'node:fs';import assert from 'node:assert/strict';import{createRequire}from'node:module';
const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);const browser=await chromium.launch({channel:'chrome',headless:true});
try{const p=await browser.newPage({viewport:{width:1440,height:1000}});await p.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');await p.evaluate(async()=>{const{createLocalRenderer}=await import('/web/product/local-renderer.js');window.reviewRenderer=await createLocalRenderer({base:'/web/'});});
for(const id of ['cuisine-blanche','cuisine-ilot','bureau-meuble','salle-a-manger-meublee','terrasse-mer']){
 const raw=JSON.parse(fs.readFileSync(`web/data/scenes/${id}.json`,'utf8'));
 for(const [material,pattern,width,length]of [['chene-naturel','lames',.19,1.9],['ipe-terrasse','lames',.14,2],['chene-naturel','baton-rompu',.09,.6]]){
 const data=await p.evaluate(async({raw,id,material,pattern,width,length})=>{const r=window.reviewRenderer;await r.openScene(raw,`/web/assets/images/${raw.image.file}`,id);r.selectMaterial(material);r.setPattern(pattern);r.setWidth(width);r.setPlankLength(length);await r.rendre();return r.canvas.toDataURL('image/jpeg',.94);},{raw,id,material,pattern,width,length});
 fs.writeFileSync(`review/room-expansion/${id}-${material}-${pattern}.jpg`,Buffer.from(data.split(',')[1],'base64'));
 }console.log('RENDERED',id);
}
}finally{await browser.close();}
