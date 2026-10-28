/** DEV photo + logical foreground only. No material, camera or lighting pass. */
export function foregroundOverlay(snapshot) {
  const {width,height}=snapshot.size;
  const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
  const ctx=canvas.getContext('2d');ctx.drawImage(snapshot.photo,0,0,width,height);
  const mask=document.createElement('canvas');mask.width=width;mask.height=height;
  const m=mask.getContext('2d');m.fillStyle='#ff0000';
  const trace=polygon=>{polygon.forEach((p,i)=>{const x=p.x*width,y=p.y*height;i?m.lineTo(x,y):m.moveTo(x,y);});m.closePath();};
  for(const object of snapshot.scene.occluders||[]){
    if(object.kind==='fixture')continue;
    m.beginPath();trace(object.polygon);for(const hole of object.holes||[])trace(hole);m.fill('evenodd');
  }
  ctx.globalAlpha=.45;ctx.drawImage(mask,0,0);ctx.globalAlpha=1;
  return canvas;
}
