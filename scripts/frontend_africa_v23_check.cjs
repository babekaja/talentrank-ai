const fs=require('fs');const path=require('path');const root=path.resolve(__dirname,'../apps/web/src/app');
const routes=fs.readFileSync(path.join(root,'app.routes.ts'),'utf8');
const pages=['talentgraph','prooflab','skillsproof','opportunity-bridge'];
let checks=0;const problems=[];
for (const name of pages){const file=path.join(root,'features/africa',name+'.ts');const body=fs.readFileSync(file,'utf8');
  for(const term of ['standalone:true','@Component','/api/v1/africa/', 'tr-icon']){
    checks++;if(!body.includes(term))problems.push(name+': missing '+term);
  }
}
for(const route of ['talentgraph-africa','prooflab-africa','documents/:id/preuves','matching/resultat/:id/opportunites']){
  checks++;if(!routes.includes(route))problems.push('Missing route: '+route);
}
const nav=fs.readFileSync(path.join(root,'features/shell/shell.ts'),'utf8');
for(const link of ['/talentgraph-africa','/prooflab-africa']){checks++;if(!nav.includes(link))problems.push('Missing nav '+link);}
if(problems.length){console.error(problems.join('\n'));process.exitCode=1;}else console.log(JSON.stringify({static_checks_passed:checks,angular_build_verified:false}));
