/**
 * Bounded photo-guided foreground matte. No camera, plane, floor or lighting input.
 * Only a 2 source-pixel uncertainty band can change. Thin prior branches survive.
 */
export function refineOcclusion(coarse, image, width, height) {
  const start=performance.now(), out=new Uint8ClampedArray(coarse);
  if(!image || image.length!==width*height*4 || !coarse.some(v=>v>0))
    return {alpha:out,changed:0,boundaryPixels:0,ms:performance.now()-start};
  const r=4, seeds=[];
  // Confident seeds have the same class on four sides, 2px away.
  const inside=(x,y)=>coarse[y*width+x]>=128;
  for(let y=r;y<height-r;y++)for(let x=r;x<width-r;x++){
    const i=y*width+x, b=inside(x,y);
    const solid=inside(x-2,y)===b&&inside(x+2,y)===b&&inside(x,y-2)===b&&inside(x,y+2)===b;
    if(solid)continue;
    // Keep slender foreground branches; never erase a few-pixel leg.
    if(b&&((!inside(x-2,y)&&!inside(x+2,y))||(!inside(x,y-2)&&!inside(x,y+2))))continue;
    seeds.push(i);
  }
  let changed=0;
  for(const i of seeds){
    const x=i%width,y=(i-x)/width,p=i*4;
    let fg=Infinity,bg=Infinity;
    for(let dy=-r;dy<=r;dy++)for(let dx=-r;dx<=r;dx++){
      const xx=x+dx,yy=y+dy,j=yy*width+xx,b=inside(xx,yy);
      // A seed must be interior, rather than a mixed/AA boundary pixel.
      if(xx<2||yy<2||xx>=width-2||yy>=height-2)continue;
      if(inside(xx-2,yy)!==b||inside(xx+2,yy)!==b||inside(xx,yy-2)!==b||inside(xx,yy+2)!==b)continue;
      const q=j*4;
      const color=(image[p]-image[q])**2+(image[p+1]-image[q+1])**2+(image[p+2]-image[q+2])**2;
      const score=color+36*(dx*dx+dy*dy);
      if(b)fg=Math.min(fg,score);else bg=Math.min(bg,score);
    }
    if(!Number.isFinite(fg)||!Number.isFinite(bg)||Math.abs(fg-bg)<600)continue;
    // Strong evidence only; no feather expansion or global dilation.
    const value=fg<bg?255:0;
    if(value!==out[i]){out[i]=value;changed++;}
  }

  return {alpha:out,changed,boundaryPixels:seeds.length,ms:performance.now()-start};
}

