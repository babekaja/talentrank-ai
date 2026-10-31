#!/usr/bin/env node
'use strict';
/** Source-level checks only. This is not a substitute for ng build or browser E2E tests. */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../apps/web/src');
let ts;
try{ts=require('typescript');}
catch{
  ts=require(path.resolve(__dirname,'../apps/web/node_modules/typescript'));
}
let count=0,components=0,checks=0;
function filesIn(folder){return fs.readdirSync(folder,{withFileTypes:true}).flatMap(x=>x.isDirectory()?filesIn(path.join(folder,x.name)):[path.join(folder,x.name)]);}
const files=filesIn(path.join(root,'app')).filter(f=>f.endsWith('.ts'));
for(const f of files){
  const src=fs.readFileSync(f,'utf8');
  const ast=ts.createSourceFile(f,src,ts.ScriptTarget.Latest,true,ts.ScriptKind.TS);
  assert.equal(ast.parseDiagnostics.length,0,`${f}: ${ast.parseDiagnostics.map(x=>x.messageText).join('; ')}`);
  count++;
  if(src.includes('@Component(')) {assert(src.includes('standalone:true')||src.includes('standalone: true'),`${f} must be standalone`);components++;}
  assert(!src.includes('[innerHTML]')&&!src.includes('bypassSecurityTrustHtml'),`${f}: unsafe HTML escape bypass`);
  assert(!/localStorage\.setItem\([^\n]*(?:token|password|candidate|document)/i.test(src),`${f}: forbidden sensitive browser storage`);
  const rx=/from\s*['"](\.{1,2}\/[^'"\n]+)['"]/g;
  for(const m of src.matchAll(rx)){
    const candidate=path.resolve(path.dirname(f),m[1]);
    assert(fs.existsSync(candidate+'.ts')||fs.existsSync(candidate+'.js')||fs.existsSync(path.join(candidate,'index.ts')),`Missing local import ${m[1]} from ${f}`);
    checks++;
  }
}
const routes=fs.readFileSync(path.join(root,'app/app.routes.ts'),'utf8');
for(const route of ['candidats/:id','campagnes/:id','matching/resultat/:id','documents/:id/visionneuse','confidentialite','parametres','acces-refuse'])assert(routes.includes(`path:'${route}'`),`route absent: ${route}`);
for(const pathRole of ['offres','campagnes','candidats','candidatures','importations','matching','rapports','confidentialite','equipe','audit'])assert(new RegExp(`path:'${pathRole}'.*canActivate:\\[roleGuard\\]`).test(routes),`missing role guard on ${pathRole}`);
const auth=fs.readFileSync(path.join(root,'app/core/auth/auth.service.ts'),'utf8');
assert(auth.includes('refreshing:Promise<string|null>|null=null'));
const matching=fs.readFileSync(path.join(root,'app/features/matching/matching.ts'),'utf8');
assert(matching.includes('Aucun rejet')||matching.includes('Aucun candidat'));
assert(fs.existsSync(path.join(root,'styles.css')));
console.log(JSON.stringify({status:'pass',typescript_files:count,standalone_components:components,local_imports_checked:checks,role_guard_routes:10,build_executed:false},null,2));
