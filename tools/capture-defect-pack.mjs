/** Generate a private, reproducible source-resolution diagnostic pack. */
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {defectReport,reportText} from '../web/product/defect-report.js';
const args={};
for(let i=2;i<process.argv.length;i++){const key=process.argv[i];if(!key.startsWith('--'))throw Error('Expected --option');args[key.slice(2)]=process.argv[i+1]?.startsWith('--')?true:process.argv[++i]??true;}
if(args.help){console.log('node tools/capture-defect-pack.mjs --scene piece-claire --product BTRPF39009 --pattern baton-rompu --angle 0 --viewport 1440x900 --case case-001\nImported scene: --scene-file <local SceneData.json> --image <original.png>\nOptional: --report <DefectReport.json> --reference <local Roomvo capture.png> --no-pattern\nRequires a local server (PPAI_BASE, default http://127.0.0.1:8000) and PPAI_PLAYWRIGHT_CORE.');process.exit(0);}
const allowed=new Set(['scene','scene-file','image','product','pattern','angle','viewport','case','report','reference','no-pattern']);
for(const k of Object.keys(args))if(!allowed.has(k))throw Error('Unknown option '+k);
if(!args.scene&&!args['scene-file'])throw Error('Supply --scene or --scene-file');
if(args.scene&&args['scene-file'])throw Error('Choose one scene source');
if(args['scene-file']&&!args.image)throw Error('Imported scene needs its original --image');
if(args.image&&!/\.(png|jpg|jpeg|webp)$/i.test(args.image))throw Error('Original must be JPEG, PNG or WebP');
const id=args.case||'case-'+(args.scene||'imported')+'-'+(args.product||'BTRPF39009');
if(!/^[a-zA-Z0-9_-]{1,100}$/.test(id))throw Error('Invalid case id');
const [width,height]=String(args.viewport||'1440x900').split('x').map(Number);
if(![width,height].every(v=>Number.isInteger(v)&&v>=200&&v<=4096))throw Error('Invalid viewport');
const angle=Number(args.angle||0);if(!Number.isFinite(angle))throw Error('Invalid angle');
const root=path.resolve('review/defects'),out=path.join(root,id);fs.mkdirSync(out,{recursive:true});
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
const mime=p=>/\.png$/i.test(p)?'image/png':/\.webp$/i.test(p)?'image/webp':'image/jpeg';
try{
 const page=await browser.newPage({viewport:{width,height}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const base=process.env.PPAI_BASE||'http://127.0.0.1:8000';
 if(args['scene-file'])await page.route('**/__defect-source-image',r=>r.fulfill({contentType:mime(args.image),body:fs.readFileSync(args.image)}));
 await page.goto(base+'/tools/product-concept.html?dev=1&prefetch=0');
 await page.waitForFunction(()=>window.__concept?.adapter.connecte&&window.__visualDiagnostics,null,{timeout:90000});
 if(args['scene-file']){
  const raw=JSON.parse(fs.readFileSync(args['scene-file'],'utf8'));raw.id='diagnostic-imported';raw.label='Photo de diagnostic';
  await page.evaluate(async({raw,url})=>{if(!await window.__concept.adapter.openPhotoScene(raw,url))throw Error(window.__concept.adapter.refusScene);},{raw,url:base+'/__defect-source-image'});
 }else{
  const available=await page.evaluate(id=>window.__concept.DEMO_ROOMS.some(r=>r.id===id),args.scene);
  if(available){await page.evaluate(id=>window.__concept.openRoom(id),args.scene);await page.waitForFunction(()=>!window.__concept.state.applying&&window.__concept.adapter.scene===window.__concept.room().id,null,{timeout:90000});}
  else await page.evaluate(async id=>{if(!await window.__concept.adapter.openRoom(id))throw Error('Unknown renderer scene');},args.scene);
 }
 const result=await page.evaluate(async input=>{
  const c=window.__concept,product=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id===(input.product||c.state.productId));
  if(!product||product.renderable===false)throw Error('Product unavailable');
  if(input.pattern&&!['lames','baton-rompu','point-de-hongrie'].includes(input.pattern))throw Error('Invalid pattern');
  const profile={...product.renderProfile,...(input.pattern?{pattern:input.pattern}:{})};
  if(c.state.source==='demo'&&window.PPSurfaceProducts.status(product,c.room().surfaceType)==='incompatible')throw Error('Product incompatible with selected room');
  const failed=c.adapter.geometryValidation?.status==='failed';
  const frame=await c.adapter.applyProfile(profile,input.angle);if(!failed&&!frame)throw Error('Render failed');
  c.state.productId=product.id;
  // This exports full source images; no viewport crop is baked into them.
  const flags=['debugGrid','debugMasks','debugCamera','debugFloorPlane','debugScale',...(input.patternIds?['debugPattern']:[])];
  const pack=window.__visualDiagnostics.capture(flags);
  pack.metadata.productId=product.id;pack.metadata.floorAngle=input.angle;pack.metadata.pattern=profile.pattern;
  pack.metadata.exportTransform={kind:'source image',scale:1,offsetX:0,offsetY:0};
  if(!c.state.source)pack.metadata.ViewTransform={available:false,reason:'Direct SceneData capture; source-image exports use exportTransform'};
  const png=c=>c.toDataURL('image/png').split(',')[1],images=Object.fromEntries(Object.entries(pack.images).map(([k,v])=>[k,png(v)]));
  const signature=JSON.stringify(c.adapter.diagnosticSnapshot().scene.floorZones.map(z=>z.plane.projection));
  if(!failed){const unlit=await c.adapter.diagnosticUnlitFrame();if(!unlit)throw Error('Unlit diagnostic failed');images.unlit=png(unlit);const neutral=await c.adapter.diagnosticNeutralFrame();if(!neutral)throw Error('Neutral diagnostic failed');images.neutral=png(neutral);}
  if(JSON.stringify(c.adapter.diagnosticSnapshot().scene.floorZones.map(z=>z.plane.projection))!==signature)throw Error('Diagnostic changed camera');
  return {images,metadata:pack.metadata};
 },{product:args.product||null,pattern:args.pattern||null,angle,patternIds:!args['no-pattern']});
 if(errors.length)throw Error(errors.join('\n'));
 const names={original:'01-original.png',render:'02-render.png',debugGrid:'03-debug-grid.png',debugMasks:'04-debug-masks.png',debugCamera:'05-debug-camera.png',debugScale:'06-debug-scale.png',debugFloorPlane:'07-debug-floor-plane.png',debugPattern:'08-debug-pattern.png',unlit:'09-unlit.png',floorMask:'10-floor-mask-raw.png',occluderMask:'11-occluder-mask-raw.png',floorSpacePattern:'13-pattern-floor-space.png',neutral:'14-neutral.png'};
 for(const [key,data]of Object.entries(result.images))fs.writeFileSync(path.join(out,names[key]),Buffer.from(data,'base64'));
 let nativeOriginal=null;
 if(args.image){
  nativeOriginal='00-original-native'+path.extname(args.image).toLowerCase();
  fs.copyFileSync(args.image,path.join(out,nativeOriginal));
  result.metadata.originalNativeSize=await page.evaluate(async url=>{const im=new Image();im.src=url;await im.decode();return{width:im.naturalWidth,height:im.naturalHeight};},base+'/__defect-source-image');
  result.metadata.rendererImageSize=result.metadata.imageSize;
 }
 let reference=null;if(args.reference){reference='12-reference'+path.extname(args.reference).toLowerCase();if(!/\.(png|jpg|jpeg|webp)$/.test(reference))throw Error('Reference must be a local image');fs.copyFileSync(args.reference,path.join(out,reference));}
 const report=defectReport(args.report?JSON.parse(fs.readFileSync(args.report,'utf8')):{id,sceneId:result.metadata.sceneId,imageSize:result.metadata.imageSize,defects:[],confirmedCorrect:[],references:{original:true,roomvo:!!reference}});
 if(report.sceneId!==result.metadata.sceneId)throw Error('Report scene does not match captured scene');
 result.metadata.caseId=id;result.metadata.renderBackend=await page.evaluate(()=>window.__concept.adapter.diagnosticSnapshot()?.config?window.__concept.adapter.moteur?.backend:null);
 result.metadata.references={original:true,roomvo:!!reference};result.metadata.invariants={diagnosticCameraUnchanged:true,pageErrors:errors};
 fs.writeFileSync(path.join(out,'metadata.json'),JSON.stringify(result.metadata,null,2));
 fs.writeFileSync(path.join(out,'defect-report.json'),JSON.stringify(report,null,2));fs.writeFileSync(path.join(out,'defect-report.txt'),reportText(report));
 const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
 const gallery=Object.entries(result.images).map(([key])=>'<figure><a href="'+names[key]+'"><img loading="lazy" src="'+names[key]+'"></a><figcaption>'+esc(key)+'</figcaption></figure>').join('');
 fs.writeFileSync(path.join(out,'index.html'),'<!doctype html><html lang="fr"><meta charset="utf-8"><title>'+esc(id)+'</title><style>body{font:16px system-ui;margin:24px;background:#f5f4ef}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}img{max-width:100%}figure{margin:0}pre{white-space:pre-wrap}</style><h1>'+esc(id)+'</h1><p>Original + couches réelles du moteur, en résolution source. Aucune validation esthétique automatique.</p><p><a href="metadata.json">Metadata</a> · <a href="defect-report.json">DefectReport</a></p><main>'+(nativeOriginal?'<figure><a href='+nativeOriginal+'><img loading=lazy src='+nativeOriginal+'></a><figcaption>Original natif fourni, sans réduction</figcaption></figure>':'')+gallery+(reference?'<figure><img src="'+reference+'"><figcaption>Référence fournie localement</figcaption></figure>':'')+'</main><pre>'+esc(reportText(report))+'</pre></html>');
 const packs=fs.readdirSync(root,{withFileTypes:true}).filter(e=>e.isDirectory()&&fs.existsSync(path.join(root,e.name,'metadata.json')));
 fs.writeFileSync(path.join(root,'index.html'),'<!doctype html><html lang="fr"><meta charset="utf-8"><title>Defect packs</title><h1>Packs de diagnostic privés</h1><p>Pas de verdict de réalisme automatique.</p><ul>'+packs.map(e=>'<li><a href="'+encodeURIComponent(e.name)+'/index.html">'+esc(e.name)+'</a></li>').join('')+'</ul></html>');
 console.log('Diagnostic pack generated: '+out+' ('+Object.keys(result.images).length+' images). Human report pending unless supplied.');
}finally{await browser.close();}
