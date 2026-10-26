import{message,trustedMessage,isId}from'./message-protocol.js';
import{retailerConfig}from'./retailer-config.js';
import{AnalyticsAdapter}from'./analytics-adapter.js';
import{SceneSession}from'./scene-session.js';
import{JourneyPerformance}from'./journey-performance.js';

export function installRetailerUX(c){
 if(!c)return;
 const $=id=>document.getElementById(id),q=new URLSearchParams(location.search),config=retailerConfig(location.search,location.origin);
 const analytics=new AnalyticsAdapter(e=>window.dispatchEvent(new CustomEvent('pose-parquet:analytics',{detail:e})));
 const perf=new JourneyPerformance({enabled:q.get('telemetry')!=='0'});
 let storage=null;try{storage=sessionStorage;}catch{}
 let sessions=new SceneSession(storage,(config.retailerId||'invalid')+'/'+(config.catalogId||'invalid'));
 const saved=sessions.read();let restoring=true,restored=false;
 let catalogId=config.catalogId;
 const ids=()=>config.valid?config.catalogs[catalogId]:[];
 const allowed=id=>config.valid&&(ids()===null||ids()?.includes(id));
 const find=id=>c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id===id&&allowed(id));
 const favoriteKey=()=>config.retailerId==='demo'&&catalogId==='default'?'pp.favourites.v1':'pp.favourites/'+config.retailerId+'/'+catalogId;
 const emit=(type,payload={})=>{
  let m;try{m=message(type,payload);}catch{return;}
  analytics.event(type,payload);
  if(config.valid&&config.parentOrigin&&window.parent!==window)window.parent.postMessage(m,config.parentOrigin);
 };
 const save=()=>{if(!restoring)sessions.save(c.state);};
 function saveFavorites(set){try{localStorage.setItem(favoriteKey(),JSON.stringify([...set]));}catch{}}
 function favorites(values){
  values=[...new Set(values)];
  if(values.some(id=>!find(id)))return false;
  c.state.favourites=new Set(values);saveFavorites(c.state.favourites);c.paintCatalogue();c.paintCard();
  const n=values.length;$('favCount').textContent=String(n);$('favCount').classList.toggle('hidden',n===0);$('hFav').setAttribute('aria-pressed',String(n>0));return true;
 }
 function loadFavorites(){try{const value=JSON.parse(localStorage.getItem(favoriteKey())||'[]');if(Array.isArray(value))favorites(value.filter(id=>isId(id)&&find(id)).slice(0,1000));}catch{}}
 function setProduct(id){
  const p=find(id);if(!p||p.renderable===false)return false;
  if(c.state.source&&window.PPSurfaceProducts.status(p,c.room().surfaceType)==='incompatible')return false;
  c.select(id,true);return c.state.productId===id;
 }
 function setCatalog(id){
  if(!Object.hasOwn(config.catalogs||{},id))return false;
  const permitted=config.catalogs[id],products=c.PREMIBEL_DEMO_PRODUCTS.filter(p=>(permitted===null||permitted.includes(p.id))&&p.renderable!==false&&(!c.state.source||window.PPSurfaceProducts.status(p,c.room().surfaceType)!=='incompatible'));
  if(!products.length)return false;
  catalogId=id;sessions=new SceneSession(storage,config.retailerId+'/'+catalogId);if(!allowed(c.state.productId))c.select(products[0].id,true);
  loadFavorites();c.paintCatalogue();save();return true;
 }
 function reset(){window.__sessionRooms?.clear();window.__sessionRooms?.home();c.clearAnalysisCache();c.state.orientationDeg=0;c.state.floorScale=1;c.state.compare=null;const initial=find(config.productId)||c.PREMIBEL_DEMO_PRODUCTS.find(p=>allowed(p.id)&&p.renderable!==false);if(initial)setProduct(initial.id);sessions.clear();}
 window.__retailerUX={config,emit,allowed,saveFavorites,performance:perf,
  tapCorrection(){return {supported:false,reason:'automatic_local_correction_unavailable'};},
  progressiveResult({generation,stage='fast'}={}){return {accepted:generation===c.state.photoGeneration&&['fast','refined'].includes(stage),implemented:false};},
 };
 window.addEventListener('message',e=>{
  if(!config.valid||!trustedMessage(e,{origin:config.parentOrigin,source:window.parent,direction:'command'}))return;
  const {type,payload}=e.data;let ok=false;
  if(type==='SET_PRODUCT')ok=setProduct(payload.productId);
  if(type==='SET_CATALOG')ok=setCatalog(payload.catalogId);
  if(type==='SET_FAVORITES')ok=favorites(payload.favoriteIds);
  if(type==='OPEN_ROOM_SELECTOR'){c.openRooms();ok=true;}
  if(type==='RESET_SESSION'){reset();ok=true;}
  emit('COMMAND_RESULT',{command:type,ok,code:ok?'ok':'unsupported_or_unavailable'});
 });
 const notice=document.createElement('p');notice.id='retailerNotice';notice.className='pp-link-note';notice.setAttribute('role','status');notice.hidden=true;document.querySelector('#entry .entry-in')?.prepend(notice);
 const tell=text=>{notice.textContent=text;notice.hidden=false;};
 function restore(){
  if(restored||!c.DEMO_ROOMS.length)return;restored=true;if(!config.valid){restoring=false;return;}
  const hasLink=q.has('productId')||q.has('roomId');
  const productId=q.get('productId')||(!hasLink?saved?.productId:null);
  const roomId=q.get('roomId')||(!hasLink&&saved?.source==='demo'?saved.roomId:null);
  const angle=hasLink?Number(q.get('angle')||0):saved?.orientation||0;
  if(roomId&&c.DEMO_ROOMS.some(r=>r.id===roomId)){c.openRoom(roomId);if(!hasLink)analytics.track('session_restored',{source:'demo'});}
  if(productId){if(!setProduct(productId))tell('Cette référence ne dispose pas d’un aperçu compatible. Choisissez un autre parquet.');else if(q.has('productId'))tell('Visualisez '+c.product().name+' chez vous.');}
  if(Number.isFinite(angle)&&angle>=0&&angle<360&&c.state.source)c.setOrientation(angle,false);
  if(!hasLink&&saved?.source==='demo'&&saved.scale){c.state.floorScale=saved.scale;c.paint();}
  if(!hasLink&&saved?.source==='uploaded')tell('Pour retrouver votre pièce, importez de nouveau la même photo. Aucune photo n’a été conservée après rechargement.');
  loadFavorites();restoring=false;save();
 }
 window.addEventListener('pp:library-ready',restore);restore();
 window.addEventListener('pp:journey',e=>{
  const name=e.detail?.name;
  if(name==='photo:choisie')perf.start();
  const steps={'photo:affichee':'photoDisplayed','analyse:debut':'analysisStarted','scene:posee':'sceneReady','scene:manuelle':'sceneReady','rendu:premier':'firstFloorRender'};
  if(steps[name])perf.mark(steps[name]);
  if(name==='produit_rendu'&&c.state.source==='uploaded'){perf.mark('firstFloorRender');requestAnimationFrame(()=>{if(c.etatProduit()==='RENDER_READY')perf.mark('interactiveReady');});}
  if(name==='photo:affichee')emit('PHOTO_IMPORTED',{source:'uploaded'});
  if(name==='analyse:echec')emit('ANALYSIS_COMPLETED',{status:'unavailable'});
  if(name==='scene:posee')emit('ANALYSIS_COMPLETED',{status:c.adapter.geometryValidation?.status==='degraded'?'approximate':'ready'});
  if(name==='scene:refusee'||name==='analyse:fin'&&!['auto_render','approximate_render'].includes(c.state.roomAnalysis.analysis?.experimental?.floor?.sceneStatus))emit('ANALYSIS_COMPLETED',{status:'manual'});
  if(name==='piece:selection')emit('ROOM_SELECTED',{roomId:c.state.roomId});
  if(name==='produit:selection')emit('PRODUCT_SELECTED',{productId:c.state.productId});
  if(name==='favori:ajout')emit('FAVORITE_ADDED',{productId:e.detail.productId});
  if(name==='favori:retrait')emit('FAVORITE_REMOVED',{productId:e.detail.productId});
  if(name==='comparaison:ouverte')emit('COMPARE_OPENED',{productId:c.state.productId});
  if(['produit_rendu','photo:affichee','piece:selection','produit:selection','orientation:change'].includes(name))save();
 });
 window.addEventListener('pp:download',()=>emit('DOWNLOAD_COMPLETED',{productId:c.state.productId}));
 window.addEventListener('pagehide',save);
 document.addEventListener('click',e=>{
  const a=e.target.closest('a[data-sheet],#ficheLegere a[href]');if(!a)return;
  const productId=a.dataset.sheet?c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.ref===a.dataset.sheet)?.id:c.state.productId;if(!productId)return;
  if(config.parentOrigin&&window.parent!==window)e.preventDefault();
  emit('PRODUCT_PAGE_REQUESTED',{productId});
 },true);

 const help=document.createElement('p');help.className='pp-photo-help';help.textContent='Montrez le sol, cadrez la pièce et évitez une photo trop près du sol.';
 document.querySelector('.doors').insertAdjacentElement('beforebegin',help);
 const dialog=(id,title)=>{const d=document.createElement('dialog');d.id=id;d.className='pp-dialog';const close=document.createElement('button');close.type='button';close.className='pp-close';close.textContent='Fermer';close.onclick=()=>d.close();const h=document.createElement('h2');h.textContent=title;d.append(close,h);document.body.append(d);return d;};
 const share=dialog('shareResult','Partager votre choix'),body=document.createElement('div');share.append(body);
 const shareButton=document.createElement('button');shareButton.type='button';shareButton.id='shareResultOpen';shareButton.textContent='Partager mon choix';
 shareButton.onclick=()=>{
  if(!c.state.source)return;body.replaceChildren();const privatePhoto=c.state.source==='uploaded';emit('SHARE_REQUESTED',{kind:privatePhoto?'private':'demo'});
  const p=document.createElement('p');
  if(privatePhoto){p.textContent='Partagez l’image de votre rendu. Le partage de votre photo par lien n’est pas encore disponible.';body.append(p);const b=document.createElement('button');b.type='button';b.textContent='Télécharger mon rendu';b.onclick=()=>document.querySelector('#photoActions [aria-label="Télécharger le rendu"]').click();body.append(b);}
  else{
   const url=new URL(location.pathname,location.origin);for(const [key,value]of Object.entries({retailerId:config.retailerId,catalogId,locale:config.locale,productId:c.state.productId,roomId:c.state.roomId,pattern:c.product().pattern,angle:c.state.orientationDeg})){if(value!=null)url.searchParams.set(key,value);}
   p.textContent='Ce lien retrouve la pièce, le produit et le sens de pose. Les photos personnelles ne sont pas incluses.';body.append(p);
   const input=document.createElement('input');input.id='shareResultLink';input.readOnly=true;input.value=url.href;input.setAttribute('aria-label','Lien de votre choix');body.append(input);
   const copy=document.createElement('button');copy.type='button';copy.textContent='Copier le lien';copy.onclick=async()=>{try{await navigator.clipboard.writeText(input.value);copy.textContent='Lien copié';}catch{input.focus();input.select();copy.textContent='Sélectionnez et copiez le lien';}};body.append(copy);
   if(['127.0.0.1','localhost'].includes(url.hostname)){const note=document.createElement('p');note.className='pp-link-note';note.textContent='Ce lien local fonctionne sur ce PC. Le partage à distance utilisera l’adresse publique de votre site.';body.append(note);}
  }
  share.showModal();
 };
 $('photoActions').append(shareButton);
 const zoom=dialog('materialZoom','Le bois de plus près');
 function zoomMaterial(){
  analytics.track('product_view',{productId:c.state.productId});
  zoom.querySelectorAll('[data-content]').forEach(n=>n.remove());const box=document.createElement('div');box.dataset.content='';
  const sw=document.querySelector('#card .sw'),ready=sw?.dataset.materialPreviewReady==='true',p=document.createElement('p');
  p.textContent=ready?(c.product().materialFidelity==='exact'?'Rendu matière issu du produit.':'Matière représentative : la teinte réelle peut varier.'):'Photo du produit : cette image peut montrer une pièce complète.';
  const img=document.createElement('img');img.alt=p.textContent;const bg=sw&&getComputedStyle(sw).backgroundImage;const match=bg?.match(/^url\(["']?(.*?)["']?\)$/);img.src=match?.[1]||c.product().thumbnail||c.product().catalogThumbnail||'';box.append(p,img);zoom.append(box);zoom.showModal();
 }
 const zoomButton=document.createElement('button');zoomButton.type='button';zoomButton.textContent='Voir la matière';zoomButton.onclick=zoomMaterial;$('photoActions').append(zoomButton);
 const annotate=()=>{const sw=document.querySelector('#card .sw');if(sw){sw.setAttribute('role','button');sw.tabIndex=0;sw.setAttribute('aria-label','Voir la matière');}};
 new MutationObserver(annotate).observe($('card'),{childList:true,subtree:true});annotate();
 $('card').addEventListener('click',e=>{if(e.target.closest('.sw'))zoomMaterial();});
 $('card').addEventListener('keydown',e=>{if(e.target.closest('.sw')&&['Enter',' '].includes(e.key)){e.preventDefault();zoomMaterial();}});
 const guide=dialog('captureGuide','Cadrez votre pièce');
 const frame=document.createElement('div');frame.className='pp-guide-frame';frame.innerHTML='<span>Gardez le sol visible · repère indicatif</span>';
 const guidance=document.createElement('p');guidance.textContent='Reculez légèrement et gardez la pièce entière dans le cadre. Ce repère prépare la prise de photo ; il ne détecte pas la position du téléphone.';
 const input=document.createElement('input');input.type='file';input.accept='image/jpeg,image/png,image/webp';input.setAttribute('capture','environment');input.hidden=true;input.onchange=()=>{const file=input.files?.[0];guide.close();if(file)c.loadUpload(file);input.value='';};
 const capture=document.createElement('button');capture.type='button';capture.textContent='Prendre la photo';capture.onclick=()=>input.click();guide.append(frame,guidance,capture,input);
 const openCapture=document.createElement('button');openCapture.id='guidedPhotoOpen';openCapture.type='button';openCapture.className='pp-mobile-capture';openCapture.textContent='Prendre une photo';openCapture.onclick=()=>guide.showModal();const entryActions=document.createElement('div');entryActions.className='pp-entry-actions';

 entryActions.append(openCapture);help.insertAdjacentElement('beforebegin',entryActions);
 if(!config.valid)tell('Cette intégration n’est pas configurée. Contactez votre magasin.');
 else emit('READY',{retailerId:config.retailerId,catalogId,locale:config.locale});
}