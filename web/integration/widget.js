/* Classic one-line loader. CSS/JS of the visualizer stay inside its iframe. */
(()=>{
 const script=document.currentScript;if(!script)return;
 const scriptURL=new URL(script.src,location.href),data={...script.dataset};
 import(new URL('message-protocol.js',scriptURL).href).then(({message,trustedMessage,COMMANDS,isId})=>{
  const url=new URL(data.visualizerUrl||'../../tools/product-concept.html',scriptURL);
  if(url.protocol!=='https:'&&!(url.protocol==='http:'&&['127.0.0.1','localhost','[::1]'].includes(url.hostname)))throw Error('HTTPS required for hosted integration');
  const mode=data.mode==='modal'?'modal':'inline',target=document.createElement(mode==='modal'?'dialog':'div');
  target.style.cssText=mode==='modal'?'padding:0;border:0;border-radius:12px;width:calc(100vw - 24px);height:calc(100dvh - 24px);max-width:1400px;max-height:none;':'width:100%;height:clamp(560px,85dvh,1000px);min-width:0;';
  target.setAttribute('aria-label','Visualiseur de parquet');
  const frame=document.createElement('iframe');frame.title='Visualisez votre parquet chez vous';frame.style.cssText='border:0;width:100%;height:100%;display:block';
  frame.setAttribute('sandbox','allow-scripts allow-same-origin allow-downloads allow-forms allow-popups allow-popups-to-escape-sandbox');
  frame.referrerPolicy='strict-origin-when-cross-origin';if(mode==='modal'){frame.style.height='calc(100% - 48px)';frame.style.marginTop='48px';}
  url.searchParams.set('retailerId',data.retailerId||'demo');url.searchParams.set('catalogId',data.catalogId||'default');url.searchParams.set('locale',data.locale||'fr-FR');url.searchParams.set('mode',mode);url.searchParams.set('parentOrigin',location.origin);
  if(isId(data.productId))url.searchParams.set('productId',data.productId);
  const listeners=new Map(),queue=[];let ready=false,mounted=false,loadingTimer;
  const status=document.createElement('div');status.setAttribute('role','status');status.style.cssText='position:absolute;inset:48px 0 0;background:white;padding:24px;font:16px/1.5 system-ui';status.textContent='Ouverture du visualiseur…';target.style.position='relative';
  const emit=(type,payload)=>{for(const fn of listeners.get(type)||[])try{fn(payload);}catch{/* Host handlers are isolated. */}};
  function send(type,payload={}){let m;try{m=message(type,payload,'command');}catch{return false;}if(!ready){if(queue.length>=20)return false;queue.push(m);}else frame.contentWindow.postMessage(m,url.origin);return true;}
  function mount(){if(mounted)return;mounted=true;target.append(frame,status);if(mode==='modal'){const close=document.createElement('button');close.type='button';close.textContent='Fermer';close.setAttribute('aria-label','Fermer le visualiseur');close.style.cssText='position:absolute;right:8px;top:4px;min-height:44px;z-index:2;border-radius:8px;border:1px solid #ccc;background:white;padding:6px 12px';close.onclick=()=>api.close();target.append(close);document.body.append(target);}else script.insertAdjacentElement('afterend',target);frame.src=url.href;loadingTimer=setTimeout(()=>{if(ready)return;status.textContent='Le visualiseur ne répond pas en mode intégré. ';const a=document.createElement('a'),external=new URL(url);external.searchParams.delete('parentOrigin');external.searchParams.delete('mode');a.href=external.href;a.target='_blank';a.rel='noopener noreferrer';a.textContent='Ouvrir le visualiseur dans un nouvel onglet';status.append(a);},8000);}
  const api={
   open(){mount();if(mode==='modal'&&!target.open)target.showModal();else target.hidden=false;},
   close(){if(mode==='modal')target.close();else target.hidden=true;},
   setProduct:id=>send('SET_PRODUCT',{productId:id}),
   setCatalog:id=>send('SET_CATALOG',{catalogId:id}),
   setFavorites:ids=>send('SET_FAVORITES',{favoriteIds:ids}),
   openRoomSelector:()=>send('OPEN_ROOM_SELECTOR'),resetSession:()=>send('RESET_SESSION'),
   on(type,fn){if(typeof fn!=='function')return()=>{};if(!listeners.has(type))listeners.set(type,new Set());listeners.get(type).add(fn);return()=>listeners.get(type).delete(fn);},
  };
  window.addEventListener('message',e=>{
   if(!trustedMessage(e,{origin:url.origin,source:frame.contentWindow,direction:'event'}))return;
   const {type,payload}=e.data;if(type==='READY'){ready=true;clearTimeout(loadingTimer);status.remove();while(queue.length)frame.contentWindow.postMessage(queue.shift(),url.origin);}
   emit(type,payload);
  });
  window.PoseParquetVisualizer=api;window.dispatchEvent(new Event('pose-parquet-widget-ready'));if(mode==='inline')api.open();
 }).catch(()=>{const error=document.createElement('p');error.textContent='Le visualiseur est indisponible. Réessayez plus tard.';script.insertAdjacentElement('afterend',error);});
})();