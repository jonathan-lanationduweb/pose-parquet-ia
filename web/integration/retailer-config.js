import{isId}from'./message-protocol.js';
/** Deployment-owned registry. URL parameters NEVER add trusted origins or catalogs. */
export const RETAILERS=Object.freeze({
 demo:{catalogs:{default:null},allowedParentOrigins:[],locale:'fr-FR',features:{share:true,download:true}},
});
export function retailerConfig(search,origin,registry=RETAILERS){
 const q=new URLSearchParams(search),retailerId=q.get('retailerId')||'demo';
 if(!isId(retailerId)||!Object.hasOwn(registry,retailerId))return {valid:false,reason:'unknown_retailer'};
 const r=registry[retailerId],catalogId=q.get('catalogId')||'default',locale=q.get('locale')||r.locale||'fr-FR';
 if(!Object.hasOwn(r.catalogs,catalogId)||locale!=='fr-FR')return {valid:false,reason:'unsupported_catalog_or_locale'};
 const requested=q.get('parentOrigin'),allowed=[origin,...r.allowedParentOrigins];
 return {...r,valid:true,retailerId,catalogId,locale,parentOrigin:requested&&/^https?:\/\//.test(requested)&&allowed.includes(requested)?requested:null,productId:isId(q.get('productId'))?q.get('productId'):null,mode:q.get('mode')==='modal'?'modal':'inline'};
}