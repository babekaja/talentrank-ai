// Static only: this does not execute Angular or inspect browser behavior.
const fs = require('fs');
const path = require('path');
const root = path.join(__dirname,'..','apps','web','src','app');
function requireSource(file,markers){
  const src=fs.readFileSync(path.join(root,file),'utf8');
  for(const marker of markers){if(!src.includes(marker))throw Error(`${file}: missing ${marker}`);}
}
requireSource('app.routes.ts',['espace-candidat','CandidatePortal']);
requireSource('core/auth/auth.interceptor.ts',["request.url.startsWith('/api/v1/candidate-portal/')"]);
requireSource('features/portal/candidate-portal.ts',['verify()','setConsent','logout()','notice_version','training-suggestions']);
requireSource('features/candidates/candidate-detail.ts',['sendCandidateCode','send-access-code']);
console.log(JSON.stringify({status:'PASS',checks:10,type:'static-v24-only',angular_build:false}));
