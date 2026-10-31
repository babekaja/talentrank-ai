import { VisualGuide } from '../../shared/ui/visual-guide';
import { HumanStatus } from '../../shared/ui/human-status';
import { NativeChart } from '../../shared/ui/native-chart';
import type { ChartDatum } from '../../shared/ui/native-chart';
import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, computed, OnInit, OnDestroy, DestroyRef, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { Campaign, apiError, Page } from '../../shared/recruitment';
import { AuthService } from '../../core/auth/auth.service';

interface Weights {essential:number;desirable:number;experience:number;projects_training:number}
interface Configuration {version:number;weights:Weights;algorithm_version:string}
interface MatchingRun {id:string;campaign_id:string;job_id:string;status:string;total:number;processed:number;criteria_version:number;config_version:number;algorithm_version:string;created_at:string;completed_at:string|null;weights?:Weights;mapping?:{skill_criteria:number;mapped:number;unmapped:number;mapped_required:number}}
interface Criterion {code:string;label:string;state:string;contribution:number}
interface RankingSummary {assessed_weight_percent:number;criteria_count:number;ranked_count:number;unranked_count:number;provisional:boolean;note:string}
interface Result {rank?:number|null;matching_percentage?:number|null;ranking_scope_percent?:number;candidate_name?:string;candidate_reference?:string;criteria?:Criterion[];id:string;application_id:string;candidate_reference_id:string;score:number|null;state:string;documented:number;to_review:number;not_documented:number;group_coverage:Record<string,unknown>}

