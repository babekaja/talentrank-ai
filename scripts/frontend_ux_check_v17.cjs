#!/usr/bin/env node
/** Static UX and safety regression checks. This is NOT an Angular compile or browser audit. */
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const base=path.resolve(__dirname,'../apps/web/src');
const read=p=>fs.readFileSync(path.join(base,p),'utf8');
let checks=0;
function contains(file,parts){const src=read(file);for(const phrase of parts){assert(src.includes(phrase),`${file}: missing ${phrase}`);checks++;}}
const css=read('styles.css');
for(const selector of ['--tr-canvas','--tr-brand','--tr-ink','.dark {','.nav-active','.btn-primary','.field','.skeleton-line','.human-callout','.skip-link',':focus-visible','prefers-reduced-motion']){assert(css.includes(selector),`missing design token: ${selector}`);checks++;}
contains('app/features/shell/shell.ts',['Aller directement au contenu','Votre organisation','Outils de recherche','isEvaluator()','isAdmin()','aria-controls="main-menu"','jugement humain','Se déconnecter']);
contains('app/features/dashboard/dashboard.ts',['/api/v1/dashboard/overview','nextStepTitle(d)','nextStepDescription(d)','tr-empty-state','tr-loading-state','aria-label','recrutement']);
contains('app/features/candidates/candidates.ts',['/api/v1/candidates','formOpen','tr-empty-state','tr-loading-state','aria-label','Voir le dossier']);
contains('app/features/uploads/uploads.ts',['fileChange($event)','onDrop($event)','removeSelected($index)','role="progressbar"','/api/v1/uploads/batches']);
contains('app/features/matching/matching.ts',['Paramètres réservés aux administrateurs','<details','score','/api/v1/matching-runs','jamais une décision']);
contains('app/features/reviews/my-reviews.ts',['candidate_reference','Votre avis sur ce dossier','/api/v1/evaluator/assignments','Vérification nécessaire']);
contains('app/features/training/training.ts',['/api/v1/training-courses','verified_at','rel="noopener noreferrer"']);
contains('app/shared/ui/empty-state.ts',['actionRoute','role="status"','routerLink']);
contains('app/shared/ui/loading-state.ts',['aria-live="polite"','skeleton-line']);
const root=path.join(base,'app/features');
function visit(p){return fs.readdirSync(p,{withFileTypes:true}).flatMap(x=>x.isDirectory()?visit(path.join(p,x.name)):[path.join(p,x.name)]);}
const pages=visit(root).filter(x=>x.endsWith('.ts'));
let fake=0;
for(const file of pages){let src=fs.readFileSync(file,'utf8');assert(!src.includes('bypassSecurityTrustHtml'),`unsafe HTML bypass in ${file}`);checks++;
 if(/const\s+(fake|mock)(Candidates|Jobs|Applications)/i.test(src))fake++;
}
assert.equal(fake,0,'Hard-coded production recruiting fake data detected');checks++;
console.log(JSON.stringify({result:'PASS',static_ux_checks:checks,frontend_pages_scanned:pages.length,angular_compilation:'NOT_RUN',browser_accessibility_audit:'NOT_RUN'},null,2));
