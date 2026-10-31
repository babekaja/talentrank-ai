#!/usr/bin/env node
/** Non-compiling structural checks, deliberately reported separately from ng build. */
'use strict';
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const root=path.join(__dirname,'..','apps','web','src','app');
const read=(p)=>fs.readFileSync(path.join(root,p),'utf8');
const routes=read('app.routes.ts');
const shell=read('features/shell/shell.ts');
const review=read('features/reviews/my-reviews.ts');
const assignment=read('features/reviews/assignments.ts');
const training=read('features/training/training.ts');
const apps=read('features/applications/applications.ts');
for(const [route,roles] of [
 ['tableau-de-bord','recruitmentRoles'],['affectations','recruitmentRoles'],
 ['mes-examens','evaluatorRoles'],['formations','recruitmentRoles']]){
 const re=new RegExp(`path:'${route}'.*canActivate:\\[roleGuard\\],data:\\{roles:${roles}\\}`);
 assert(re.test(routes),`Guard with ${roles} missing: ${route}`);
}
for(const [page,ui,api] of [
 ['review',review,'/api/v1/evaluator/assignments'],
 ['assignments',assignment,'/api/v1/evaluator/assignments'],
 ['training',training,'/api/v1/training-courses'],
 ['applications',apps,'/api/v1/applications']]){
 assert(ui.includes(api),`${page}: real API missing`);
 assert(ui.includes('apiError('),`${page}: errors not rendered`);
 assert(ui.includes('loading()')||ui.includes('busy()'),`${page}: loading/busy feedback missing`);
 assert(!ui.includes('bypassSecurityTrustHtml')&&!ui.includes('[innerHTML]'),`${page}: unsafe HTML`);
}
assert(review.includes('candidate_reference')&&!review.includes('candidate_name'),
 'Evaluator screen must remain masked');
assert(review.includes('notes')===false,'Forbidden fake attribute');
assert(training.includes('rel="noopener noreferrer"'),'Training external links must be isolated');
assert(training.includes('verified_at'),'Training verification status missing');
assert(assignment.includes('availableOffset()'),'Assignable list must be paged');
assert(apps.includes('offset()')&&apps.includes('total()'),'Applications page must be paged');
assert(shell.includes('isEvaluator()')&&shell.includes('routerLink="/mes-examens"'));
console.log(JSON.stringify({status:'pass',checks:19,compilation:false,note:'Source structure only; Angular template typecheck and browser E2E not performed'},null,2));
