import { TrIcon } from '../../shared/ui/tr-icon';
import {Component, inject, signal} from '@angular/core';
import {RouterLink} from '@angular/router';
import {HttpClient} from '@angular/common/http';
import {firstValueFrom} from 'rxjs';
import {apiError} from '../../shared/recruitment';
interface Hit {document_id:string;filename:string;page_number:number;excerpt:string;similarity:number;status:string}
@Component({selector:'tr-semantic',standalone:true,imports:[TrIcon,RouterLink],template:`
<header class="mb-7"><h1 class="text-3xl font-bold"><tr-icon name="search" [size]="23" class="inline-flex align-middle mr-2"/> Recherche avancée dans les CV</h1><p class="mt-2 text-slate-500">Cette recherche expérimentale retrouve les passages proches de votre expression. Les résultats ne prouvent pas une compétence.</p></header>
<div class="card p-5 flex flex-wrap gap-2 mb-5"><input class="input flex-1" aria-label="Recherche sémantique" [value]="query()" (input)="query.set($any($event.target).value)" (keydown.enter)="search()" placeholder="Développement de services backend REST"/><button class="btn-primary" [disabled]="busy() || query().trim().length < 2" (click)="search()"><tr-icon name="search" [size]="16" class="inline-flex align-middle mr-1"/>Rechercher</button></div>
@if(error()){<p role="alert" class="alert-error mb-4">{{error()}}</p>}
@if(warning()){<p class="text-sm text-amber-700 mb-4">{{warning()}}</p>}
@if(busy()){<p role="status">Recherche locale en cours…</p>}
@for(r of items();track $index){<article class="card p-5 mb-4"><div class="flex justify-between"><a [routerLink]="['/documents',r.document_id]" class="font-semibold text-indigo-700">{{r.filename}}</a><span class="text-xs text-slate-500">Page {{r.page_number}} · similarité : {{r.similarity}}</span></div><p class="mt-3 text-sm whitespace-pre-wrap">{{r.excerpt}}</p><p class="mt-2 text-xs text-slate-500">Recherche uniquement : vérification humaine nécessaire.</p></article>}
`})
export class SemanticSearch {private http=inject(HttpClient);readonly query=signal('');readonly busy=signal(false);readonly error=signal('');readonly warning=signal('');readonly items=signal<Hit[]>([]);
 async search(){this.busy.set(true);this.error.set('');this.warning.set('');try{
  const r=await firstValueFrom(this.http.post<{items:Hit[];warning:string}>('/api/v1/semantic/search',{query:this.query(),limit:10}));this.items.set(r.items);this.warning.set(r.warning);
 }catch(e){this.items.set([]);this.error.set(apiError(e))}finally{this.busy.set(false)}}
}
