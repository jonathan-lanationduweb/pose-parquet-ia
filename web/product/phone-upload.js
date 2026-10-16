const input=document.getElementById('phonePhoto'),preview=document.getElementById('phonePreview'),send=document.getElementById('phoneSend'),status=document.getElementById('phoneStatus'),pick=document.querySelector('.phone-pick');
const token=location.hash.slice(1);let photo=null,url=null,busy=false,generation=0;
if(!/^[A-Za-z0-9_-]{32}$/.test(token)){status.textContent='Ce lien est incomplet. Scannez un nouveau QR code sur le PC.';input.disabled=true;pick.hidden=true;}
input.addEventListener('change',async()=>{
  const file=input.files?.[0];if(!file||busy)return;const gen=++generation;send.hidden=true;photo=null;preview.hidden=true;
  if(file.size>40*1024*1024){status.textContent='Cette photo est trop volumineuse. Choisissez une autre photo.';return;}
  status.textContent='Préparation de la photo…';const source=URL.createObjectURL(file);
  try{const img=new Image();img.src=source;await img.decode();if(gen!==generation)return;
    const ratio=Math.min(1,2560/Math.max(img.naturalWidth,img.naturalHeight));const canvas=document.createElement('canvas');canvas.width=Math.round(img.naturalWidth*ratio);canvas.height=Math.round(img.naturalHeight*ratio);canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);
    photo=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.92));if(gen!==generation)return;if(!photo)throw new Error();
    if(url)URL.revokeObjectURL(url);url=URL.createObjectURL(photo);preview.src=url;preview.hidden=false;send.hidden=false;status.textContent='Votre photo est prête.';
  }catch{status.textContent='Photo illisible. Essayez une photo JPEG, PNG ou WebP.';}
  finally{URL.revokeObjectURL(source);}
});
send.addEventListener('click',async()=>{
 if(!photo||busy)return;busy=true;send.disabled=true;input.disabled=true;status.textContent='Envoi en cours…';
 try{const response=await fetch(`/v1/photo-transfers/${token}/photo`,{method:'PUT',headers:{'Content-Type':'image/jpeg'},body:photo});if(!response.ok){const data=await response.json();throw new Error(typeof data.detail==='string'?data.detail:'Envoi impossible. Réessayez.');}
  status.textContent='Photo envoyée ! Retrouvez le résultat sur votre PC.';send.hidden=true;pick.hidden=true;photo=null;
 }catch(e){status.textContent=e.message||'Connexion interrompue. Réessayez.';send.disabled=false;input.disabled=false;}
 finally{busy=false;}
});
window.addEventListener('pagehide',()=>{generation++;if(url)URL.revokeObjectURL(url);});
