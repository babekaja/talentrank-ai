import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, computed, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { apiError } from '../../shared/recruitment';
import { EmptyState } from '../../shared/ui/empty-state';
interface Skill {id:string;code:string;label_fr:string;label_en:string;taxonomy:string;version:string;external_uri:string|null}
@Component({selector:'tr-skills',standalone:true,imports:[TrIcon,RouterLink,EmptyState],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="brain" [size]="15"/> Langage commun des métiers</p><h1>Référentiel des compétences</h1><p>Retrouvez les compétences que le système sait nommer et leurs variantes linguistiques. Une proximité de sens n'est jamais considérée comme une équivalence automatiquement validée.</p></div><a class="btn-light" routerLink="/recherche-semantique">Explorer les rapprochements</a></header>
<div class="grid grid-cols-2 gap-3 mb-6"><div class="stat-card"><span class="meta-label">Compétences affichées</span><strong class="text-3xl">{{skills().length}}</strong><span class="text-xs muted">Maximum 100 par recherche</span></div><div class="stat-card"><span class="meta-label">Référentiels représentés</span><strong class="text-3xl">{{taxonomies().length}}</strong><span class="text-xs muted">Identifiés dans les résultats chargés</span></div></div>
<section class="card overflow-hidden"><div class="p-5 sm:p-6 border-b border-slate-100 dark:border-slate-700"><h2 class="section-heading">Trouver une compétence</h2><form (submit)="submitSearch($event)" class="mt-4 flex flex-wrap gap-3"><label class="flex-1 min-w-[220px]"><span class="field-label">Nom ou code, en français ou en anglais</span><input class="field" type="search" [value]="search()" (input)="search.set($any($event.target).value)" maxlength="100" placeholder="Ex. Angular, logistique, gestion de stock"/></label><button class="btn-primary self-end" type="submit" [disabled]="loading()"><tr-icon name="search" [size]="16" class="inline-flex align-middle mr-1"/>Rechercher</button><button class="btn-light self-end" type="button" (click)="clearSearch()" [disabled]="loading() || (!search()&&!query())">Effacer</button></form><div class="flex flex-wrap gap-3 items-end mt-4"><label><span class="field-label">Filtrer les résultats affichés</span><select class="field !w-auto" [value]="taxonomy()" (change)="taxonomy.set($any($event.target).value)"><option value="">Tous les référentiels</option>@for(t of taxonomies();track t){<option [value]="t">{{t}}</option>}</select></label><p class="text-xs muted pb-3" aria-live="polite">{{filtered().length}} compétence(s) affichée(s)</p></div></div>
@if(error()){<div class="alert-error m-5" role="alert">{{error()}} <button type="button" class="underline ml-2" (click)="load()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Réessayer</button></div>}
@if(loading()){<p class="p-8 muted" role="status">Recherche dans les compétences…</p>}
@else if(!filtered().length){<tr-empty-state illustration="skills-extraction" title="Aucune compétence trouvée" description="Essayez une expression plus courte ou retirez le filtre de référentiel. Si le catalogue est vide, l'administrateur doit initialiser les compétences."/>}
@else{<div class="overflow-x-auto"><table class="w-full min-w-[650px]"><thead class="table-head"><tr><th class="px-5 py-4">Compétence</th><th>En anglais</th><th>Référentiel</th><th>Actions</th></tr></thead><tbody>@for(s of filtered();track s.id){<tr><td class="table-td"><strong>{{s.label_fr}}</strong><p class="mt-1 text-xs muted font-mono">{{s.code}}</p></td><td class="table-td">{{s.label_en||'Non renseigné'}}</td><td class="table-td"><span class="soft-badge">{{s.taxonomy}}</span><p class="text-xs muted mt-2">Version {{s.version}}</p></td><td class="table-td"><a class="inline-link" [routerLink]="['/competences',s.id,'synonymes']">Voir les synonymes →</a>@if(s.external_uri && isOfficialUrl(s.external_uri)){<a class="block inline-link mt-2 text-xs" [href]="s.external_uri" target="_blank" rel="noopener noreferrer">Voir la source externe ↗</a>}</td></tr>}</tbody></table></div>}
</section><p class="mt-4 section-caption">Les descriptions locales n'établissent pas à elles seules la reconnaissance officielle d'un diplôme ou d'une qualification.</p>`})
export class Skills implements OnInit {
 private readonly http=inject(HttpClient);readonly skills=signal<Skill[]>([]);readonly search=signal('');readonly query=signal('');readonly taxonomy=signal('');
 readonly loading=signal(true);readonly error=signal('');
 readonly taxonomies=computed(()=>[...new Set(this.skills().map(s=>s.taxonomy))].sort());
 readonly filtered=computed(()=>this.skills().filter(s=>!this.taxonomy()||s.taxonomy===this.taxonomy()));
 ngOnInit(){void this.load();}
 submitSearch(e:Event){e.preventDefault();this.query.set(this.search().trim());void this.load();}
 clearSearch(){this.search.set('');this.query.set('');this.taxonomy.set('');void this.load();}
 isOfficialUrl(value:string){try{return new URL(value).protocol==='https:';}catch{return false;}}
 async load(){this.loading.set(true);this.error.set('');try{const r=await firstValueFrom(this.http.get<{items:Skill[]}>('/api/v1/skills',{params:{q:this.query(),limit:100}}));this.skills.set(r.items);if(this.taxonomy()&&!r.items.some(x=>x.taxonomy===this.taxonomy()))this.taxonomy.set('');}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
}
