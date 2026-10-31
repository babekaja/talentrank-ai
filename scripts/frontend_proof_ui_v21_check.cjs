#!/usr/bin/env node
/** Checks source contracts, not Angular compilation or runtime UX. */
'use strict';
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const app=path.resolve(__dirname,'../apps/web/src/app');
const read=p=>fs.readFileSync(path.join(app,p),'utf8');
let checks=0;
function has(file,needle){const text=read(file);assert.ok(text.includes(needle),`${file}: missing ${needle}`);checks++;}
const doc='features/insights/document-viewer.ts';
for(const needle of ['/documents/${encodeURIComponent(this.id)}/viewer','page_number:this.currentPage()',
  '/documents/${encodeURIComponent(this.id)}/download','responseType:\'blob\'','URL.revokeObjectURL',
  'bypassSecurityTrustResourceUrl','v.total_pages','validMention','m.end<=p.text.length',
  'p.text.slice(m.start,m.end)===m.text','part.focus','aria-label="Document original"',
  'aria-label="Preuves reconnues dans le texte"','page','start','end','this.focusRange.set(null)'])has(doc,needle);
const comp='features/matching/matching-compare.ts';
for(const needle of ['/matching-runs/${encodeURIComponent(runId)}/compare','result_ids:ids',
  'ids.length<2||ids.length>5','new Set(ids)','filteredRows()',
  'findCriterion(r,row.code)','tr-native-chart','showEvidence(r.id,c.code)',
  '/matching-results/${encodeURIComponent(id)}/explanation','e.source_still_matches',
  'e.start_offset','e.end_offset','role="group"','scope(r)','r.score===null'])has(comp,needle);
const detail='features/matching/matching-detail.ts';
for(const needle of ['/matching-results/${encodeURIComponent(id)}/explanation',
  'd.stale','r.score===null', // next special case below
  'c.evidence','e.source_still_matches','e.start_offset','e.end_offset',
  'tr-native-chart','Demander un examen humain','criterionReason','criterionKind',
  '/request-review','note_code','evaluable_subset_coverage']){
  if(needle==='r.score===null')continue;
  has(detail,needle);
}
has(detail,'d.score===null');
const routes=read('app.routes.ts');assert.ok(routes.includes('matching/analyses/:id/comparer'));checks++;
const matching=read('features/matching/matching.ts');assert.ok(matching.includes('Comparer en détail')&&matching.includes('compareIds().join'));checks+=2;
const css=fs.readFileSync(path.resolve(__dirname,'../apps/web/src/styles.css'),'utf8');
assert.ok(css.includes('.criterion-chip-good')&&css.includes('.criterion-chip-review'));checks+=2;
for(const screen of [doc,comp,detail]){
 const text=read(screen);
 for(const bad of ['[innerHTML]','bypassSecurityTrustHtml','Math.random()','mockCandidates','fakeCandidates']){
  assert.ok(!text.includes(bad),`${screen}: unsafe or fabricated ${bad}`);checks++;
 }
 assert.ok(text.includes('TrIcon'),`${screen}: missing Lucide`);checks++;
}
const nginx=fs.readFileSync(path.resolve(__dirname,'../apps/web/nginx.conf'),'utf8');
assert.ok(nginx.includes('frame-src \'self\' blob:'));checks++;
console.log(JSON.stringify({result:'PASS',checks,frontend_angular_build:'NOT_RUN',browser_tests:'NOT_RUN'},null,2));
