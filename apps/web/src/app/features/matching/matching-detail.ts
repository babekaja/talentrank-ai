import { VisualGuide } from '../../shared/ui/visual-guide';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { TrIcon } from '../../shared/ui/tr-icon';
import { NativeChart } from '../../shared/ui/native-chart';
import type { ChartDatum } from '../../shared/ui/native-chart';
import { apiError } from '../../shared/recruitment';
import { MatchingCriterion, MatchingResultView, CriterionFilter, criterionKind, criterionStatus, criterionReason, coverageScope } from '../../shared/matching-presentation';

interface Detail extends MatchingResultView {
  run_id:string;criteria_version:number;algorithm_version:string;
  configuration_version:number;stale:boolean;criteria:MatchingCriterion[];disclaimer:string;
}
@Component({selector:'tr-matching-detail',standalone:true,imports:[VisualGuide, TrIcon,RouterLink,NativeChart],template:`
<header class="page-intro"><div><a routerLink="/matching" class="inline-link text-sm"><tr-icon name="arrow-left" [size]="16"/> Toutes les analyses</a>
  <p class="eyebrow mt-4"><tr-icon name="clipboard-check" [size]="16"/> Comprendre le résultat</p><h1>Pourquoi cette correspondance ?</h1><p>Chaque constat s'appuie sur les critères approuvés et les passages réellement extraits du CV.</p></div>
  <button class="btn-light" type="button" (click)="load()" [disabled]="loading()"><tr-icon name="refresh-cw" [size]="17"/> Actualiser</button>
</header>
<tr-visual-guide title="Vérifiez les passages avant de conclure" description="Une explication indique ce qui a été trouvé dans le document, sans juger toute une personne." />
@if(error()){<div class="alert-error mb-5" role="alert">{{error()}}</div>}
@if(loading()){<div class="card p-8" role="status">Chargement du résultat et de ses preuves…</div>}
@if(detail();as d){
  @if(d.stale){<div class="alert-error mb-5" role="alert"><tr-icon name="alert" [size]="18"/> Les informations source ont changé depuis le calcul. Ce résultat doit être actualisé avant toute utilisation.</div>}
  <div class="grid gap-5 lg:grid-cols-[1.15fr_.85fr] mb-6">
    <section class="card p-6 sm:p-7"><p class="eyebrow"><tr-icon name="user-round" [size]="15"/> Dossier {{d.candidate_reference_id.slice(0,8)}}</p>
      @if(d.matching_percentage!==null && d.matching_percentage!==undefined){<div class="soft-panel mt-4 p-4"><p class="text-sm font-semibold">Rang #{{d.rank}} · correspondance pondérée au poste</p><p class="text-3xl font-bold mt-2">{{d.matching_percentage}} %</p><p class="text-xs muted mt-2">Comparaison sur les critères communs évalués, représentant {{d.ranking_scope_percent}} % du poids du poste.</p></div>}
      <div class="flex flex-wrap items-start justify-between gap-3 mt-4"><div><p class="text-xs muted">{{d.score===null?'Couverture des critères évaluables':'Couverture documentaire'}}</p><strong class="text-4xl font-bold">{{coverageDisplay(d)}}</strong></div>
       <span class="soft-badge">{{d.criteria.length}} critères analysés</span></div>
      @if(d.score===null){<div class="human-callout p-4 mt-5 text-sm"><strong>Une revue humaine est nécessaire.</strong> La couverture complète ne peut pas être calculée, car certains critères ne sont pas évaluables automatiquement.
        @if(scope(d);as s){@if(s.evaluable_subset_coverage!==null){<p class="mt-2">Couverture des seules mentions évaluables : {{s.evaluable_subset_coverage}}/100, sur {{s.assessable_weight_percent}} % des critères pondérés. Ce n'est pas un score global.</p>}}
      </div>}
      @else{<p class="section-caption mt-4">Cette note décrit uniquement la couverture des critères documentés. Elle ne prédit pas la réussite professionnelle.</p>}
      <div class="flex gap-3 flex-wrap mt-6">
        <a class="btn-light" [routerLink]="['/matching/resultat',d.id,'ecarts']"><tr-icon name="list-checks" [size]="17"/> Voir les écarts</a>
        <a class="btn-light" [routerLink]="['/matching/resultat',d.id,'opportunites']"><tr-icon name="graduation-cap" [size]="17"/> Parcours de formation</a>
        <button type="button" class="btn-primary" (click)="review()" [disabled]="busy()"><tr-icon name="users" [size]="17"/> {{busy()?'Enregistrement…':'Demander un examen humain'}}</button>
      </div>
      @if(message()){<p role="status" class="alert-ok mt-4">{{message()}}</p>}
    </section>
    <section class="card p-5 sm:p-6"><h2 class="section-heading">Ce que contient le dossier</h2><p class="section-caption mt-1">Répartition des critères, pas une évaluation de la personne.</p>
      @if(d.criteria.length){<tr-native-chart kind="donut" [data]="chartData()" [height]="230" description="Nombre de critères documentés, à vérifier et non retrouvés"/>}
      @else{<p class="section-caption mt-4">Aucun critère enregistré pour cette analyse.</p>}
      <dl class="grid grid-cols-3 text-center gap-2 mt-2"><div><dt class="text-xs muted">Documentés</dt><dd class="text-xl font-bold">{{count('documented')}}</dd></div><div><dt class="text-xs muted">À vérifier</dt><dd class="text-xl font-bold">{{count('review')}}</dd></div><div><dt class="text-xs muted">Non retrouvés</dt><dd class="text-xl font-bold">{{count('not_found')}}</dd></div></dl>
    </section>
  </div>
  <section class="card overflow-hidden" aria-label="Explication par critère">
    <div class="px-5 sm:px-6 py-5 border-b border-slate-200 dark:border-slate-700"><h2 class="section-heading">Examiner les critères du poste</h2><p class="section-caption mt-1">Sélectionnez un statut, puis ouvrez une preuve pour vérifier le passage d'origine.</p>
      <div class="flex flex-wrap gap-2 mt-4" role="group" aria-label="Filtrer les critères">
        @for(f of filters;track f.value){<button type="button" class="btn-light !min-h-9 transition-colors" [class.!bg-[#205f77]]="filter()===f.value" [class.!text-white]="filter()===f.value" [class.!border-[#205f77]]="filter()===f.value" [attr.aria-pressed]="filter()===f.value" (click)="filter.set(f.value)">{{f.label}}</button>}
      </div>
    </div>
    <div class="divide-y divide-slate-100 dark:divide-slate-700/60">
      @for(c of filteredCriteria();track c.code){<article class="p-5 sm:p-6 hover:bg-[#fafcfd] dark:hover:bg-slate-800/40 transition-colors"><div class="flex flex-wrap items-start justify-between gap-4"><div class="min-w-0 flex-1"><h3 class="font-bold text-lg text-slate-800 dark:text-slate-100">{{c.label}}</h3><p class="text-xs text-slate-400 mt-1 font-mono">{{groupLabel(c.group)}} · critère {{c.code}}</p></div>
          <span class="criterion-chip" [class.criterion-chip-good]="kind(c.state)==='documented'" [class.criterion-chip-review]="kind(c.state)==='review'">{{status(c.state)}}</span></div>
        <p class="section-caption mt-2.5 text-sm">{{reason(c.note_code??'')}}</p>
        @if(kind(c.state)==='documented'){<p class="mt-2 text-xs text-emerald-700 dark:text-emerald-300 font-medium">Contribution au calcul documentaire : +{{c.contribution.toFixed(2)}} point(s)</p>}
        @else{<p class="mt-2 text-xs text-slate-400">Ce critère ne confirme aucune compétence automatiquement.</p>}
        <button type="button" class="inline-link mt-4 text-sm flex items-center gap-1.5" [attr.aria-expanded]="expanded()===c.code" (click)="toggle(c.code)"><tr-icon name="search" [size]="16"/> {{expanded()===c.code?'Masquer la preuve':'Consulter la preuve ou la limite'}}</button>
        @if(expanded()===c.code){<div class="rounded-xl border-l-4 border-l-[#205f77] bg-[#f5fafb] dark:bg-slate-800/80 mt-4 p-4">
            @if(c.evidence;as e){<p class="text-xs text-slate-400 mb-2 font-medium">CV · page {{e.page_number}} · statut : {{e.verification_status_at_run}}</p>
              @if(e.source_still_matches){<blockquote class="leading-relaxed text-sm italic text-slate-700 dark:text-slate-200 break-words border-l-2 border-slate-300 dark:border-slate-600 pl-3.5 my-2">« {{e.source_excerpt||e.matched_text}} »</blockquote>
                <p class="text-xs text-slate-500 mt-2">Expression reconnue : <strong class="text-slate-700 dark:text-slate-300">« {{e.matched_text}} »</strong></p>
                <a [routerLink]="['/documents',e.document_id,'visionneuse']" [queryParams]="{page:e.page_number,start:e.start_offset,end:e.end_offset}"
                  class="btn-light mt-3 !min-h-9 text-xs"><tr-icon name="file-text" [size]="15"/> Ouvrir le CV à la page correspondante</a>
              }@else{<p class="text-sm text-amber-700">La preuve source a été modifiée ou n'est plus disponible. Il faut actualiser l'analyse.</p>}
            }@else{<p class="text-sm text-slate-500">Aucun passage source retenu pour ce critère. Cela ne signifie pas que la compétence est absente du candidat.</p>}
          </div>}
      </article>}
    </div>
    @if(!filteredCriteria().length){<p class="section-caption p-6">Aucun critère à afficher avec ce filtre.</p>}
  </section>
  <details class="card mt-6 p-5 text-sm"><summary class="font-semibold cursor-pointer">Détails techniques et reproductibilité</summary>
    <dl class="mt-4 space-y-2 text-xs muted"><div>Algorithme : {{d.algorithm_version}}</div><div>Version des critères : {{d.criteria_version}}</div><div>Configuration : {{d.configuration_version}}</div><div>{{d.disclaimer}}</div></dl>
  </details>
}
`})
export class MatchingDetail implements OnInit {
  private readonly http=inject(HttpClient);private readonly route=inject(ActivatedRoute);
  readonly detail=signal<Detail|null>(null);readonly loading=signal(true);readonly busy=signal(false);
  readonly error=signal('');readonly message=signal('');
  readonly filter=signal<CriterionFilter>('all');readonly expanded=signal<string|null>(null);
  readonly filters:{value:CriterionFilter;label:string}[]=[{value:'all',label:'Tous'},{value:'documented',label:'Documentés'},{value:'review',label:'À vérifier'},{value:'not_found',label:'Non retrouvés'}];
  readonly chartData=computed<ChartDatum[]>(()=>[
    {label:'Mentions documentées',value:this.count('documented')},
    {label:'À vérifier',value:this.count('review')},
    {label:'Non retrouvées',value:this.count('not_found')},
  ]);
  readonly filteredCriteria=computed(()=>(this.detail()?.criteria??[]).filter(c=>this.filter()==='all'||criterionKind(c.state)===this.filter()));
  kind=criterionKind;status=criterionStatus;reason=criterionReason;
  scope(d:Detail){return coverageScope(d.group_coverage);}
  coverageDisplay(d:Detail){const s=this.scope(d);return d.score!==null?d.score+'/100':s?.evaluable_subset_coverage!==null&&s?.evaluable_subset_coverage!==undefined?s.evaluable_subset_coverage+'/100':'À examiner';}
  groupLabel(group?:string){return ({essential:'Compétence essentielle',desirable:'Compétence souhaitable',experience:'Expérience',projects_training:'Projet ou formation'} as Record<string,string>)[group??'']??'Critère professionnel';}
  count(kind:Exclude<CriterionFilter,'all'>){return this.detail()?.criteria.filter(c=>criterionKind(c.state)===kind).length??0;}
  toggle(code:string){this.expanded.update(v=>v===code?null:code);}
  ngOnInit(){void this.load();}
  async load(){this.loading.set(true);this.error.set('');try{
    const id=this.route.snapshot.paramMap.get('id');if(!id)throw new Error('Identifiant de résultat absent.');
    this.detail.set(await firstValueFrom(this.http.get<Detail>(`/api/v1/matching-results/${encodeURIComponent(id)}/explanation`)));
  }catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
  async review(){this.busy.set(true);this.error.set('');this.message.set('');try{
    const id=this.route.snapshot.paramMap.get('id');if(!id)throw new Error('Résultat introuvable.');
    await firstValueFrom(this.http.post(`/api/v1/matching-results/${encodeURIComponent(id)}/request-review`,{}));
    this.message.set('Demande de vérification enregistrée. La décision reste humaine.');
  }catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
}
