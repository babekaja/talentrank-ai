#!/usr/bin/env node
/** Static screen regression: verifies API bindings, accessibility affordances, and risky patterns.
 *  Not an Angular build and not a browser accessibility certification. */
'use strict';
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const base=path.resolve(__dirname,'../apps/web/src/app/features');
const screens={
 'insights/reports.ts':['/api/v1/reports/history','/api/v1/reports/campaigns/','filteredHistory()','[disabled]','role="alert"','aria-live'],
 'audit/audit.ts':['/api/v1/audit-logs','limit:100','filtered()','actionTypes()','role="status"'],
 'skills/skills.ts':['/api/v1/skills','limit:100','filtered()','submitSearch($event)','role="alert"'],
 'skills/aliases.ts':['/api/v1/skills/','canEdit()','language()','justification','Référentiel'],
 'team/team.ts':['/api/v1/members','/api/v1/invitations','confirmUpdate()','pending()','role="status"'],
 'insights/document-quality.ts':['/api/v1/documents/','severityLabel','filtered()','role="alert"'],
 'insights/skill-gaps.ts':['/api/v1/matching-results/','d.score===null','manual_review_required','group.items'],
 'settings/settings.ts':['PreferencesService','auth.user()','aria-pressed','/confidentialite','/mes-examens']
};
let checks=0;
for(const [file,needs] of Object.entries(screens)){
 const src=fs.readFileSync(path.join(base,file),'utf8');
 for(const marker of needs){assert(src.includes(marker),`${file}: missing ${marker}`);checks++;}
 for(const forbidden of ['[innerHTML]','bypassSecurityTrustHtml','Math.random()','fakeCandidates']){assert(!src.includes(forbidden),`${file}: risky pattern ${forbidden}`);checks++;}
 assert(src.includes('apiError(')||file==='settings/settings.ts',`${file}: missing API error handler`);checks++;
}
const css=fs.readFileSync(path.resolve(__dirname,'../apps/web/src/styles.css'),'utf8');
for(const className of ['.step-number','.option-tile','.option-tile-selected','.soft-badge']){assert(css.includes(className));checks++;}
console.log(JSON.stringify({status:'PASS',checks,screens:Object.keys(screens).length,angular_build:'NOT_RUN',browser_tests:'NOT_RUN'},null,2));
