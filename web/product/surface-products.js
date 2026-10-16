/* Surface compatibility uses explicit catalogue metadata, never a product name. */
(() => {
  const compatibility = product => {
    if (['interior','exterior','both','unknown'].includes(product?.compatibility)) return product.compatibility;
    return product?.usage === 'terrasse' ? 'exterior' : product?.usage === 'interieur' ? 'interior' : 'unknown';
  };
  const status = (product, surface) => {
    const value=compatibility(product);
    if(value==='unknown'||!['interior_floor','exterior_terrace'].includes(surface))return 'unknown';
    return value==='both'||value===(surface==='exterior_terrace'?'exterior':'interior')?'compatible':'incompatible';
  };
  const defaultProduct = (products,current,surface) => {
    if(current?.renderable!==false&&current?.renderProfile&&status(current,surface)==='compatible')return current;
    return products.find(p=>p.renderable!==false&&p.renderProfile&&status(p,surface)==='compatible')
      ||(status(current,surface)!=='incompatible'?current:null);
  };
  window.PPSurfaceProducts={compatibility,status,defaultProduct};
})();
