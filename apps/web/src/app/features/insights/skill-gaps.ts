import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, computed, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { apiError } from '../../shared/recruitment';
interface Entry {code:string;label:string;category:string;state:string;has_source:boolean;contribution:number}
interface Gap {score:number|null;evaluable_subset_coverage:number|null;assessable_weight_percent:number|null;documented:Entry[];needs_review:Entry[];not_found:Entry[];other:Entry[];warning:string}
@Component({selector:'tr-skill-gaps',standalone:true,imports:[TrIcon,RouterLink],template:`
<a [routerLink]="['/matching/resultat',id]" class="inline-link text-sm">← Retour aux justifications</a>
<header class="page-intro mt-5"><div><p class="eyebrow"><tr-icon name="target" [size]="15"/> Correspondance expliquée</p><h1>Ce que le CV permet de vérifier</h1><p>Un CV présente une partie du parcours d'une personne. Une compétence non retrouvée n'est pas nécessairement une compétence absente.</p></div><a routerLink="/formations" class="btn-light">Catalogue des formations</a></header>
@if(error()){<div class="alert-error mb-5" role="alert">{{error()}} <button type="button" class="underline ml-2" (click)="load()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Réessayer</button></div>}
@if(loading()){<div role="status" class="card p-7">Chargement des observations par critère…</div>}
@if(data();as d){<div class="card p-6 mb-5"><div class="flex flex-wrap items-center justify-between gap-4"><div><p class="meta-label">{{d.score===null?'Couverture des critères évaluables':'Couverture documentaire'}}</p><p class="text-3xl font-bold mt-2">{{coverageDisplay(d)}}</p>@if(d.score===null&&d.assessable_weight_percent!==null){<p class="text-xs muted mt-1">sur {{d.assessable_weight_percent}} % des critères pondérés</p>}</div><div class="soft-panel p-4 text-sm max-w-xl">{{d.warning}}</div></div></div>
<div class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6"><div class="stat-card"><span class="meta-label">Documentées</span><strong class="text-3xl">{{d.documented.length}}</strong></div><div class="stat-card"><span class="meta-label">À vérifier</span><strong class="text-3xl">{{d.needs_review.length}}</strong></div><div class="stat-card"><span class="meta-label">Non retrouvées</span><strong class="text-3xl">{{d.not_found.length}}</strong></div><div class="stat-card"><span class="meta-label">Autres</span><strong class="text-3xl">{{d.other.length}}</strong></div></div>
<div class="grid gap-5 lg:grid-cols-2">@for(group of groups(d);track group.key){<section class="card overflow-hidden"><div class="px-5 py-5 border-b border-slate-100 dark:border-slate-700"><h2 class="section-heading">{{group.title}} <span class="text-sm muted">({{group.items.length}})</span></h2><p class="section-caption mt-1">{{group.description}}</p></div>
@if(!group.items.length){<p class="p-6 muted text-sm">Aucun critère dans cette catégorie.</p>}
@else{<div class="divide-y divide-slate-100 dark:divide-slate-700">@for(x of group.items;track x.code){<div class="p-5"><div class="flex flex-wrap items-center justify-between gap-2"><strong>{{x.label}}</strong><span class="soft-badge">{{x.has_source?'Extrait lié':'Sans extrait lié'}}</span></div><p class="text-xs muted mt-2">{{categoryLabel(x.category)}} · {{stateLabel(x.state)}}</p>@if(x.contribution>0){<p class="mt-1 text-xs font-semibold">Contribution calculée : {{x.contribution}} point(s)</p>}</div>}</div>}</section>}</div>
<p class="section-caption mt-5">Le catalogue des formations présente des ressources vérifiables, mais aucune formation ou compétence n'est attribuée automatiquement à un candidat.</p>}
`})
export class SkillGaps implements OnInit {
 private readonly http=inject(HttpClient);private readonly route=inject(ActivatedRoute);
 readonly data=signal<Gap|null>(null);readonly loading=signal(true);readonly error=signal('');
 get id(){return this.route.snapshot.paramMap.get('id')??'';}
 ngOnInit(){void this.load();}
 coverageDisplay(d:Gap){return d.score!==null?d.score.toFixed(1)+'/100':d.evaluable_subset_coverage!==null?d.evaluable_subset_coverage.toFixed(1)+'/100':'À examiner';}
 async load(){this.loading.set(true);this.error.set('');try{this.data.set(await firstValueFrom(this.http.get<Gap>(`/api/v1/matching-results/${encodeURIComponent(this.id)}/gaps`)));}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 groups(d:Gap){return [
  {key:'doc',title:'Compétences documentées',description:'Le CV contient une mention reliée au critère.',items:d.documented},
  {key:'review',title:'Points à confirmer',description:'Éléments incertains ou non évaluables automatiquement.',items:d.needs_review},
  {key:'missing',title:'Non retrouvées dans ce CV',description:'Aucune preuve extraite ne correspond actuellement au critère.',items:d.not_found},
  {key:'other',title:'Autres observations',description:'États complémentaires enregistrés par le moteur.',items:d.other}];}
 categoryLabel(v:string){return ({skill:'Compétence',experience:'Expérience',qualification:'Qualification',certification:'Certification',language:'Langue',other:'Autre'} as Record<string,string>)[v]??v;}
 stateLabel(v:string){return ({documented_mention:'Mention documentée',needs_review:'À vérifier',manual_review_required:'Examen humain requis',not_documented:'Non retrouvée',not_found:'Non retrouvée'} as Record<string,string>)[v]??v.replaceAll('_',' ');}
}
