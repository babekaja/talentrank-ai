import { HumanStatus } from '../../shared/ui/human-status';
import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, inject, OnInit, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { Campaign, Application, Page, apiError } from '../../shared/recruitment';
interface Run {id:string;status:string;created_at:string;total:number;processed:number}
@Component({selector:'tr-campaign-detail',standalone:true,imports:[HumanStatus,TrIcon,RouterLink],template:`
<header class="page-heading"><div><a routerLink="/campagnes" class="inline-flex items-center gap-1.5 text-sm font-medium text-[#205f77] hover:underline dark:text-[#a8d4ef]"><tr-icon name="arrow-left" [size]="15"/> Toutes les campagnes</a><h1 class="mt-2 text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Dossier de campagne</h1><p class="mt-1 text-sm text-slate-500">Suivi de l'examen humain et des analyses documentaires.</p></div><a routerLink="/importations" class="btn-primary"><tr-icon name="upload" [size]="16" class="inline-flex align-middle mr-1.5"/> Importer des CV</a></header>
@if(error()){<p role="alert" class="alert-error mb-5">{{error()}} <button class="underline ml-2" (click)="load()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Réessayer</button></p>}
@if(loading()){<p role="status" class="card p-6 text-slate-500">Chargement des informations…</p>}
@else if(campaign();as c){<div class="mb-6 grid gap-4 md:grid-cols-3"><article class="stat-card"><p class="eyebrow"><tr-icon name="clipboard" [size]="15"/> Campagne</p><h2 class="text-xl font-bold text-slate-800 dark:text-slate-100 mt-1">{{c.name}}</h2><p class="mt-1"><span class="status-pill status-pill--good">{{c.status | humanStatus:'campaign'}}</span></p></article><article class="stat-card"><p class="eyebrow">Candidatures reçues</p><strong class="text-3xl font-bold text-[#172e49] dark:text-white">{{total()}}</strong><p class="text-xs text-slate-400">Dossiers associés à ce recrutement</p></article><article class="stat-card"><p class="eyebrow">Analyses comparatives</p><strong class="text-3xl font-bold text-[#172e49] dark:text-white">{{runs().length}}</strong><a routerLink="/matching" class="inline-link text-sm mt-1">Comparer les dossiers →</a></article></div>
<section class="card overflow-hidden mb-6"><div class="flex items-center justify-between gap-3 p-5 border-b border-slate-100 dark:border-slate-700/60"><h2 class="section-heading">Candidatures</h2><a routerLink="/candidatures" class="inline-link text-sm">Enregistrer une candidature →</a></div>
@if(!applications().length){<p class="px-5 py-6 text-slate-500">Aucune candidature liée à cette campagne.</p>}
@else{<div class="overflow-x-auto"><table class="w-full min-w-[530px]"><thead class="table-head"><tr><th class="px-5 py-3.5">Référence dossier</th><th>Examen humain</th><th>Enregistrée</th></tr></thead><tbody>@for(a of applications();track a.id){<tr class="hover:bg-[#f6fafb] dark:hover:bg-[#1d3545] transition-colors"><td class="table-td font-mono text-xs">{{a.id.slice(0,12)}}</td><td class="table-td"><span class="status-pill">{{a.review_status}}</span></td><td class="table-td text-slate-500 text-xs">{{a.created_at.slice(0,10)}}</td></tr>}</tbody></table></div>}
<div class="flex justify-between items-center p-4 text-sm border-t border-slate-100 dark:border-slate-700/60"><span>{{total()}} candidature(s)</span><div class="flex gap-2"><button class="btn-light" [disabled]="offset()===0" (click)="page(-1)">Précédent</button><button class="btn-light" [disabled]="offset()+25>=total()" (click)="page(1)"><tr-icon name="arrow-right" [size]="16" class="inline-flex align-middle mr-1"/>Suivant</button></div></div></section>
<section class="card p-5"><h2 class="section-heading mb-3">Historique des analyses</h2>@if(!runs().length){<p class="text-sm text-slate-500">Aucune analyse enregistrée pour le moment.</p>}
@for(r of runs();track r.id){<div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 py-3.5 dark:border-slate-800 first:border-t-0"><div><p class="font-medium text-sm text-slate-800 dark:text-slate-100"><span class="font-mono bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded text-xs">{{r.id.slice(0,8)}}</span> · {{r.status | humanStatus:'run'}}</p><p class="text-xs text-slate-400 mt-1">{{r.processed}} sur {{r.total}} traités</p></div><a routerLink="/matching" class="inline-link text-sm font-semibold">Ouvrir l'analyse →</a></div>}</section>
}
`})
export class CampaignDetail implements OnInit {
 private http=inject(HttpClient);private route=inject(ActivatedRoute);
 readonly loading=signal(true);readonly error=signal('');readonly campaign=signal<Campaign|null>(null);
 readonly applications=signal<Application[]>([]);readonly total=signal(0);readonly offset=signal(0);readonly runs=signal<Run[]>([]);
 private get id(){return this.route.snapshot.paramMap.get('id')??'';}
 ngOnInit(){void this.load();}
 async load(){this.loading.set(true);this.error.set('');try{
   const [c,r]=await Promise.all([firstValueFrom(this.http.get<Campaign>(`/api/v1/campaigns/${encodeURIComponent(this.id)}`)),firstValueFrom(this.http.get<{items:Run[]}>('/api/v1/matching-runs',{params:{campaign_id:this.id}}))]);
   this.campaign.set(c);this.runs.set(r.items);
   await this.loadApplications();
 }catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 async loadApplications(){try{const result=await firstValueFrom(this.http.get<Page<Application>>('/api/v1/applications',{params:{campaign_id:this.id,limit:25,offset:this.offset()}}));this.applications.set(result.items);this.total.set(result.total);}catch(e){this.error.set(apiError(e));}}
 page(delta:number){this.offset.update(x=>Math.max(0,x+25*delta));void this.loadApplications();}
}
