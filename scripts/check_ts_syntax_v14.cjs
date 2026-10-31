/* Syntax-only offline TypeScript check. Not an Angular build or type-check. */
const fs=require('fs');
const path=require('path');
const {execFileSync}=require('child_process');
let ts;
try {ts=require('typescript');} catch (_) {
  try {ts=require(path.join(execFileSync('npm',['root','-g'],{encoding:'utf8'}).trim(),'typescript'));}
  catch (err) { console.error('TypeScript is unavailable; run npm install in apps/web.');process.exit(2); }
}
const root=path.resolve(__dirname,'../apps/web/src');
let count=0;let errors=[];
function walk(p) {
  for(const d of fs.readdirSync(p,{withFileTypes:true})) {
    const target=path.join(p,d.name);
    if(d.isDirectory()) walk(target);
    else if(/\.ts$/.test(d.name)) {
      count++;
      const sf=ts.createSourceFile(target,fs.readFileSync(target,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TS);
      for(const e of sf.parseDiagnostics) errors.push(`${target}:${e.start}: ${ts.flattenDiagnosticMessageText(e.messageText,' ')}`);
    }
  }
}
walk(root);
console.log(JSON.stringify({checked_typescript_files:count,syntax_errors:errors,angular_full_build_verified:false},null,2));
if(errors.length)process.exit(1);
