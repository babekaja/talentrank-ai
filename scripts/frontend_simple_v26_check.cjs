#!/usr/bin/env node
'use strict';
/* Checks user-facing source invariants. Not an Angular compilation or a WCAG browser audit. */
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const base=path.resolve(__dirname,'../apps/web/src/app');
const read=p=>fs.readFileSync(path.join(base,p),'utf8');
const shell=read('features/shell/shell.ts');
const guide=read('features/onboarding/getting-started.ts');
const dash=read('features/dashboard/dashboard.ts');
const match=read('features/matching/matching.ts');
const uploads=read('features/uploads/uploads.ts');
const routes=read('app.routes.ts');
const auth=read('shared/models/auth.ts');
const reports=read('features/insights/reports.ts');
const error=read('shared/recruitment.ts');
let checks=0;function check(yes,msg){assert.ok(yes,msg);checks++;}
const main=shell.slice(shell.indexOf('Recruter au quotidien'),shell.indexOf('managementTools.update'));
check((main.match(/routerLink=/g)||[]).length<=9,'Too many first-level recruiting links');
for(const text of ['Mon accueil','Comment commencer ?','Mes offres d\'emploi','Déposer des CV','Candidatures reçues','Résultats des CV','Mes rapports'])check(main.includes(text),'Missing plain-language navigation: '+text);
for(const text of ['managementTools()','advancedTools()','aria-controls="expert-links"','aria-controls="management-links"','isEvaluator()','isAdmin()'])check(shell.includes(text),'Missing role/expand navigation: '+text);
check(shell.includes("this.managementTools.set(true)"),'Deep linked management page must show its category');
check(shell.includes('Les résultats expliquent ce qui est documenté'),'Human decision notice removed');
check(routes.includes("path:'demarrer',canActivate:[roleGuard]"),'Guide route not protected by server-equivalent role UI guard');
check(guide.includes('/api/v1/dashboard/overview'),'Guide uses fake numbers instead of API');
check(!guide.includes('setTimeout')&&!guide.includes('Math.random'),'Guide creates simulated progress');
check((guide.match(/number:[1-5]/g)||[]).length===5,'The five user-facing steps were not created');
check(guide.includes('vocabulary')&&guide.includes('À vérifier'),'Plain French glossary missing');
check(dash.includes('cards.slice(0,4)')&&dash.includes('cards.slice(4)'),'Dashboard overload not reduced');
check(dash.includes('routerLink="/demarrer"'),'Dashboard guide unavailable');
check(match.includes('Quels CV correspondent au poste ?')&&match.includes('Paramètres réservés aux administrateurs'),'Matching still developer-oriented');
check(match.includes("r.score===null?'À examiner'"),'Non-calculable matching score falsely shown as 0');
check(uploads.includes('Envoyer les CV')&&uploads.includes('Voir les CV reçus'),'CV upload copy not simplified');
check(uploads.includes('/api/v1/uploads/batches'),'Upload API replaced with fake data');
check(reports.includes('/api/v1/reports/history'),'Real reports API removed');
check(auth.includes('organization_slug')&&auth.includes('role:'),'Real auth contract absent');
check(error.includes('err.status === 413')&&error.includes('err.status >= 500'),'Actionable errors missing');
console.log(JSON.stringify({status:'PASS',checks,visual_build:'NOT_RUN',e2e:'NOT_RUN',role_auth:'BACKEND_ENFORCED'},null,2));
