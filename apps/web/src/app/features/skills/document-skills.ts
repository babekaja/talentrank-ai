import { HumanStatus } from '../../shared/ui/human-status';
import { TrIcon } from '../../shared/ui/tr-icon';
import {Component, OnInit, inject, signal} from '@angular/core';
import {HttpClient} from '@angular/common/http';
import {ActivatedRoute, RouterLink} from '@angular/router';
import {firstValueFrom} from 'rxjs';
import {apiError} from '../../shared/recruitment';
interface Mention {id:string;skill_label:string;skill_code:string;matched_text:string;source_quote:string;status:string;method:string;page_number:number;start_offset:number;end_offset:number;rules_version:string;context_code?:string}
interface Fact {id:string;category:string;source_text:string;page_number:number;rule_version:string;review_status:string}
interface FactsResult {items:Fact[];note:string}
interface Result {document_id:string;state:string;items:Mention[];note:string}
@Component({selector:'tr-document-skills',standalone:true,imports:[HumanStatus,TrIcon,RouterLink],template:`
<a [routerLink]="['/documents',id]" class="text-indigo-700 font-semibold text-sm">← Document</a>
<div class="flex flex-wrap items-center justify-between gap-4 my-6"><div><h1 class="text-3xl font-bold"><tr-icon name="brain" [size]="23" class="inline-flex align-middle mr-2"/> Compétences mentionnées</h1><p class="text-sm mt-2 text-slate-500">Une mention dans le CV n'est pas une expertise prouvée. Aucun score de recrutement n'est calculé ici.</p></div><a class="btn-light" [routerLink]="['/documents',id,'preuves']"><tr-icon name="file-search" [size]="17"/> SkillsProof : examiner les sources</a><button class="btn-primary" (click)="analyze()" [disabled]="busy()">{{busy()?'En cours…':'Analyser / actualiser'}}</button></div>
@if(error()){<p class="alert-error mb-4" role="alert">{{error()}}</p>}
@if(info()){<p class="alert-ok mb-4" role="status">{{info()}}</p>}
@if(loading()){<p>Chargement…</p>}
@else if(data();as d){<div class="card p-5 mb-5"><span class="font-semibold">État de l’analyse :</span> {{d.state | humanStatus:'document'}} · {{d.items.length}} mention(s)</div>
@if(!d.items.length){<p class="card p-5">Aucune mention retrouvée. Cela ne signifie pas que le candidat ne possède pas ces compétences.</p>}
@for(m of d.items;track m.id){<article class="card p-5 mb-4"><div class="flex flex-wrap justify-between gap-2"><div><h2 class="font-semibold text-lg">{{m.skill_label}}</h2><p class="text-xs mt-1 text-slate-500">Page {{m.page_number}}</p></div><span class="text-sm font-medium">{{m.status | humanStatus:'mention'}}</span></div><blockquote class="mt-3 border-l-2 border-indigo-300 pl-4 whitespace-pre-wrap text-sm leading-6">{{m.source_quote}}</blockquote><p class="text-xs mt-2 text-slate-500">Terme retrouvé : {{m.matched_text}}</p><details class="text-xs muted mt-3"><summary class="cursor-pointer">Informations techniques de la détection</summary><p class="mt-2">Méthode : {{m.method}} · Règle : {{m.rules_version}} · Contexte : {{m.context_code || 'non renseigné'}}</p></details>
<div class="flex flex-wrap gap-2 mt-4"><button class="btn-light" (click)="review(m,'confirmed')">Confirmer la mention</button><button class="btn-light" (click)="review(m,'needs_review')">À vérifier</button><button class="btn-light" (click)="review(m,'rejected')">Corriger : non pertinente</button></div></article>}
}
@if(facts();as f){
<section class="card p-5 mt-7"><h2 class="text-xl font-bold mb-2">Parcours extrait mot pour mot</h2>
<p class="text-sm text-slate-500 mb-4">Lignes à examiner : aucun diplôme, emploi, durée ni expertise déduit automatiquement.</p>
@for(item of f.items;track item.id){<div class="border-t py-3">
<strong>{{item.category}}</strong> · <small>Page {{item.page_number}}</small>
<p class="whitespace-pre-wrap text-sm mt-1">{{item.source_text}}</p>
</div>}
@if(!f.items.length){<p class="text-sm text-slate-500">Aucune rubrique structurée détectée.</p>}
</section>}
`})
export class DocumentSkills implements OnInit {
 private http=inject(HttpClient);private route=inject(ActivatedRoute);
 get id(){return this.route.snapshot.paramMap.get('id')??''}
 readonly facts=signal<FactsResult|null>(null);readonly data=signal<Result|null>(null);readonly loading=signal(false);readonly busy=signal(false);readonly error=signal('');readonly info=signal('');
 ngOnInit(){void this.load()}
 async load(){this.loading.set(true);try{this.data.set(await firstValueFrom(this.http.get<Result>(`/api/v1/documents/${this.id}/nlp`)));
      this.facts.set(await firstValueFrom(this.http.get<FactsResult>(`/api/v1/documents/${this.id}/nlp/facts`)))}catch(e){this.error.set(apiError(e))}finally{this.loading.set(false)}}
 async analyze(){this.busy.set(true);this.error.set('');try{await firstValueFrom(this.http.post(`/api/v1/documents/${this.id}/nlp/analyze`,{}));this.info.set('Analyse placée dans la file de traitement. Actualisez ensuite pour consulter les résultats.');}catch(e){this.error.set(apiError(e))}finally{this.busy.set(false)}}
 async review(m:Mention,decision:string){this.error.set('');try{await firstValueFrom(this.http.patch(`/api/v1/documents/${this.id}/nlp/${m.id}/review`,{decision}));await this.load()}catch(e){this.error.set(apiError(e))}}
}
