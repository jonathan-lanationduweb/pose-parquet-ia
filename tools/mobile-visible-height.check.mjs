import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 await page.addInitScript(()=>{const viewport=new EventTarget();Object.assign(viewport,{height:720,width:390,offsetTop:0,offsetLeft:0,scale:1});Object.defineProperty(window,'visualViewport',{value:viewport,configurable:true});});
 await page.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');await page.waitForFunction(()=>window.__concept?.adapter.connecte);
 await page.evaluate(()=>window.__concept.openRoom('cuisine-ouverte'));await page.waitForFunction(()=>window.__concept.etatApplication()==='rendered',null,{timeout:60000});
 for(const height of [720,620,760]){
  await page.evaluate(height=>{visualViewport.height=height;visualViewport.dispatchEvent(new Event('resize'));},height);
  await page.waitForTimeout(100);
  const rect=await page.locator('#card').boundingBox();assert.ok(rect.y+rect.height<=height,`Card below visible viewport ${height}`);
  for(const name of ['Choisir un parquet','Personnaliser']){const b=await page.locator('#card').getByRole('button',{name,exact:true}).boundingBox();assert.ok(b&&b.y+b.height<=height,`Button ${name} clipped`);}
  console.log(`PASS visible ${height}px / layout 844px: all bottom commands visible`);
 }
 await page.screenshot({path:'review/current-fixes/phone-visible-height.jpg'});
}finally{await browser.close();}
