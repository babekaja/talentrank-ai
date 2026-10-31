import { TrIcon } from '../../shared/ui/tr-icon';
import { afterNextRender, Component, ElementRef, inject, Injector, OnInit, signal, viewChild } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { firstValueFrom } from 'rxjs';
import { Application, Candidate, Campaign, Page, apiError } from '../../shared/recruitment';

@Component({selector:'tr-applications',standalone:true,imports:[TrIcon,FormsModule],template:`
<header class="page-intro"><div><p class="eyebrow"><tr-icon name="users" [size]="15"/> Recrutement · étape 3</p><h1 class="mt-2">Candidatures</h1><p>Associez les dossiers aux campagnes, puis partagez des observations utiles et fondées sur les documents.</p></div></header>
@if(error()){<p class="alert-error mb-4" role="alert">{{error()}}</p>}@if(success()){<p #successMessage class="alert-ok mb-4 scroll-mt-24" role="status" tabindex="-1">{{success()}}</p>}
<form class="card mb-6 p-6" (ngSubmit)="create()"><div class="mb-5"><div class="flex items-center gap-3 mb-1"><span class="step-number">1</span><h2 class="section-heading">Enregistrer une candidature</h2></div><p class="section-caption">Choisissez la campagne, retrouvez la personne, puis associez son dossier.</p></div><div class="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]"><label><span class="field-label">Campagne active</span><select class="field" name="campaign" [(ngModel)]="campaign_id" required><option value="">Choisir une campagne</option>@for(c of campaigns();track c.id){@if(c.status==='active'){<option [value]="c.id">{{c.name}}</option>}}</select></label><label><span class="field-label">Rechercher un candidat</span><div class="flex gap-2"><input class="field" type="search" name="candidateSearch" [(ngModel)]="candidateSearch" placeholder="Nom du candidat"/><button type="button" class="btn-light" (click)="searchCandidates()">Chercher</button></div></label><label><span class="field-label">Candidat</span><select class="field" name="candidate" [(ngModel)]="candidate_id" required><option value="">Choisir un candidat</option>@for(c of candidates();track c.id){<option [value]="c.id">{{c.full_name}} ({{c.reference}})</option>}</select></label><button class="btn-primary self-end" [disabled]="busy() || !campaign_id || !candidate_id" type="submit">Associer</button></div></form>
<div class="card overflow-hidden">@if(loading()){<p class="p-6">Chargement…</p>}@else if(!rows().length){<div class="p-8 text-center"><h3 class="font-bold">Aucun dossier pour le moment</h3><p class="section-caption mt-2">Les candidatures enregistrées apparaîtront ici. Vous pourrez ensuite demander une revue humaine.</p></div>}@else{
<div class="hidden overflow-x-auto md:block"><table class="data-table w-full min-w-[660px]"><thead class="table-head"><tr><th class="px-5 py-4">Candidat</th><th>Campagne</th><th>État d'examen</th><th>Action</th></tr></thead><tbody>@for(a of rows();track a.id){<tr><td class="table-td"><div class="flex items-center gap-3"><div class="flex-shrink-0 h-8 w-8 rounded-full bg-[#deeef3] flex items-center justify-center text-xs font-bold text-[#205f77]" aria-hidden="true">{{(a.candidate_name ?? candidateName(a.candidate_id)).split(' ').slice(0,2).map(n => n[0]).join('').toUpperCase()}}</div><div><span class="font-semibold">{{a.candidate_name ?? candidateName(a.candidate_id)}}</span> <span class="text-xs text-slate-400">{{a.candidate_reference}}</span></div></div></td><td class="table-td">{{a.campaign_name ?? campaignName(a.campaign_id)}}</td><td class="table-td"><span class="status-pill" [class.status-pill--good]="a.review_status==='reviewed'" [class.status-pill--warning]="a.review_status==='pending'||a.review_status==='needs_clarification'">{{reviewLabel(a.review_status)}}</span></td><td class="table-td"><button type="button" (click)="select(a, $event)" [disabled]="busy()" [attr.aria-expanded]="selected()?.id===a.id" [attr.aria-controls]="selected()?.id===a.id ? 'application-review' : null" class="record-action">Consulter et donner un avis <tr-icon name="arrow-right" [size]="16"/></button></td></tr>}</tbody></table></div>
<div class="space-y-3 bg-[#f8fbfc] p-3 md:hidden dark:bg-[#112333]">@for(a of rows();track a.id){<article class="record-card"><div class="flex flex-wrap items-start justify-between gap-3"><div><h2 class="record-card__title">{{a.candidate_name ?? candidateName(a.candidate_id)}}</h2><p class="record-card__meta mt-1">{{a.candidate_reference}}</p></div><span class="status-pill" [class.status-pill--good]="a.review_status==='reviewed'" [class.status-pill--warning]="a.review_status==='pending'||a.review_status==='needs_clarification'">{{reviewLabel(a.review_status)}}</span></div><div class="record-card__divider"></div><p class="record-card__label">Campagne</p><p class="record-card__value">{{a.campaign_name ?? campaignName(a.campaign_id)}}</p><button type="button" (click)="select(a, $event)" [disabled]="busy()" [attr.aria-expanded]="selected()?.id===a.id" [attr.aria-controls]="selected()?.id===a.id ? 'application-review' : null" class="record-action mt-4">Consulter et donner un avis <tr-icon name="arrow-right" [size]="16"/></button></article>}</div>}
</div>
<div class="list-pagination flex justify-between items-center p-4 text-sm"><span>{{total()}} candidature(s) · page {{offset()/25+1}}</span><div class="flex gap-2"><button type="button" class="btn-light" [disabled]="loading() || offset()===0" (click)="page(-1)">Précédent</button><button type="button" class="btn-light" [disabled]="loading() || offset()+25>=total()" (click)="page(1)"><tr-icon name="arrow-right" [size]="16" class="inline-flex align-middle mr-1"/>Suivant</button></div></div>
@if(selected()){
<form #reviewPanel id="application-review" class="card mt-6 scroll-mt-24 p-6" aria-labelledby="application-review-title" (ngSubmit)="review()">
 <div class="mb-5 flex items-start justify-between gap-4 border-b border-slate-100 pb-4 dark:border-slate-800">
  <div class="min-w-0"><p class="mb-1 text-xs font-semibold uppercase tracking-wide text-[#4f8fa0]">Avis humain</p><h2 #reviewHeading id="application-review-title" tabindex="-1" class="text-xl font-bold text-slate-800 dark:text-slate-100">{{selected()!.candidate_name ?? candidateName(selected()!.candidate_id)}}</h2><p class="section-caption mt-1">{{selected()!.campaign_name ?? campaignName(selected()!.campaign_id)}}</p></div>
  <button type="button" class="btn-light shrink-0" [disabled]="busy()" (click)="closeReview()"><tr-icon name="x" [size]="16"/>Fermer</button>
 </div>
 @if(reviewError()){<p class="alert-error mb-4" role="alert">{{reviewError()}}</p>}
 <label class="field-label" for="review-finding">Appréciation</label>
 <select id="review-finding" class="field" name="finding" [(ngModel)]="finding" [disabled]="busy()"><option value="reviewed">Examiné</option><option value="needs_clarification">Vérification nécessaire</option><option value="shortlisted">Ajouter à la liste d'examen</option></select>
 <label class="field-label mt-4" for="review-note">Note factuelle du recruteur</label>
 <textarea id="review-note" class="field" name="note" [(ngModel)]="note" [disabled]="busy()" required minlength="3" maxlength="4000" rows="4" placeholder="Votre appréciation après examen du dossier…"></textarea>
 <button class="btn-primary mt-4" [disabled]="busy() || note.trim().length<3" type="submit">{{busy()?'Enregistrement…':"Enregistrer l'avis"}}</button>
 <p class="mt-3 text-xs text-slate-500">Ce statut est un avis humain, pas une décision automatisée d'embauche ou de rejet.</p>
 <section class="mt-6 border-t border-slate-200 pt-4 dark:border-slate-700" aria-labelledby="review-history-title" [attr.aria-busy]="reviewsLoading()">
  <h3 id="review-history-title" class="mb-4 font-bold text-slate-700 dark:text-slate-300">Historique des avis</h3>
  @if(reviewsLoading()){<p class="text-sm" role="status">Chargement des avis…</p>}
  @else if(reviewsError()){<div class="alert-error" role="alert"><p>{{reviewsError()}}</p><button type="button" class="btn-light mt-3" (click)="loadReviews(selected()!.id)">Réessayer</button></div>}
  @else if(!pastReviews().length){<p class="text-sm text-slate-500">Aucun avis enregistré pour cette candidature.</p>}
  @else{<div class="space-y-3">@for(r of pastReviews();track $index){<div class="rounded-r-lg border-l-4 border-[#205f77] bg-[#f5fafb] py-1 pl-4 text-sm dark:bg-slate-800"><div class="mb-1 flex flex-wrap items-center gap-2"><span class="font-semibold text-[#205f77] dark:text-slate-200">{{reviewLabel(r.finding)}}</span><span class="text-slate-300 dark:text-slate-600">·</span><time class="text-xs text-slate-400">{{r.created_at.slice(0,16).replace('T',' ')}}</time></div><p class="leading-relaxed text-slate-600 dark:text-slate-400">{{r.note}}</p></div>}</div>}
 </section>
</form>}
`})
export class Applications implements OnInit {
 private http=inject(HttpClient);private injector=inject(Injector);
 private reviewPanel=viewChild<ElementRef<HTMLElement>>('reviewPanel');
 private reviewHeading=viewChild<ElementRef<HTMLElement>>('reviewHeading');
 private successMessage=viewChild<ElementRef<HTMLElement>>('successMessage');
 private reviewTrigger:HTMLElement|null=null;private reviewRequest=0;
 readonly reviewsLoading=signal(false);readonly reviewsError=signal('');readonly reviewError=signal('');
readonly rows=signal<Application[]>([]);readonly candidates=signal<Candidate[]>([]);readonly campaigns=signal<Campaign[]>([]);readonly selected=signal<Application|null>(null);readonly pastReviews=signal<{finding:string;note:string;created_at:string}[]>([]);readonly loading=signal(true);readonly busy=signal(false);readonly offset=signal(0);readonly total=signal(0);readonly error=signal('');readonly success=signal('');campaign_id='';candidate_id='';candidateSearch='';finding:'reviewed'|'needs_clarification'|'shortlisted'='reviewed';note='';
 ngOnInit(){void this.load();}
 page(delta:number){this.offset.update(x=>Math.max(0,x+delta*25));this.selected.set(null);void this.load();}
 reviewLabel(v:string){return ({pending:'À examiner',reviewed:'Examiné',needs_clarification:'Précisions nécessaires',shortlisted:'À revoir en équipe'} as Record<string,string>)[v]??v;}
 candidateName(id:string){return this.candidates().find(c=>c.id===id)?.full_name || 'Candidat non trouvé';}
 campaignName(id:string){return this.campaigns().find(c=>c.id===id)?.name || 'Campagne';}
 async load(){this.loading.set(true);try{const [a,c,ca]=await Promise.all([firstValueFrom(this.http.get<Page<Application>>('/api/v1/applications',{params:{limit:25,offset:this.offset()}})),firstValueFrom(this.http.get<Page<Candidate>>('/api/v1/candidates?limit=100')),firstValueFrom(this.http.get<Page<Campaign>>('/api/v1/campaigns?limit=100'))]);this.rows.set(a.items);this.total.set(a.total);this.candidates.set(c.items);this.campaigns.set(ca.items);}catch(e){this.error.set(apiError(e));}finally{this.loading.set(false);}}
 async create(){this.busy.set(true);this.error.set('');this.success.set('');try{await firstValueFrom(this.http.post('/api/v1/applications',{candidate_id:this.candidate_id,campaign_id:this.campaign_id}));this.candidate_id='';this.success.set('Candidature enregistrée.');this.offset.set(0);await this.load();}catch(e){this.error.set(apiError(e));}finally{this.busy.set(false);}}
 async select(v:Application,event?:Event){
  if(this.busy())return;
  this.reviewTrigger=event?.currentTarget as HTMLElement|null;
  this.selected.set(v);this.finding='reviewed';this.note='';this.pastReviews.set([]);
  this.error.set('');this.success.set('');this.reviewError.set('');
  afterNextRender(()=>{
   if(this.selected()?.id!==v.id)return;
   this.reviewPanel()?.nativeElement.scrollIntoView({block:'start',behavior:'instant'});
   this.reviewHeading()?.nativeElement.focus({preventScroll:true});
  },{injector:this.injector});
  await this.loadReviews(v.id);
 }
 closeReview(){
  if(this.busy())return;
  this.selected.set(null);this.reviewRequest++;this.reviewsLoading.set(false);
  this.pastReviews.set([]);this.reviewsError.set('');this.reviewError.set('');this.note='';
  this.reviewTrigger?.focus();
 }
 async loadReviews(id:string){
  const request=++this.reviewRequest;
  this.reviewsLoading.set(true);this.reviewsError.set('');
  try{
   const reviews=await firstValueFrom(this.http.get<{finding:string;note:string;created_at:string}[]>(`/api/v1/applications/${id}/reviews`));
   if(request===this.reviewRequest && this.selected()?.id===id)this.pastReviews.set(reviews);
  }catch(e){if(request===this.reviewRequest && this.selected()?.id===id)this.reviewsError.set(apiError(e));}
  finally{if(request===this.reviewRequest && this.selected()?.id===id)this.reviewsLoading.set(false);}
 }
 async searchCandidates(){try{const q=encodeURIComponent(this.candidateSearch.trim());const p=await firstValueFrom(this.http.get<Page<Candidate>>(`/api/v1/candidates?limit=100&q=${q}`));this.candidates.set(p.items);}catch(e){this.error.set(apiError(e));}}
 async review(){
  const id=this.selected()?.id;const note=this.note.trim();
  if(!id || this.busy() || note.length<3 || note.length>4000)return;
  this.busy.set(true);this.reviewError.set('');this.success.set('');
  try{
   await firstValueFrom(this.http.post(`/api/v1/applications/${id}/reviews`,{finding:this.finding,note}));
   this.selected.set(null);this.reviewRequest++;this.note='';
   this.success.set('Avis humain enregistré et tracé dans le journal.');await this.load();
   afterNextRender(()=>this.successMessage()?.nativeElement.focus(),{injector:this.injector});
  }catch(e){this.reviewError.set(apiError(e));}
  finally{this.busy.set(false);}
 }
}
