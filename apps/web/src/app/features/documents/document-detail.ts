import { HumanStatus } from '../../shared/ui/human-status';
import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { apiError } from '../../shared/recruitment';
interface Detail {id:string;filename:string;status:string;page_count:number;error_code:string|null;warnings:{page_number:number|null;code:string;message:string}[]}
interface ExtractedPage {page_number:number;text:string;method:string;version:string;verification_status:string}
@Component({selector:'tr-document',standalone:true,imports:[HumanStatus,TrIcon,RouterLink],template:`
<a routerLink="/importations" class="text-sm font-semibold text-indigo-700">← Importations</a>
<div class="mt-4 mb-6 flex flex-wrap justify-between gap-4 items-center"><div><h1 class="text-3xl font-bold"><tr-icon name="file" [size]="23" class="inline-flex align-middle mr-2"/> Extraction documentaire</h1><p class="mt-2 text-slate-500">Texte original extrait, sans interprétation des compétences.</p></div><div class="flex gap-2"><a class="btn-light" [routerLink]="['/documents',id,'visionneuse']">Visualiseur</a><a class="btn-light" [routerLink]="['/documents',id,'controle']">Contrôle qualité</a><a class="btn-light" [routerLink]="['/documents',id,'competences']">Mentions NLP</a><button class="btn-light" (click)="download()" [disabled]="loading()">Télécharger le document</button><button class="btn-light" (click)="retry()" [disabled]="busy() || !retryAllowed()">Relancer l'extraction</button></div></div>
@if(error()){<div class="alert-error mb-5" role="alert">{{error()}}</div>}
@if(info()){<div class="alert-ok mb-5" role="status">{{info()}}</div>}
@if(loading()){<p class="text-slate-500">Chargement…</p>}
@else if(detail();as d){
<div class="card p-6 mb-5"><h2 class="font-semibold break-all">{{d.filename}}</h2><p class="text-sm mt-2 text-slate-500">État : {{d.status | humanStatus:'document'}} · {{d.page_count}} page(s) de texte sauvegardée(s)</p>@if(d.error_code){<details class="text-xs muted mt-2"><summary class="cursor-pointer">Détail technique du problème</summary><p class="text-rose-700 mt-2">{{d.error_code}}</p></details>}</div>
@if(d.warnings.length){<section class="card p-5 mb-5"><h2 class="font-bold mb-2">Informations à vérifier</h2>@for(w of d.warnings;track $index){<p class="text-sm py-1">Page {{w.page_number ?? '?'}} : {{w.message}}</p>}</section>}
@for(p of pages();track p.page_number){<article class="card p-6 mb-5"><div class="mb-4 flex flex-wrap justify-between gap-2"><h2 class="font-bold">Page {{p.page_number}}</h2><span class="text-xs text-slate-500">{{p.verification_status | humanStatus:'document'}}</span></div><details class="text-xs muted mb-3"><summary class="cursor-pointer">Méthode de lecture</summary><p>{{p.method}} · {{p.version}}</p></details><pre class="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-slate-700 dark:text-slate-200">{{p.text || 'Aucun texte extrait'}}</pre></article>}
@if(!pages().length){<p class="text-slate-500">Le traitement n'a pas encore produit de texte consultable.</p>}
}
`})
export class DocumentDetail implements OnInit {
 private http=inject(HttpClient);private route=inject(ActivatedRoute);readonly detail=signal<Detail|null>(null);readonly pages=signal<ExtractedPage[]>([]);readonly loading=signal(true);readonly busy=signal(false);readonly error=signal('');readonly info=signal('');
 get id(){return this.route.snapshot.paramMap.get('id')??'';}
 ngOnInit(){void this.load();}
 retryAllowed(){return ['pending','failed'].includes(this.detail()?.status??'');}
 async load(){this.loading.set(true);this.error.set('');try{const [detail,pages]=await Promise.all([firstValueFrom(this.http.get<Detail>(`/api/v1/documents/${this.id}`)),firstValueFrom(this.http.get<{items:ExtractedPage[]}>(`/api/v1/documents/${this.id}/pages`))]);this.detail.set(detail);this.pages.set(pages.items);}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 async retry(){this.busy.set(true);this.error.set('');try{const res=await firstValueFrom(this.http.post<{queued:boolean}>(`/api/v1/documents/${this.id}/retry`,{}));this.info.set(res.queued?'Nouvelle extraction en file.':'File de traitement indisponible. Réessayez plus tard.');await this.load();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async download(){this.error.set('');try{const blob=await firstValueFrom(this.http.get(`/api/v1/documents/${this.id}/download`,{responseType:'blob'}));const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`cv-${this.id}.${blob.type==='application/pdf'?'pdf':'docx'}`;a.click();URL.revokeObjectURL(url);}catch(e){this.error.set(apiError(e));}}
}
