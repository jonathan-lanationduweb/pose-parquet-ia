/** No network or provider. Integrators explicitly subscribe to sanitized events. */
export const FUNNEL=Object.freeze({
 READY:'visualizer_open',PHOTO_IMPORTED:'photo_import',ROOM_SELECTED:'demo_room_selected',
 PRODUCT_SELECTED:'product_selected',FAVORITE_ADDED:'favorite',COMPARE_OPENED:'compare',
 SHARE_REQUESTED:'share',DOWNLOAD_COMPLETED:'download',PRODUCT_PAGE_REQUESTED:'product_page_click',
});
export class AnalyticsAdapter{
 constructor(sink=null){this.sink=sink;}
 track(name,payload={}){try{this.sink?.({name,payload,at:Date.now()});}catch{/* Host analytics must never block the visualizer. */}}
 event(type,payload){const name=FUNNEL[type];if(name)this.track(name,payload);if(type==='ANALYSIS_COMPLETED')this.track(payload.status==='manual'?'analysis_manual_required':payload.status==='unavailable'?'analysis_unavailable':'analysis_success',payload);}
}