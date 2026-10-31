import { VisualGuide } from '../../shared/ui/visual-guide';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { TrIcon } from '../../shared/ui/tr-icon';
import { NativeChart } from '../../shared/ui/native-chart';
import type { ChartDatum } from '../../shared/ui/native-chart';
import { apiError } from '../../shared/recruitment';
import { MatchingCriterion, MatchingResultView, DocumentaryEvidence, CriterionFilter, criterionKind, criterionStatus, coverageScope } from '../../shared/matching-presentation';

interface ComparedResult extends MatchingResultView {stale:boolean;criteria:MatchingCriterion[]}
interface ComparedResponse {items:ComparedResult[];note:string}
interface ExplanationResponse {id:string;criteria:MatchingCriterion[];stale:boolean}
interface CriterionRow {code:string;label:string}

@Component({selector:'tr-matching-compare',standalone:true,imports:[VisualGuide, TrIcon,RouterLink,NativeChart],template:`
<header class="page-intro"><div><a routerLink="/matching" class="inline-link text-sm"><tr-icon name="arrow-left" [size]="16"/> Analyses</a>
  <p class="eyebrow mt-4"><tr-icon name="compare" [size]="16"/> Voir les parcours ensemble</p><h1>Comparer les candidatures</h1>
  <p>Examinez les mentions trouvées pour chaque critère. Ce tableau ne choisit pas un candidat à votre place.</p></div>
  <button type="button" class="btn-light" (click)="reload()" [disabled]="loading()"><tr-icon name="refresh-cw" [size]="17"/> Actualiser</button>
</header>
<tr-visual-guide title="Avant de comparer les dossiers" description="Examinez les critères communs, les preuves disponibles et les éléments qui demandent une vérification." />
@if(error()){<div class="alert-error mb-5" role="alert">{{error()}}</div>}
@if(loading()){<div class="card p-8" role="status">Chargement des candidatures et des critères…</div>}
@if(items().length){
  <div class="human-callout mb-5 p-4 text-sm"><tr-icon name="shield-check" [size]="17"/><strong> Comparaison documentaire seulement.</strong> Une mention non retrouvée ne prouve pas l'absence d'une compétence. Les résultats incomplets ne sont pas notés zéro.</div>
  <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-3 mb-6" aria-label="Dossiers sélectionnés">
    @for(r of items();track r.id){<article class="card p-5 flex flex-col gap-3"><p class="eyebrow"><tr-icon name="user-round" [size]="15"/> Dossier {{ $index+1 }}</p>
      <h2 class="font-semibold break-all">Réf. {{r.candidate_reference_id.slice(0,8)}}</h2>@if(r.stale){<p role="status" class="alert-error text-xs">Preuves modifiées : nouvelle analyse nécessaire.</p>}
      <div><strong class="text-2xl">{{r.stale?'À actualiser':coverageDisplay(r)}}</strong><p class="text-xs muted">Correspondance pondérée au poste</p>
        @if(r.rank!==null && r.rank!==undefined){<p class="text-sm font-semibold mt-2">Rang #{{r.rank}}</p><p class="text-xs muted">Critères communs évalués : {{r.ranking_scope_percent}} % du poids du poste.</p>}
      </div>
      <dl class="grid grid-cols-3 gap-3 border-t pt-3 border-slate-200 dark:border-slate-700 text-center"><div><dt class="text-xs muted">Mentions</dt><dd class="font-bold">{{r.documented??0}}</dd></div><div><dt class="text-xs muted">À vérifier</dt><dd class="font-bold">{{r.to_review??0}}</dd></div><div><dt class="text-xs muted">Non trouvées</dt><dd class="font-bold">{{r.not_documented??0}}</dd></div></dl>
      <a class="inline-link text-sm mt-auto" [routerLink]="['/matching/resultat',r.id]">Consulter son analyse <tr-icon name="arrow-up-right" [size]="15"/></a>
    </article>}
  </section>
  <section class="card p-5 sm:p-6 mb-6" aria-label="Graphique des mentions par candidature"><h2 class="section-heading">Mentions documentées</h2><p class="section-caption mb-4">Ce graphique compare le nombre de mentions reconnues, pas les aptitudes humaines.</p>
    <tr-native-chart kind="bars" [data]="chartItems()" [height]="MathMax(220,items().length*58)" description="Nombre de mentions reconnues par candidature, à interpréter avec les preuves sources"/>
  </section>
  <section class="card overflow-hidden" aria-label="Critères comparés">
    <div class="p-5 sm:p-6 border-b border-slate-200 dark:border-slate-700 flex flex-wrap justify-between gap-3"><div><h2 class="section-heading">Critère par critère</h2><p class="section-caption mt-1">{{filteredRows().length}} critère(s) · {{items().length}} dossier(s)</p></div>
      <div class="flex flex-wrap gap-2" role="group" aria-label="Filtrer les critères">
        @for(option of filters;track option.value){<button type="button" class="btn-light !min-h-9" [attr.aria-pressed]="filter()===option.value" [class.border-blue-500]="filter()===option.value" (click)="filter.set(option.value)">{{option.label}}</button>}
      </div>
    </div>
    <div class="overflow-x-auto" tabindex="0" aria-label="Tableau comparatif défilant horizontalement">
      <table class="w-full text-left text-sm border-collapse" [style.minWidth.px]="240+items().length*240">
        <caption class="sr-only">Comparaison des critères professionnels entre deux à cinq dossiers</caption>
        <thead class="table-head"><tr><th scope="col" class="p-4 w-[240px] min-w-[240px] sticky left-0 bg-slate-100 dark:bg-slate-800 z-10">Critère demandé</th>@for(r of items();track r.id){<th scope="col" class="p-4 min-w-[240px]">Dossier {{r.candidate_reference_id.slice(0,8)}}</th>}</tr></thead>
        <tbody>@for(row of filteredRows();track row.code){<tr class="border-t border-slate-200 dark:border-slate-700 align-top"><th scope="row" class="p-4 font-semibold sticky left-0 bg-white dark:bg-[#142331] z-10">{{row.label}}</th>
        @for(r of items();track r.id){<td class="p-4 min-w-[240px]">
          @if(findCriterion(r,row.code);as c){<span class="criterion-chip" [class.criterion-chip-good]="kind(c.state)==='documented'" [class.criterion-chip-review]="kind(c.state)==='review'">{{status(c.state)}}</span>
            @if(kind(c.state)==='documented'){<p class="mt-2 text-xs muted">Contribution documentaire : +{{c.contribution.toFixed(2)}} point(s)</p>}
            <button type="button" class="inline-link text-xs mt-3" [disabled]="proofBusy()===r.id" (click)="showEvidence(r.id,c.code)"><tr-icon name="search" [size]="15"/> {{proofBusy()===r.id?'Chargement…':'Voir l’explication'}}</button>
            @if(openProof()===r.id+'|'+c.code){<div class="mt-3 rounded-xl bg-slate-50 p-3 dark:bg-slate-800">
              @if(proofError()){<p class="text-xs" role="alert">{{proofError()}}</p>}
              @else if(proof(r.id,c.code);as e){<p class="text-xs mb-2">CV · page {{e.page_number}} {{e.source_still_matches?'':'· extrait devenu indisponible'}}</p>
                @if(e.source_still_matches){<blockquote class="text-sm break-words">{{e.source_excerpt||e.matched_text}}</blockquote>
                  <a class="inline-link text-xs mt-2 inline-flex gap-1" [routerLink]="['/documents',e.document_id,'visionneuse']" [queryParams]="{page:e.page_number,start:e.start_offset,end:e.end_offset}">Ouvrir le CV <tr-icon name="arrow-up-right" [size]="14"/></a>}
                @else{<p class="text-xs">La preuve a changé. Une nouvelle analyse est nécessaire.</p>}
              }@else{<p class="text-xs">Aucun passage source confirmé pour ce critère.</p>}
            </div>}
          }@else{<span class="text-xs muted">Critère non enregistré dans ce résultat</span>}
        </td>}
        </tr>}</tbody>
      </table>
    </div>
    @if(!filteredRows().length){<p class="section-caption p-6">Aucun critère ne correspond à ce filtre.</p>}
  </section>
  <p class="mt-5 text-xs muted"><tr-icon name="info" [size]="15"/> Les documents et preuves sont chargés uniquement pour les utilisateurs autorisés par le serveur.</p>
}
`})
export class MatchingCompare implements OnInit {
  private readonly http=inject(HttpClient);private readonly route=inject(ActivatedRoute);
  readonly loading=signal(true);readonly error=signal('');readonly items=signal<ComparedResult[]>([]);
  readonly filter=signal<CriterionFilter>('all');readonly openProof=signal<string|null>(null);
  readonly proofBusy=signal<string|null>(null);readonly proofError=signal('');
  readonly proofCache=signal<Record<string,ExplanationResponse>>({});
  readonly filters:{value:CriterionFilter;label:string}[]=[{value:'all',label:'Tous'},{value:'documented',label:'Documentés'},{value:'review',label:'À vérifier'},{value:'not_found',label:'Non retrouvés'}];
  readonly rows=computed<CriterionRow[]>(()=>{
    const unique=new Map<string,CriterionRow>();
    for(const item of this.items())for(const c of item.criteria){if(!unique.has(c.code))unique.set(c.code,{code:c.code,label:c.label});}
    return [...unique.values()].sort((a,b)=>a.label.localeCompare(b.label,'fr'));
  });
  readonly filteredRows=computed(()=>this.rows().filter(row=>this.filter()==='all'||this.items().some(item=>{const c=this.findCriterion(item,row.code);return c&&criterionKind(c.state)===this.filter();})));
  readonly chartItems=computed<ChartDatum[]>(()=>this.items().map(r=>({label:'Dossier '+r.candidate_reference_id.slice(0,8),value:r.documented??0})));
  MathMax=Math.max;
  scope(r:MatchingResultView){return coverageScope(r.group_coverage);}
  coverageDisplay(r:MatchingResultView){return r.matching_percentage!==null&&r.matching_percentage!==undefined?new Intl.NumberFormat('fr-FR',{maximumFractionDigits:2}).format(r.matching_percentage)+' %':'Non calculable';}
  kind=criterionKind;status=criterionStatus;
  ngOnInit(){void this.reload();}
  findCriterion(r:ComparedResult,code:string):MatchingCriterion|undefined{return r.criteria.find(c=>c.code===code);}
  proof(id:string,code:string):DocumentaryEvidence|null{return this.proofCache()[id]?.criteria.find(c=>c.code===code)?.evidence??null;}
  async reload(){this.error.set('');this.loading.set(true);this.openProof.set(null);this.proofCache.set({});try{
    const runId=this.route.snapshot.paramMap.get('id');
    const ids=(this.route.snapshot.queryParamMap.get('ids')??'').split(',').filter(Boolean);
    if(!runId||ids.length<2||ids.length>5||new Set(ids).size!==ids.length||ids.some(id=>id.length>80))throw new Error('Sélectionnez entre deux et cinq résultats de la même analyse.');
    const response=await firstValueFrom(this.http.post<ComparedResponse>(`/api/v1/matching-runs/${encodeURIComponent(runId)}/compare`,{result_ids:ids}));
    this.items.set(response.items);
  }catch(e){this.error.set(apiError(e));this.items.set([]);}finally{this.loading.set(false);}}
  async showEvidence(id:string,code:string){const key=id+'|'+code;if(this.openProof()===key){this.openProof.set(null);return;}
    this.openProof.set(key);this.proofError.set('');if(this.proofCache()[id])return;
    this.proofBusy.set(id);try{const explanation=await firstValueFrom(this.http.get<ExplanationResponse>(`/api/v1/matching-results/${encodeURIComponent(id)}/explanation`));this.proofCache.update(cache=>({...cache,[id]:explanation}));
      if(explanation.stale)this.proofError.set('Les preuves ont changé depuis ce calcul. Une nouvelle analyse est nécessaire.');
    }catch(e){this.proofError.set(apiError(e));}finally{this.proofBusy.set(null);}}
}
