export const QUALITY_CRITERIA=Object.freeze({
 S1:{label:'Perspective',defects:['D3','D6']},S2:{label:'Scale',defects:['D4','D9']},
 S3:{label:'Floor boundary',defects:['D1','D8']},S4:{label:'Occlusion',defects:['D2','D8']},
 S5:{label:'Lighting',defects:['D7']},S6:{label:'Finish/reflections',defects:[]},
 S7:{label:'Material',defects:[]},S8:{label:'Transitions',defects:['D8']}
});
export const QUALITY_STATUSES=Object.freeze(['PASS','PARTIAL','FAIL','NOT_EVALUABLE']);
export const QUALITY_SEVERITIES=Object.freeze(['MINOR','MODERATE','SEVERE','BLOCKING']);
/** Reports record observation, never infer visual PASS from renderer success. */
export function visualQualityReport(input){
 if(!input||typeof input.sceneId!=='string'||!input.sceneId)throw Error('sceneId required');
 if(typeof input.productId!=='string'||!input.productId)throw Error('productId required');
 if(!input.viewport||![input.viewport.width,input.viewport.height].every(v=>v>0))throw Error('viewport required');
 for(const key of Object.keys(QUALITY_CRITERIA)){
  const c=input.criteria?.[key];
  if(!c||!QUALITY_STATUSES.includes(c.status)||!QUALITY_SEVERITIES.includes(c.severity)||!c.observation?.trim())throw Error('Incomplete visual observation '+key);
 }
 for(const key of input.confirmedCorrect||[])if(input.criteria[key]?.status!=='PASS')throw Error('Unconfirmed correct '+key);
 for(const [key,value]of Object.entries(input.scores||{}))if(value!==null&&(!Number.isFinite(value)||value<0||value>5))throw Error('Invalid subjective score '+key);
 return {...input,schema:'pose-parquet/visual-quality@1',humanReviewPending:input.humanReviewPending!==false,
  confirmedCorrect:input.confirmedCorrect||[],priorityFailures:input.priorityFailures||[],reviewDecision:qualityReviewDecision(input)};
}
export function qualityReviewDecision(report){
 if(report.debugMetadata?.renderBlocked||report.criteria?.S1?.status==='FAIL')return 'MANUAL_REQUIRED';
 const scores=report.scores||{};
 if(['S1','S2','S4'].some(k=>report.criteria?.[k]?.status!=='PASS')||
 ['perspective','scale','occlusion'].some(k=>scores[k]!=null&&scores[k]<4)||
 report.debugMetadata?.geometryStatus==='APPROXIMATE')return 'APPROXIMATE';
 return 'HUMAN_REVIEW_REQUIRED'; // Not a calibration certificate or automatic aesthetic approval.
}
export function qualityReportText(report){
 const r=visualQualityReport(report);
 return ['VISUAL QUALITY REPORT','Scene: '+r.sceneId,'Product: '+r.productId,'Viewport: '+r.viewport.width+' × '+r.viewport.height,
 ...Object.entries(QUALITY_CRITERIA).flatMap(([key,v])=>['',key+' '+v.label+': '+r.criteria[key].status+' / '+r.criteria[key].severity,'Observation: '+r.criteria[key].observation]),
 '','CONFIRMED CORRECT: '+r.confirmedCorrect.join(', '),'PRIORITY FAILURES: '+r.priorityFailures.join(', '),
 'Review decision: '+r.reviewDecision,'Human review: '+(r.humanReviewPending?'pending':'recorded')].join('\n');
}