@Component({selector:'tr-matching',standalone:true,imports:[VisualGuide, HumanStatus,TrIcon,NativeChart,FormsModule,RouterLink],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="compare" [size]="15"/> Comparer sans décider à votre place</p><h1 class="mt-2">Quels CV correspondent au poste ?</h1><p>Classez les CV selon leur correspondance pondérée aux critères du poste. Consultez le pourcentage obtenu et les preuves avant de donner votre avis.</p></div></header>
<tr-visual-guide title="Portée du résultat" description="Les mentions trouvées ne remplacent ni un entretien ni un examen complet du dossier." /><div class="human-callout mb-6 p-4 text-sm leading-relaxed"><strong>À retenir :</strong> Le chiffre indique seulement les critères que le CV permet de vérifier. Il ne mesure pas la valeur d’une personne. Quand un élément est incertain, demandez un avis humain.</div>
@if(error()){<p class="alert-error mb-4" role="alert">{{error()}}</p>}
@if(info()){<p class="alert-ok mb-4" role="status">{{info()}}</p>}
<section class="grid gap-5 lg:grid-cols-[1fr_1fr] mb-6">
 <div class="card p-5"><div class="flex items-center gap-3 mb-4"><div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] bg-[#e2eff5] dark:bg-[#1c3d4e]"><tr-icon name="search" [size]="18" class="text-[#1c5a72] dark:text-blue-200"/></div><div><p class="eyebrow text-[10px] mb-0.5">Étape 1</p><h2 class="section-heading">Choisir le recrutement</h2></div></div><p class="section-caption mb-4 text-sm">Sélectionnez le poste concerné. TalentRank utilisera uniquement les critères validés par votre équipe.</p>
  <label class="field-label" for="match-campaign">Campagne de recrutement</label>
  <select class="field" id="match-campaign" [disabled]="busy()" [(ngModel)]="campaignId" (ngModelChange)="selectionChanged()"><option value="">Choisir une campagne</option>@for(c of campaigns();track c.id){<option [value]="c.id">{{c.name}} ({{c.status | humanStatus:'campaign'}})</option>}</select>
  <p class="mt-3 text-xs text-slate-500">Si un CV n’a pas encore été lu ou contient des informations ambiguës, le dossier sera marqué « À vérifier ».</p>
  <button class="btn-primary mt-4" [disabled]="busy() || !campaignId || hasActiveRun()" (click)="launch()">{{busy()?'Envoi en cours…':hasActiveRun()?'Analyse en cours…':'Comparer les CV'}}</button>
 </div>
 <div class="card p-5"><div class="flex items-center gap-3 mb-4"><div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] bg-[#f0ecfa] dark:bg-[#2a2045]"><tr-icon name="settings" [size]="18" class="text-[#6c4faa] dark:text-purple-200"/></div><div><p class="eyebrow text-[10px] mb-0.5">Pondération du classement</p><h2 class="section-heading">Poids des critères</h2></div></div><details class="group"><summary class="cursor-pointer list-none text-sm font-semibold text-slate-600 dark:text-slate-300 marker:content-none">Modifier les poids des prochaines analyses <span aria-hidden="true" class="font-normal text-slate-400 ml-1">⌄</span></summary><p class="section-caption mt-2 mb-4">Les poids déterminent la part de chaque catégorie dans le pourcentage. Une modification s’applique à la prochaine analyse ; les classements déjà calculés conservent leurs poids.</p>
  @if(config();as c){<p class="mb-3 text-xs text-slate-500">Configuration v{{c.version}} · {{c.algorithm_version}}</p>
  <div class="grid grid-cols-2 gap-3 text-sm">
   <label>Essentielles (%)<input type="number" class="field" min="0" max="100" [(ngModel)]="weights.essential" [disabled]="auth.user()?.role!=='org_admin'"/></label>
   <label>Souhaitables (%)<input type="number" class="field" min="0" max="100" [(ngModel)]="weights.desirable" [disabled]="auth.user()?.role!=='org_admin'"/></label>
   <label>Expérience (%)<input type="number" class="field" min="0" max="100" [(ngModel)]="weights.experience" [disabled]="auth.user()?.role!=='org_admin'"/></label>
   <label>Projets / formations (%)<input type="number" class="field" min="0" max="100" [(ngModel)]="weights.projects_training" [disabled]="auth.user()?.role!=='org_admin'"/></label>
  </div>
  <p class="text-xs text-slate-500 mt-2">Somme : {{weightSum()}}%. Les catégories sans critères sont redistribuées ; les critères non évaluables restent à vérifier.</p>
  @if(auth.user()?.role==='org_admin'){<button class="btn-light mt-3" [disabled]="busy() || weightSum()!==100 || weights.essential===0" (click)="saveWeights()">Enregistrer une nouvelle version</button>}
  }
 </details></div>
</section>
@if(selectedRun()?.weights;as weights){<section class="soft-panel mb-6 p-4" aria-label="Poids utilisés pour ce classement"><h2 class="font-semibold text-sm">Poids utilisés pour cette analyse</h2><div class="mt-3 flex flex-wrap gap-2 text-sm"><span class="soft-badge">Essentielles : {{weights.essential}} %</span><span class="soft-badge">Souhaitables : {{weights.desirable}} %</span><span class="soft-badge">Expérience : {{weights.experience}} %</span><span class="soft-badge">Projets et formations : {{weights.projects_training}} %</span></div><p class="mt-2 text-xs muted">Les catégories sans critère sont redistribuées. Le classement porte sur les critères évalués en commun.</p></section>}
<section class="card overflow-hidden mb-6"><h2 class="px-5 py-4 font-bold border-b border-slate-100 dark:border-slate-800">2. Retrouver une comparaison</h2>
@if(loading()){<p class="p-5 text-slate-500" role="status">Chargement…</p>}
@else if(!runs().length){<p class="p-5 text-slate-500">Aucune comparaison pour ce recrutement. Choisissez une campagne ci-dessus puis cliquez sur « Comparer les CV ».</p>}
@else{<div class="overflow-x-auto"><table class="w-full min-w-[720px] text-left text-sm"><thead class="table-head bg-[#f0f6f8] dark:bg-[#1c3040]"><tr><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">Analyse</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">Avancement</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">Référentiel</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">Version</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">État</th><th class="px-4 py-3.5"></th></tr></thead><tbody>@for(r of runs();track r.id){<tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-[#eef7f8] dark:hover:bg-[#1c3040] transition-colors duration-150"><td class="p-4"><span class="font-mono text-xs bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-md">{{r.id.slice(0,8)}}</span></td><td class="p-4 tabular-nums text-sm">{{r.processed}} / {{r.total}} CV</td><td class="p-4 text-sm">{{r.mapping?.mapped ?? 0}} / {{r.mapping?.skill_criteria ?? 0}} liées@if(r.mapping;as mapping){@if(mapping.unmapped){<span class="badge badge-amber mt-1">{{mapping.unmapped}} à vérifier</span>}}</td><td class="p-4 text-xs text-slate-500 tabular-nums">v{{r.criteria_version}} · cfg {{r.config_version}}</td><td class="p-4"><span class="status-pill" [class.status-pill--good]="r.status==='completed'" [class.status-pill--warning]="isActive(r)">{{r.status | humanStatus:'run'}}</span></td><td class="p-4"><button class="btn-light" (click)="selectRun(r.id)">Voir</button></td></tr>}</tbody></table></div>}
</section>
@if(selectedRunId()){
<section class="card overflow-hidden"><div class="flex flex-wrap justify-between gap-3 px-5 py-5 border-b border-slate-100 dark:border-slate-800"><div><h2 class="section-heading">3. Classement des CV pour le poste</h2><p class="text-sm text-slate-500">{{total()}} résultats · indicateur documentaire, jamais une décision</p></div><div class="flex flex-wrap gap-2"><a class="btn-light" routerLink="/rapports" [queryParams]="{campaign:campaignId,run:selectedRunId()}" [class.pointer-events-none]="selectedRun()?.status!=='completed'" [attr.aria-disabled]="selectedRun()?.status!=='completed'" [attr.tabindex]="selectedRun()?.status!=='completed'?-1:null">Exporter ce classement</a><button class="btn-light" [disabled]="compareIds().length<2 || compareIds().length>5" (click)="compare()">Aperçu rapide ({{compareIds().length}}/5)</button>@if(compareIds().length>=2 && compareIds().length<=5){<a class="btn-primary" [routerLink]="['/matching/analyses',selectedRunId(),'comparer']" [queryParams]="{ids:compareIds().join(',')}"><tr-icon name="columns-3" [size]="17"/> Comparer en détail</a>}<button class="btn-light" [disabled]="refreshing()" (click)="refresh()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Actualiser</button></div></div>
@if(ranking();as ranking){<div class="px-5 py-4 text-sm border-b border-slate-100 dark:border-slate-800"><p class="font-semibold">{{ranking.provisional?'Classement provisoire':'Du pourcentage le plus élevé au plus faible'}}</p><p class="muted mt-1">{{ranking.ranked_count}} CV classés sur {{ranking.criteria_count}} critères communs représentant {{ranking.assessed_weight_percent}} % du poids du poste. Les scores égaux partagent le même rang.</p>@if(ranking.unranked_count){<p class="muted mt-1">{{ranking.unranked_count}} dossier(s) non classé(s) : analyse ou critères communs insuffisants.</p>}</div>}
@if(resultsLoading()){<p class="p-5" role="status">Chargement du classement…</p>}
@else if(!results().length){<p class="p-5 text-slate-500">Résultats non disponibles. L'analyse peut être encore en cours.</p>}
@else{<div class="overflow-x-auto"><table class="w-full min-w-[760px] text-left text-sm"><thead class="table-head bg-[#f0f6f8] dark:bg-[#1c3040]"><tr><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">Rang</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">Candidat</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">Correspondance pondérée</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">Éléments trouvés</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">À vérifier</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">État</th><th class="px-4 py-3.5 font-bold tracking-wide text-[#3d5a6c] dark:text-slate-200">Preuves</th></tr></thead><tbody>@for(r of results();track r.id){<tr class="border-b border-slate-100 dark:border-slate-800 hover:bg-[#eef7f8] dark:hover:bg-[#1c3040] transition-colors duration-150"><td class="p-4"><span class="block font-bold tabular-nums mb-2">{{r.rank!==null && r.rank!==undefined?'#'+r.rank:'Non classé'}}</span><input type="checkbox" [checked]="compareIds().includes(r.id)" [disabled]="!compareIds().includes(r.id) && compareIds().length>=5" (change)="toggleCompare(r.id,$any($event.target).checked)" [attr.aria-label]="'Comparer '+r.candidate_reference_id"/></td><td class="p-4 font-mono text-xs"><span class="bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-md">{{r.candidate_reference || r.candidate_reference_id.slice(0,8)}}</span>@if(r.candidate_name){<span class="block mt-2 font-sans text-sm font-medium">{{r.candidate_name}}</span>}</td><td class="p-4 font-bold tabular-nums">{{matchingDisplay(r)}}@if(r.matching_percentage!==null && r.matching_percentage!==undefined){<div class="mt-2 h-1.5 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden" aria-hidden="true"><div class="h-full bg-[#205f77] dark:bg-[#78b4c8]" [style.width.%]="r.matching_percentage"></div></div><small class="block text-xs font-normal muted mt-1">Sur les critères communs évalués</small>}</td><td class="p-4 tabular-nums font-medium text-emerald-700 dark:text-emerald-400">{{r.documented}}</td><td class="p-4 tabular-nums font-medium text-amber-700 dark:text-amber-400">{{r.to_review}}</td><td class="p-4"><span class="status-pill" [class.status-pill--good]="r.state==='documentary_coverage'" [class.status-pill--warning]="r.state==='partial_review_required'">{{stateLabel(r.state)}}</span></td><td class="p-4"><a class="inline-link whitespace-nowrap text-sm" [routerLink]="['/matching/resultat',r.id]">Comprendre →</a></td></tr>}</tbody></table></div>}
<div class="p-4 flex justify-between items-center"><button class="btn-light" [disabled]="offset()===0" (click)="page(-1)">Précédent</button><small class="text-slate-500">{{offset()+1}} – {{offset()+results().length}} sur {{total()}}</small><button class="btn-light" [disabled]="offset()+30>=total()" (click)="page(1)"><tr-icon name="arrow-right" [size]="16" class="inline-flex align-middle mr-1"/>Suivant</button></div></section>
@if(comparison();as cr){<section class="card p-5 mt-5"><h3 class="text-lg font-bold mb-2">Comparaison documentaire</h3><p class="text-xs muted mb-3">Ce graphique présente uniquement les mentions identifiées. Il ne désigne pas de meilleur candidat.</p><tr-native-chart kind="bars" [data]="compareChartItems()" [height]="240" description="Mentions documentées par dossier comparé"/><div class="overflow-x-auto"><table class="w-full min-w-[600px] text-sm text-left"><thead class="table-head"><tr><th class="p-3">Référence</th><th>Correspondance pondérée</th><th>Éléments trouvés</th><th>À vérifier</th></tr></thead><tbody>@for(r of cr;track r.id){<tr><td class="p-3 font-mono">{{r.candidate_reference_id.slice(0,8)}}</td><td>{{matchingDisplay(r)}}@if(r.rank!==null && r.rank!==undefined){<small class="block text-xs muted">Rang #{{r.rank}} · {{r.ranking_scope_percent}} % du poids du poste évalué</small>}</td><td>{{r.documented}}</td><td>{{r.to_review}}</td></tr>}</tbody></table></div><div class="mt-4 space-y-3">@for(r of cr;track r.id){<div class="rounded-lg border border-slate-200 p-3 dark:border-slate-700"><h4 class="font-semibold mb-2">{{r.candidate_reference_id.slice(0,8)}} · {{stateLabel(r.state)}}</h4>@for(c of r.criteria||[];track c.code){<p class="text-sm py-1 border-b border-slate-100 dark:border-slate-800"><strong>{{c.label}}</strong> : {{c.state | humanStatus:'run'}} · {{c.state==='manual_review_required'||c.state==='needs_review'||c.state==='awaiting_documents'?'Non évalué':'+'+c.contribution.toFixed(2)+' pts'}}</p>}</div>}</div><p class="text-xs text-slate-500 mt-4">Consultez les preuves individuelles. Aucun candidat n'est déclaré gagnant.</p></section>}
}
`})
export class MatchingPage implements OnInit,OnDestroy {
 private http=inject(HttpClient);readonly auth=inject(AuthService);
 private readonly destroyRef=inject(DestroyRef);
 private timer?:ReturnType<typeof setInterval>;
 private runsRequest=0;private resultsRequest=0;
 readonly refreshing=signal(false);readonly ranking=signal<RankingSummary|null>(null);
 readonly selectedRun=computed(()=>this.runs().find(run=>run.id===this.selectedRunId())??null);
 readonly hasActiveRun=computed(()=>this.runs().some(run=>run.campaign_id===this.campaignId&&this.isActive(run)));
 readonly campaigns=signal<Campaign[]>([]);readonly runs=signal<MatchingRun[]>([]);readonly results=signal<Result[]>([]);
 readonly compareChartItems = computed<ChartDatum[]>(()=> (this.comparison()??[]).map(r=>({label:r.candidate_reference_id.slice(0,8),value:r.documented})));
 readonly config=signal<Configuration|null>(null);readonly comparison=signal<Result[]|null>(null);
 readonly selectedRunId=signal('');readonly error=signal('');readonly info=signal('');
 readonly loading=signal(false);readonly resultsLoading=signal(false);readonly busy=signal(false);readonly compareIds=signal<string[]>([]);readonly total=signal(0);readonly offset=signal(0);
 campaignId='';weights:Weights={essential:60,desirable:20,experience:10,projects_training:10};
 ngOnInit(){void this.initialize();this.timer=setInterval(()=>{
  if(this.runs().some(run=>this.isActive(run))&&!this.refreshing()&&!this.loading()&&!this.busy())void this.refresh();
 },2000);}
 ngOnDestroy(){if(this.timer)clearInterval(this.timer);}
 isActive(run:MatchingRun){return run.status==='queued'||run.status==='running';}
 matchingDisplay(result:Result){return result.matching_percentage!==null&&result.matching_percentage!==undefined?new Intl.NumberFormat('fr-FR',{maximumFractionDigits:2}).format(result.matching_percentage)+' %':'Non calculable';}
 async initialize(){this.loading.set(true);this.error.set('');try{const [campaigns,config]=await Promise.all([
    firstValueFrom(this.http.get<Page<Campaign>>('/api/v1/campaigns?limit=100')),
    firstValueFrom(this.http.get<Configuration>('/api/v1/matching/configuration'))]);
    this.campaigns.set(campaigns.items);this.config.set(config);this.weights={...config.weights};
    if(campaigns.items.length){this.campaignId=campaigns.items[0].id;await this.loadRuns();}
  }catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 weightSum(){return this.weights.essential+this.weights.desirable+this.weights.experience+this.weights.projects_training;}
 scope(r:Result):{evaluable_subset_coverage:number|null;assessable_weight_percent:number}|null {
  return (r.group_coverage?.['summary'] as {evaluable_subset_coverage:number|null;assessable_weight_percent:number}|undefined)??null;
 }
 coverageDisplay(r:Result){const s=this.scope(r);return r.score!==null?r.score+' / 100':s?.evaluable_subset_coverage!==null&&s?.evaluable_subset_coverage!==undefined?s.evaluable_subset_coverage+' / 100':'À examiner';}
 stateLabel(value:string){return ({awaiting_documents:'CV non prêts',partial_review_required:'Vérification nécessaire',documentary_coverage:'Critères vérifiés'} as Record<string,string>)[value]||value;}
 selectionChanged(){this.ranking.set(null);this.runs.set([]);this.selectedRunId.set('');this.total.set(0);this.offset.set(0);this.info.set('');this.error.set('');this.compareIds.set([]);this.results.set([]);this.comparison.set(null);void this.loadRuns();}
 async loadRuns(){
  const campaign=this.campaignId;const request=++this.runsRequest;
  try{const params:Record<string,string>={};if(campaign)params['campaign_id']=campaign;
   const data=await firstValueFrom(this.http.get<{items:MatchingRun[]}>('/api/v1/matching-runs',{params}).pipe(takeUntilDestroyed(this.destroyRef)));
   if(this.destroyRef.destroyed||request!==this.runsRequest||campaign!==this.campaignId)return;
   this.runs.set(data.items);
   if(!this.selectedRunId()&&data.items.length)this.selectRun(data.items[0].id);
  }catch(e){if(!this.destroyRef.destroyed&&request===this.runsRequest&&campaign===this.campaignId)this.error.set(apiError(e));}
 }
 async saveWeights(){this.error.set('');this.busy.set(true);try{const res=await firstValueFrom(this.http.post<Configuration>('/api/v1/matching/configuration',this.weights));this.config.set(res);this.info.set('Pondérations enregistrées en version '+res.version+'.');}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async launch(){if(this.busy()||this.hasActiveRun())return;const campaign=this.campaigns().find(x=>x.id===this.campaignId);if(!campaign)return;
  this.busy.set(true);this.error.set('');this.info.set('');try{
  const run=await firstValueFrom(this.http.post<MatchingRun>(`/api/v1/jobs/${campaign.job_id}/matching-runs`,{}, {params:{campaign_id:campaign.id}}));
  this.info.set('Analyse lancée. Le classement s’actualise automatiquement pendant le traitement.');this.runs.update(runs=>[run,...runs.filter(r=>r.id!==run.id)]);this.selectRun(run.id);
  }catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 selectRun(id:string){this.ranking.set(null);this.selectedRunId.set(id);this.results.set([]);this.total.set(0);this.offset.set(0);this.compareIds.set([]);this.comparison.set(null);void this.loadResults();}
 async loadResults(){
  const id=this.selectedRunId();const offset=this.offset();if(!id)return;
  const request=++this.resultsRequest;this.resultsLoading.set(true);
  try{const result=await firstValueFrom(this.http.get<Page<Result>&{ranking:RankingSummary}>(`/api/v1/matching-runs/${id}/results`,{params:{limit:30,offset}}).pipe(takeUntilDestroyed(this.destroyRef)));
   if(!this.destroyRef.destroyed&&id===this.selectedRunId()&&offset===this.offset()&&request===this.resultsRequest){this.results.set(result.items);this.total.set(result.total);this.ranking.set(result.ranking??null);}
  }catch(e){if(!this.destroyRef.destroyed&&request===this.resultsRequest&&id===this.selectedRunId())this.error.set(apiError(e));}
  finally{if(request===this.resultsRequest)this.resultsLoading.set(false);}
 }
 async refresh(){if(this.refreshing())return;this.refreshing.set(true);this.error.set('');
  try{await this.loadRuns();if(!this.resultsLoading())await this.loadResults();}finally{this.refreshing.set(false);}}
 page(dir:number){this.offset.update(v=>Math.max(0,v+30*dir));void this.loadResults();}
 toggleCompare(id:string,checked:boolean){this.compareIds.update(ids=>checked?[...ids,id].slice(0,5):ids.filter(v=>v!==id));this.comparison.set(null);}
 async compare(){try{let response=await firstValueFrom(this.http.post<{items:Result[]}>(`/api/v1/matching-runs/${this.selectedRunId()}/compare`,{result_ids:this.compareIds()}));this.comparison.set(response.items);}catch(e){this.error.set(apiError(e));}}
}
