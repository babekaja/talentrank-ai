#!/usr/bin/env node
/* Source-level, not an Angular compiler, test. Must not be reported as a built application. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname,'../apps/web');
const read = name => fs.readFileSync(path.join(root,name),'utf8');
let checks = 0;
function test(ok,msg){assert.ok(ok,msg);checks++;}
const pkg = JSON.parse(read('package.json'));
test(pkg.dependencies['@lucide/angular']!==undefined,'Lucide Angular missing');
test(pkg.dependencies['echarts']!==undefined && pkg.dependencies['ngx-echarts'].startsWith('^22.'),'Angular 22 native chart packages missing');
const config=read('src/app/app.config.ts');
test(config.includes('provideLucideIcons('),'global icon provider missing');
const icon=read('src/app/shared/ui/tr-icon.ts');
test(icon.includes("from '@lucide/angular'")&&icon.includes('aria-hidden')&&icon.includes('aria-label'),'accessible Lucide component missing');
const chart=read('src/app/shared/ui/native-chart.ts');
for(const s of ['NgxEchartsDirective','provideEchartsCore','SVGRenderer','BarChart','LineChart','PieChart','role="img"','aria: {enabled: true}','Number.isFinite','slice(0, 30)']) test(chart.includes(s),'missing native chart feature: '+s);
const features=path.join(root,'src/app/features');
function visit(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?visit(path.join(dir,e.name)):[path.join(dir,e.name)]);}
const screens=visit(features).filter(f=>f.endsWith('.ts')&&!f.endsWith('.spec.ts')&&!f.endsWith('home-redirect.ts'));
for(const f of screens){
  const src=fs.readFileSync(f,'utf8');
  // The minimal 404 recovery page has a text heading and a home link instead of an icon.
  if(f===path.join(features,'system/not-found.ts')){
    test(src.includes('<h1')&&src.includes('routerLink="/"'),`Missing page recovery navigation: ${f}`);
  }else{
    test(src.includes('Lucide')||src.includes('TrIcon'),`No Lucide icons: ${f}`);
  }
  test(!src.includes('mockCandidates')&&!src.includes('fakeCandidates'),`Simulated recruiting data: ${f}`);
}
const dashboard=read('src/app/features/dashboard/dashboard.ts');
for(const v of ['dashboard/overview','<tr-native-chart kind="trend"','<tr-native-chart kind="donut"','<tr-native-chart kind="bars"','documentChart()','skillChart()','trendChart()']) test(dashboard.includes(v),'missing API-connected dashboard graph: '+v);
const reports=read('src/app/features/insights/reports.ts');
test(reports.includes('formatChart()')&&reports.includes('/api/v1/reports/history'),'Report graph not API connected');
const matching=read('src/app/features/matching/matching.ts');
test(matching.includes('compareChartItems()') && matching.includes('value:r.documented'),'Candidate comparison does not use documented mentions');
test(matching.includes('matchingDisplay(r)') && matching.includes('result.matching_percentage!==null&&result.matching_percentage!==undefined') && matching.includes(":'Non calculable'"),'Unknown matching percentage incorrectly rendered as zero');
const shell=read('src/app/features/shell/shell.ts');
test(shell.includes('advancedTools()')&&shell.includes('Outils de recherche')&&shell.includes('aria-controls="expert-links"'),'Advanced tools not collapsible');
test(shell.includes('jugement humain'),'Human decisions disclaimer missing');
console.log(JSON.stringify({status:'PASS', checks, icon_screen_count:screens.length, native_charts:6, checks_are_static:true, angular_build_verified:false},null,2));
