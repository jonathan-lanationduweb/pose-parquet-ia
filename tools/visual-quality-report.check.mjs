import assert from'node:assert/strict';import{visualQualityReport,qualityReportText,QUALITY_CRITERIA}from'../web/product/visual-quality-report.js';
const input={sceneId:'fixture',productId:'product',viewport:{width:390,height:844},criteria:Object.fromEntries(Object.keys(QUALITY_CRITERIA).map(k=>[k,{status:k==='S6'?'NOT_EVALUABLE':'PASS',severity:'MINOR',observation:'Explicit inspected evidence or missing finish data'}])),confirmedCorrect:['S1','S2','S4'],scores:{perspective:4,scale:4,occlusion:4}};
assert.equal(visualQualityReport(input).reviewDecision,'HUMAN_REVIEW_REQUIRED');assert.match(qualityReportText(input),/S6 Finish\/reflections: NOT_EVALUABLE/);
const missing=structuredClone(input);delete missing.criteria.S8;assert.throws(()=>visualQualityReport(missing));
const falsePass=structuredClone(input);falsePass.criteria.S4.status='FAIL';assert.throws(()=>visualQualityReport(falsePass));
falsePass.confirmedCorrect=['S1','S2'];assert.equal(visualQualityReport(falsePass).reviewDecision,'APPROXIMATE');
const score=structuredClone(input);score.scores.occlusion=3;assert.equal(visualQualityReport(score).reviewDecision,'APPROXIMATE');
score.debugMetadata={renderBlocked:true};assert.equal(visualQualityReport(score).reviewDecision,'MANUAL_REQUIRED');
console.log('PASS complete S1-S8, explicit observations, missing S6 data, no false confirmed PASS, manual/approximate review gate');
