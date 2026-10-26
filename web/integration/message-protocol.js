/** Public messages deliberately carry IDs and states, never photos or SceneData. */
export const VERSION=1;
export const SOURCES={command:'pose-parquet-retailer',event:'pose-parquet-visualizer'};
export const isId=x=>typeof x==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$/.test(x);
const record=x=>x&&typeof x==='object'&&!Array.isArray(x);
const schemas={
 SET_PRODUCT:{productId:isId},SET_CATALOG:{catalogId:isId},
 SET_FAVORITES:{favoriteIds:x=>Array.isArray(x)&&x.length<=1000&&x.every(isId)},
 OPEN_ROOM_SELECTOR:{},RESET_SESSION:{},
 READY:{retailerId:isId,catalogId:isId,locale:x=>x==='fr-FR'},
 ROOM_SELECTED:{roomId:isId},PHOTO_IMPORTED:{source:x=>x==='uploaded'},
 ANALYSIS_COMPLETED:{status:x=>['ready','approximate','manual','unavailable'].includes(x)},
 PRODUCT_SELECTED:{productId:isId},FAVORITE_ADDED:{productId:isId},FAVORITE_REMOVED:{productId:isId},
 COMPARE_OPENED:{productId:isId},SHARE_REQUESTED:{kind:x=>['demo','private'].includes(x)},
 DOWNLOAD_COMPLETED:{productId:isId},PRODUCT_PAGE_REQUESTED:{productId:isId},
 COMMAND_RESULT:{command:x=>COMMANDS.includes(x),ok:x=>typeof x==='boolean',code:x=>typeof x==='string'&&x.length<80},
};
export const COMMANDS=['SET_PRODUCT','SET_CATALOG','SET_FAVORITES','OPEN_ROOM_SELECTOR','RESET_SESSION'];
export const EVENTS=Object.keys(schemas).filter(x=>!COMMANDS.includes(x));
export function validMessage(m,direction){
 if(!record(m)||Object.keys(m).some(k=>!['source','version','type','payload'].includes(k)))return false;
 const types=direction==='command'?COMMANDS:EVENTS;
 if(m.source!==SOURCES[direction]||m.version!==VERSION||!types.includes(m.type)||!record(m.payload))return false;
 const schema=schemas[m.type];return Object.keys(m.payload).length===Object.keys(schema).length&&Object.entries(schema).every(([k,check])=>Object.hasOwn(m.payload,k)&&check(m.payload[k]));
}
export function message(type,payload={},direction='event'){
 const m={source:SOURCES[direction],version:VERSION,type,payload};
 if(!validMessage(m,direction))throw Error('Invalid public message: '+type);return m;
}
export function trustedMessage(event,{origin,source,direction='command'}){
 return Boolean(origin&&source&&event.origin===origin&&event.source===source&&validMessage(event.data,direction));
}