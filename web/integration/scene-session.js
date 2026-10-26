/** Per-tab restoration of public demo choices only. Never serialize a private photo. */
const KEY='pp.scene-session.v1';
export class SceneSession{
 constructor(storage,scope='demo/default'){this.storage=storage;this.key=KEY+'/'+scope;}
 save(s){
  const data={version:1,source:s.source==='demo'?'demo':s.source==='uploaded'?'uploaded':null,roomId:s.source==='demo'?s.roomId:null,productId:s.productId,orientation:Number(s.orientationDeg)||0,scale:Number(s.floorScale)||1,at:Date.now()};
  try{this.storage?.setItem(this.key,JSON.stringify(data));}catch{}return data;
 }
 read(){try{const s=JSON.parse(this.storage?.getItem(this.key)||'null');return s?.version===1&&['demo','uploaded',null].includes(s.source)&&typeof s.productId==='string'&&s.productId.length<129&&Number.isFinite(s.orientation)&&s.orientation>=0&&s.orientation<360&&Number.isFinite(s.scale)&&s.scale>=.25&&s.scale<=4?s:null;}catch{return null;}}
 clear(){try{this.storage?.removeItem(this.key);}catch{}}
}