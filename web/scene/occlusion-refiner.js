/**
 * Bounded photo-guided foreground matte. No camera, plane, floor or lighting input.
 * Only a 2 source-pixel uncertainty band can change. Thin prior branches survive.
 */
export function refineOcclusion(coarse, image, width, height) {
  const start=performance.now(), out=new Uint8ClampedArray(coarse);
  if(!image || image.length!==width*height*4 || !coarse.some(v=>v>0))
    return {alpha:out,changed:0,boundaryPixels:0,ms:performance.now()-start};
  const r=4, seeds=[], backgrounds=[];
  // Confident seeds have the same class on four sides, 2px away.
  const inside=(x,y)=>coarse[y*width+x]>=128;
  // The same immutable coarse predicate was previously evaluated for every
  // neighbour of every edge pixel (81 times). Cache it once per photo matte.
  const interior=new Uint8Array(width*height);
  for(let y=2;y<height-2;y++)for(let x=2;x<width-2;x++){
    const i=y*width+x,b=coarse[i]>=128;
    interior[i]=((coarse[i-2]>=128)===b&&(coarse[i+2]>=128)===b&&
      (coarse[i-2*width]>=128)===b&&(coarse[i+2*width]>=128)===b)?1:0;
  }
  for(let y=r;y<height-r;y++)for(let x=r;x<width-r;x++){
    const i=y*width+x, b=inside(x,y);
    const solid=interior[i];
    if(solid)continue;
    // Keep slender foreground branches; never erase a few-pixel leg.
    if(b&&((!inside(x-2,y)&&!inside(x+2,y))||(!inside(x,y-2)&&!inside(x,y+2))))continue;
    seeds.push(i);
  }
  let changed=0;
  for(const i of seeds){
    const x=i%width,y=(i-x)/width,p=i*4;
    let fg=Infinity,bg=Infinity,foreground=-1,background=-1;
    for(let dy=-r;dy<=r;dy++)for(let dx=-r;dx<=r;dx++){
      const xx=x+dx,yy=y+dy,j=yy*width+xx,b=inside(xx,yy);
      // A seed must be interior, rather than a mixed/AA boundary pixel.
      if(!interior[j])continue;
      const q=j*4;
      const color=(image[p]-image[q])**2+(image[p+1]-image[q+1])**2+(image[p+2]-image[q+2])**2;
      const score=color+36*(dx*dx+dy*dy);
      if(b&&score<fg){fg=score;foreground=q;}else if(!b&&score<bg){bg=score;background=q;}
    }
    if(foreground<0||background<0)continue;
    // Recover mixed-pixel coverage from the observed foreground/background
    // colours. A binary nearest-class decision discards original edge alpha.
    let numerator=0,contrast=0;
    for(let k=0;k<3;k++){
      const d=image[foreground+k]-image[background+k];
      numerator+=(image[p+k]-image[background+k])*d;contrast+=d*d;
    }
    if(contrast<900)continue; // Ambiguous contact: keep polygon AA as prior.
    let alpha=Math.max(0,Math.min(1,numerator/contrast)),residual=0;
    for(let k=0;k<3;k++){
      const predicted=image[background+k]+alpha*(image[foreground+k]-image[background+k]);
      residual+=(image[p+k]-predicted)**2;
    }
    if(residual>Math.max(432,contrast*.04))continue;
    if(alpha<.03)alpha=0;else if(alpha>.97)alpha=1;
    const value=Math.round(alpha*255);
    // Original C already contains alpha*F + (1-alpha)*oldFloor. Reusing C
    // as straight foreground colour applies alpha twice and retains old wood.
    // Keep reliable background samples for the compositor's inverse blend.
    if(alpha>.03&&alpha<.97)backgrounds.push(i,image[background],image[background+1],image[background+2]);
    if(value!==out[i]){out[i]=value;changed++;}
  }

  return {alpha:out,backgrounds,changed,boundaryPixels:seeds.length,ms:performance.now()-start};
}


/** Build the straight-colour backing plate for the existing SRC_ALPHA blend.
 * This is not lighting input and never replaces the original photograph.
 * Works for partial floor coverage too: P=(C-t*oldFloor)/(1-t), where t is
 * actual replacement coverage. Ambiguous mattes and manual overrides keep C.
 */
export function foregroundCompositeSource(source, coverage, occlusion, prior, backgrounds) {
  if(!source||!backgrounds?.length)return source;
  let data=null,changed=0;
  for(let j=0;j<backgrounds.length;j+=4){
    const i=backgrounds[j];
    if(occlusion[i]!==prior[i]||!coverage[i])continue;
    const t=coverage[i]/255*(1-occlusion[i]/255),retained=1-t;
    if(t<.001||retained<.03)continue;
    const p=i*4,values=[];
    let valid=true;
    for(let k=0;k<3;k++){
      const value=(source.data[p+k]-t*backgrounds[j+1+k])/retained;
      // Large clipping would amplify a bad colour/matte hypothesis.
      if(value< -3||value>258){valid=false;break;}
      values.push(Math.max(0,Math.min(255,Math.round(value))));
    }
    if(!valid||values.every((v,k)=>v===source.data[p+k]))continue;
    if(!data)data=new Uint8ClampedArray(source.data);
    for(let k=0;k<3;k++)data[p+k]=values[k];
    changed++;
  }
  return changed?{data,width:source.width,height:source.height}:source;
}
