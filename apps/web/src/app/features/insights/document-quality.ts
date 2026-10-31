import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute,RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { apiError } from '../../shared/recruitment';
import { EmptyState } from '../../shared/ui/empty-state';
interface Flag{page_number:number|null;code:string;severity:string;message:string;source_excerpt:string|null}
interface Quality {quality_state:string;processing_status:string;flags:Flag[];limitations:string[]}
@Component({selector:'tr-document-quality',standalone:true,imports:[TrIcon,RouterLink,EmptyState],template:`
<a [routerLink]="['/documents',id,'visionneuse']" class="inline-link text-sm">← Retour au CV</a>
<header class="page-intro mt-5"><div><p class="eyebrow"><tr-icon name="shield" [size]="15"/> Fiabilité des informations</p><h1>Contrôle du document</h1><p>Ces alertes aident à vérifier une extraction. Elles ne constituent ni un diagnostic de fraude ni un jugement sur la personne.</p></div><button type="button" class="btn-light" [disabled]="loading()" (click)="load()">Relancer la consultation</button></header>
@if(error()){<div role="alert" class="alert-error mb-5">{{error()}}</div>}
@if(loading()){<div role="status" class="card p-7">Chargement des indicateurs de qualité…</div>}
@if(data();as d){<div class="grid gap-3 sm:grid-cols-3 mb-6"><div class="stat-card"><span class="meta-label">Traitement du document</span><strong class="text-base mt-2">{{statusLabel(d.processing_status)}}</strong></div><div class="stat-card"><span class="meta-label">Contrôle qualité</span><strong class="text-base mt-2">{{statusLabel(d.quality_state)}}</strong></div><div class="stat-card"><span class="meta-label">Points à vérifier</span><strong class="text-3xl">{{d.flags.length}}</strong></div></div>
<section class="card overflow-hidden"><div class="p-5 sm:p-6 border-b border-slate-100 dark:border-slate-700"><h2 class="section-heading">Observations relevées</h2><p class="section-caption mt-1">Une page sans alerte n'est pas nécessairement une page correctement reconnue.</p><label class="block mt-4 max-w-xs"><span class="field-label">Afficher les alertes</span><select class="field" [value]="severity()" (change)="severity.set($any($event.target).value)"><option value="">Toutes les observations</option>@for(x of severities();track x){<option [value]="x">{{severityLabel(x)}}</option>}</select></label></div>
@if(!filtered().length){<tr-empty-state title="Aucune alerte dans cette sélection" description="Aucune règle n'a signalé de problème dans la sélection actuelle. Une vérification humaine reste possible."/>}
@else{<div class="p-5 sm:p-6 space-y-3">@for(x of filtered();track $index){<article class="rounded-2xl border border-slate-200 p-4 sm:p-5 dark:border-slate-700"><div class="flex flex-wrap justify-between gap-2"><span class="soft-badge">{{severityLabel(x.severity)}}</span><span class="text-xs muted">{{x.page_number?'Page '+x.page_number:'Document entier'}}</span></div><h3 class="mt-3 font-semibold">{{x.message}}</h3>@if(x.source_excerpt){<blockquote class="mt-3 rounded-xl border-l-4 border-slate-300 bg-slate-50 p-4 text-sm break-words whitespace-pre-wrap dark:bg-slate-800 dark:border-slate-600">{{x.source_excerpt}}</blockquote>}<p class="text-xs muted mt-3">Règle : {{x.code}}</p></article>}</div>}
</section>
@if(d.limitations.length){<section class="card p-6 mt-5"><h2 class="section-heading">Ce que ce contrôle ne peut pas garantir</h2><ul class="mt-3 list-disc pl-5 text-sm leading-relaxed muted space-y-2">@for(l of d.limitations;track l){<li>{{l}}</li>}</ul></section>}
<div class="flex flex-wrap gap-3 mt-5"><a [routerLink]="['/documents',id,'visionneuse']" class="btn-primary">Lire le document et les extraits</a><a class="btn-light" routerLink="/importations">Retour aux importations</a></div>}
`})
export class DocumentQuality implements OnInit {
 private readonly http=inject(HttpClient);private readonly route=inject(ActivatedRoute);
 readonly data=signal<Quality|null>(null);readonly loading=signal(true);readonly error=signal('');readonly severity=signal('');
 readonly severities=computed(()=>[...new Set(this.data()?.flags.map(x=>x.severity)??[])]);
 readonly filtered=computed(()=>this.data()?.flags.filter(x=>!this.severity()||x.severity===this.severity())??[]);
 get id(){return this.route.snapshot.paramMap.get('id')??'';}
 ngOnInit(){void this.load();}
 severityLabel(value:string){return ({error:'Erreur technique',warning:'À vérifier',info:'Information',high:'Attention élevée',medium:'Attention',low:'Information'} as Record<string,string>)[value]??value.replaceAll('_',' ');}
 statusLabel(value:string){return ({completed:'Terminé',done:'Terminé',failed:'Échec',needs_review:'Vérification nécessaire',processing:'En traitement',pending:'En attente',ok:'Aucune anomalie signalée'} as Record<string,string>)[value]??value.replaceAll('_',' ');}
 async load(){this.loading.set(true);this.error.set('');try{this.data.set(await firstValueFrom(this.http.get<Quality>(`/api/v1/documents/${encodeURIComponent(this.id)}/quality`)));}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
}
