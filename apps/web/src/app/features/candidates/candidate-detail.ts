import { TrIcon } from '../../shared/ui/tr-icon';
import { Component, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { apiError, Candidate } from '../../shared/recruitment';
@Component({selector:'tr-candidate-detail',standalone:true,imports:[TrIcon,RouterLink,DatePipe],template:`
<header class="page-heading"><div><a routerLink="/candidats" class="inline-flex items-center gap-1.5 text-sm font-medium text-[#205f77] hover:underline dark:text-[#a8d4ef]"><tr-icon name="arrow-left" [size]="15"/> Tous les candidats</a><h1 class="mt-2 text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Fiche candidat</h1><p class="mt-1 text-sm text-slate-500">Informations saisies ou confirmées. Aucune qualification n'est déduite de l'identité.</p></div></header>
@if(error()){<div role="alert" class="alert-error mb-5">{{error()}} <button type="button" class="ml-2 underline" (click)="load()"><tr-icon name="refresh" [size]="16" class="inline-flex align-middle mr-1"/>Réessayer</button></div>}
@if(loading()){<div class="card p-8 animate-pulse text-slate-500" role="status">Chargement du dossier…</div>}
@else if(candidate();as c){<div class="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
<section class="card p-6 sm:p-8"><div class="flex items-start gap-4"><div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#e4eef5] font-bold text-[#245b93] ring-1 ring-[#c8dce9] text-xl dark:bg-[#263f52] dark:text-[#a8d4ef] dark:ring-[#3f6078]" aria-hidden="true">{{initials(c.full_name)}}</div><div class="min-w-0"><p class="eyebrow"><tr-icon name="user" [size]="14"/> Dossier {{c.reference}}</p><h2 class="text-2xl font-bold break-words text-slate-900 dark:text-white mt-1">{{c.full_name}}</h2><p class="mt-1 text-xs text-slate-400">Enregistré le {{c.created_at | date:'dd/MM/yyyy'}}</p></div></div>
<dl class="mt-8 grid gap-5 sm:grid-cols-2 bg-[#f8fbfc] dark:bg-slate-800/60 p-5 rounded-2xl border border-slate-100 dark:border-slate-700/60"><div><dt class="field-label text-xs uppercase tracking-wider text-slate-400">Courriel de contact</dt><dd class="break-all text-sm font-medium text-slate-800 dark:text-slate-100 mt-1">{{c.email || 'Non renseigné'}}</dd></div><div><dt class="field-label text-xs uppercase tracking-wider text-slate-400">Téléphone</dt><dd class="text-sm font-medium text-slate-800 dark:text-slate-100 mt-1">{{c.phone || 'Non renseigné'}}</dd></div></dl>
<div class="mt-6 rounded-xl bg-amber-50/70 border border-amber-200/60 p-4 text-xs text-amber-900 dark:bg-amber-950/30 dark:border-amber-800/40 dark:text-amber-200 leading-relaxed">Les informations d'identité sont strictement séparées de l'analyse des compétences pour préserver l'équité du recrutement.</div></section>
<aside class="card p-6"><h2 class="section-heading">Actions pour ce dossier</h2><div class="mt-5 flex flex-col gap-2.5"><a routerLink="/candidatures" class="btn-primary text-center">Gérer les candidatures</a><a routerLink="/importations" class="btn-light text-center">Consulter les CV importés</a><a routerLink="/matching" class="btn-light text-center">Voir les analyses documentaires</a></div><div class="border-t border-slate-100 dark:border-slate-700 mt-6 pt-5"><h3 class="font-semibold text-sm text-slate-800 dark:text-slate-100">Espace candidat sécurisé</h3><p class="section-caption mt-1.5 text-xs">Un code à usage unique sera envoyé directement par email au candidat.</p><button type="button" class="btn-light mt-3 w-full justify-center" [disabled]="sending() || !c.email" (click)="sendCandidateCode()"><tr-icon name="mail" [size]="16"/> {{sending()?'Envoi…':'Envoyer un code d’accès'}}</button>@if(sent()){<p role="status" class="alert-ok mt-3 text-xs">Code envoyé au candidat.</p>}</div><p class="mt-6 text-xs text-slate-400 leading-relaxed">Les historiques de candidatures sont consultables depuis le registre sécurisé.</p></aside>
</div>}
`})
export class CandidateDetail implements OnInit {
 private http=inject(HttpClient);private route=inject(ActivatedRoute);
 readonly loading=signal(true);readonly error=signal('');readonly sending=signal(false);readonly sent=signal(false);readonly candidate=signal<Candidate|null>(null);
 ngOnInit(){void this.load();}
 async load(){this.loading.set(true);this.error.set('');try {const id=this.route.snapshot.paramMap.get('id');if(!id)throw new Error('Identifiant manquant');this.candidate.set(await firstValueFrom(this.http.get<Candidate>(`/api/v1/candidates/${encodeURIComponent(id)}`)));}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 async sendCandidateCode(){const id=this.route.snapshot.paramMap.get('id');if(!id||!this.candidate()?.email)return;
  this.sending.set(true);this.error.set('');this.sent.set(false);
  try{await firstValueFrom(this.http.post(`/api/v1/candidate-portal/candidates/${encodeURIComponent(id)}/send-access-code`,{}));this.sent.set(true);}
  catch(e){this.error.set(apiError(e));}finally{this.sending.set(false);}}
 initials(s:string){return s.trim().split(/\s+/).slice(0,2).map(x=>x[0]?.toUpperCase()??'').join('');}
}
