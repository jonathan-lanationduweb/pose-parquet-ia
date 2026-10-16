/** Phone -> PC, paired by a short-lived QR link. No account or password. */
export function installPhoneTransfer(c) {
  const home=document.querySelector('.doors'),entry=document.getElementById('entry');
  const desktop=window.matchMedia('(min-width:701px)');
  const card=document.createElement('section');card.id='phoneImport';card.className='phone-import-card';card.setAttribute('aria-label','Importer depuis mon téléphone');
  card.innerHTML=`<h3>Depuis votre téléphone</h3><img id="transferQr" width="196" height="196" alt="QR code pour envoyer une photo vers ce PC" hidden><p>Scannez avec votre appareil photo</p><p id="transferStatus" role="status"></p><a id="transferLink" target="_blank" rel="noopener noreferrer" hidden></a><button id="transferRenew" type="button" hidden>Nouveau QR code</button><p class="transfer-note">Sans compte · Gardez cette page ouverte sur le PC</p>`;
  home.insertBefore(card,document.getElementById('doorRooms'));
  const dialog=document.createElement('dialog');dialog.id='phoneTransfer';
  dialog.innerHTML='<button type="button" class="transfer-close" aria-label="Fermer le QR code">×</button>';
  document.body.append(dialog);
  const link=card.querySelector('#transferLink');
  const image=card.querySelector('img'),status=card.querySelector('[role="status"]'),renew=card.querySelector('#transferRenew');
  let transfer=null,blobUrl=null,timer=0,generation=0,controller=null,qrModules=0;
  function sizeQr(){if(!qrModules)return;const available=Math.max(0,card.clientWidth-32);image.style.width=(qrModules*Math.max(1,Math.floor(Math.min(256,available)/qrModules)))+'px';}
  new ResizeObserver(sizeQr).observe(card);
  const api='/v1/photo-transfers';
  function release(){generation++;clearTimeout(timer);controller?.abort();controller=null;if(blobUrl)URL.revokeObjectURL(blobUrl);blobUrl=null;image.hidden=true;link.hidden=true;link.removeAttribute('href');if(transfer){const t=transfer;transfer=null;fetch(`${api}/${t.id}`,{method:'DELETE',headers:{'X-Transfer-Key':t.ownerKey},keepalive:true}).catch(()=>{});}}
  async function message(response){let data;try{data=await response.json();}catch{}return typeof data?.detail==='string'?data.detail:'Le transfert est indisponible. Réessayez.';}
  async function begin(){
    release();const gen=generation;renew.hidden=true;status.textContent='Préparation du QR code…';
    controller=new AbortController();const signal=controller.signal;
    try{
      const response=await fetch(api,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({origin:location.origin}),signal});
      if(!response.ok)throw new Error(response.status===404?'Le serveur doit être mis à jour pour activer le transfert.':await message(response));
      const t=await response.json();if(gen!==generation){fetch(`${api}/${t.id}`,{method:'DELETE',headers:{'X-Transfer-Key':t.ownerKey},keepalive:true}).catch(()=>{});return;}
      transfer=t;link.href=t.phoneUrl;link.textContent='Lien téléphone : '+new URL(t.phoneUrl).hostname;link.hidden=false;const qr=await fetch(`${api}/${t.id}/qr.svg`,{headers:{'X-Transfer-Key':t.ownerKey},signal});
      if(!qr.ok)throw new Error(await message(qr));const blob=await qr.blob();const svg=await blob.text();if(gen!==generation)return;qrModules=Number(svg.match(/viewBox="0 0 (\d+) \d+"/)?.[1])||0;sizeQr();
      blobUrl=URL.createObjectURL(blob);image.src=blobUrl;image.hidden=false;status.textContent='En attente de votre photo…';poll(gen);
    }catch(e){if(gen!==generation)return;status.textContent=e.message||'Connexion impossible. Réessayez.';renew.hidden=false;}
  }
  async function poll(gen){
    if(gen!==generation||!transfer)return;
    const t=transfer,headers={'X-Transfer-Key':t.ownerKey};
    try{
      const response=await fetch(`${api}/${t.id}`,{headers,signal:controller.signal});if(gen!==generation)return;
      if(response.status===404){if(isActive())begin();else release();return;}
      if(!response.ok)throw new Error(await message(response));
      const data=await response.json();
      if(data.status==='ready'){
        status.textContent='Réception de la photo…';const photo=await fetch(`${api}/${t.id}/photo`,{headers,signal:controller.signal});
        if(!photo.ok||photo.status===204)throw new Error('Photo indisponible. Réessayez.');
        const blob=await photo.blob();if(gen!==generation)return;
        c.loadUpload(new File([blob],'photo-telephone.jpg',{type:'image/jpeg'}));dialog.close();release();return;
      }
      image.hidden=false;link.hidden=false;status.textContent='En attente de votre photo…';
    }catch(e){if(gen!==generation)return;image.hidden=true;link.hidden=true;status.textContent='Connexion au PC interrompue. Reconnexion…';}
    timer=setTimeout(()=>poll(gen),1500);
  }
  function isActive(){return desktop.matches&&(!entry.classList.contains('hidden')||dialog.open);}
  function refresh(){if(isActive()){if(!transfer&&!controller)begin();}else if(transfer||controller)release();}
  function open(){c.closeAll();dialog.append(card);dialog.showModal();if(!transfer&&!controller)begin();}
  const target=document.getElementById('sheetImport')?.parentElement;
  if(target){const b=document.createElement('button');b.type='button';b.id='sheetPhoneImport';b.className='phone-import';b.textContent='Importer depuis mon téléphone';b.onclick=open;target.append(b);}
  renew.onclick=begin;dialog.querySelector('.transfer-close').onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{home.insertBefore(card,document.getElementById('doorRooms'));refresh();});
  new MutationObserver(refresh).observe(entry,{attributes:true,attributeFilter:['class']});
  desktop.addEventListener('change',refresh);window.addEventListener('pageshow',refresh);
  window.addEventListener('pagehide',release);refresh();
}
