import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
fs.mkdirSync('review/wall-paint',{recursive:true});
try {for(const width of (process.env.PPAI_WALL_WIDTHS||'320,390,1440').split(',').map(Number)){
 const p=await browser.newPage({viewport:{width,height:900},isMobile:width<700,hasTouch:width<700});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');await p.waitForFunction(()=>window.__wallPaint&&window.__concept?.adapter.connecte,null,{timeout:90000});
 await p.evaluate(()=>window.__concept.openRoom('chambre-parisienne'));await p.waitForFunction(()=>window.__wallPaint.walls.length===3&&!window.__concept.state.applying&&window.__concept.state.applied.source==='live',null,{timeout:90000});
 const sample=()=>p.evaluate(()=>{const canvas=document.getElementById('after'),ctx=canvas.getContext('2d');return [[.16,.35],[.38,.35],[.85,.3],[.50,.50],[.4,.87]].map(([x,y])=>Array.from(ctx.getImageData(Math.floor(x*canvas.width),Math.floor(y*canvas.height),1,1).data));});
 const before=await sample();await p.locator('#photoMore').click();await p.locator('#wallPaintOpen').click();await p.locator('#wallSelect').selectOption('mur-gauche');await p.getByRole('button',{name:'Sauge',exact:true}).click();await p.waitForFunction(before=>{const n=document.getElementById('after');const actual=Array.from(n.getContext('2d').getImageData(Math.floor(n.width*.16),Math.floor(n.height*.35),1,1).data);return actual.some((v,i)=>v!==before[i]);},before[0]);
 const left=await sample();assert.notDeepEqual(left[0],before[0]);assert.deepEqual(left.slice(1),before.slice(1),'Painting left wall changed another wall, opening or floor');
 await p.locator('#wallSelect').selectOption('mur-fond');await p.getByRole('button',{name:'Terracotta',exact:true}).click();await p.waitForTimeout(100);const both=await sample();assert.notDeepEqual(both[1],before[1]);assert.deepEqual(both[0],left[0]);assert.deepEqual(both.slice(2),before.slice(2));
 const panel=await p.locator('#wallPaintPanel').boundingBox();assert.ok(panel.x>=0&&panel.x+panel.width<=width+1&&panel.y>=0&&panel.y+panel.height<=901,`Panel clipped ${width}`);
 await p.screenshot({path:`review/wall-paint/${width}-panel.jpg`,type:'jpeg',quality:90});await p.locator('#wallClose').click();
 await p.evaluate(()=>window.__concept.select('CHENF36014',true));await p.waitForFunction(()=>!window.__concept.state.applying&&window.__concept.state.applied.key===window.__concept.appliedKey(),null,{timeout:90000});const changed=await sample();assert.deepEqual(changed.slice(0,4),both.slice(0,4),'New floor lost wall paint');assert.notDeepEqual(changed[4],both[4]);
 await p.screenshot({path:`review/wall-paint/${width}-result.jpg`,type:'jpeg',quality:90});
 await p.locator('#baBtn').click();await p.locator('#compareSideBySide').click();assert.ok(await p.locator('#comparisonSides').isVisible());await p.locator('#compareClose').click();
 await p.locator('#photoMore').click();await p.locator('#wallPaintOpen').click();await p.locator('#wallReset').click();await p.waitForTimeout(100);const reset=await sample();assert.deepEqual(reset[1],before[1]);assert.deepEqual(reset[0],left[0]);await p.locator('#wallUndo').click();await p.waitForTimeout(100);assert.deepEqual((await sample())[1],both[1]);
 await p.locator('#wallNew').click();await p.waitForFunction(()=>!document.getElementById('vpWallPaint').hidden);
 const view=await p.evaluate(()=>({...window.__concept.state.vp}));const rect=await p.locator('#wallOutline').boundingBox();const stage=await p.locator('#stage').boundingBox();const x0=Math.max(stage.x+14,rect.x),x1=Math.min(stage.x+stage.width-14,rect.x+rect.width),y0=Math.max(stage.y+90,rect.y),y1=Math.min(650,rect.y+rect.height);
 for(const [x,y]of [[x0+20,y0+30],[x1-20,y0+30],[x1-20,y1-30],[x0+20,y1-30]])await p.mouse.click(x,y);
 assert.deepEqual(await p.evaluate(()=>({...window.__concept.state.vp})),view,'Contour tap panned photograph');await p.locator('#wallConfirm').click();assert.equal(await p.evaluate(()=>window.__wallPaint.walls.length),4);await p.locator('#wallUndo').click();assert.equal(await p.evaluate(()=>window.__wallPaint.walls.length),3);
 await p.locator('#wallClose').click();await p.evaluate(()=>window.__concept.openRoom('cuisine-blanche'));await p.waitForFunction(()=>!window.__concept.state.applying&&window.__concept.state.applied.source==='live',null,{timeout:90000});assert.ok(await p.evaluate(()=>window.__wallPaint.walls.every(w=>!w.color)),'Paint leaked into another room');
 assert.deepEqual(errors,[]);console.log(`PASS ${width}px: independent wall colors, protected opening/floor, floor change, reset/undo, comparisons, contour and room isolation`);await p.close();
}}finally{await browser.close();}